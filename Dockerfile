#
# BinaryMCP Engine — Optimized Multi-stage Docker Build
#
# 基于 pwnmcp, 扩展 IoT/Crypto/Reverse 分析工具
#
# Stage 1: Builder
# - Installs build-time dependencies and tools.
# - Downloads and prepares all external binaries (pwndbg, rizin, etc.).
# - Creates the Python virtual environment with all dependencies.
#
FROM --platform=linux/amd64 ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install build-time dependencies and essential tools
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      bash-completion build-essential clang cmake gcc g++ gcc-multilib \
      git curl wget file unzip sudo ca-certificates \
      python3 python3-venv python3-pip python3-dev \
      ruby-full ruby-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for Python environment management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install external tools (pwninit, checksec, one_gadget)
# Skip rizin download as v0.7.3 is no longer available
RUN wget -q https://github.com/io12/pwninit/releases/download/3.3.1/pwninit -O /usr/local/bin/pwninit && \
    chmod +x /usr/local/bin/pwninit && \
    wget https://github.com/slimm609/checksec.sh/raw/master/checksec -O /usr/local/bin/checksec && \
    chmod +x /usr/local/bin/checksec && \
    gem install one_gadget

# Create non-root user and directories
RUN useradd -m -s /bin/bash pwn && \
    mkdir -p /workspace /app && \
    chown -R pwn:pwn /workspace /app

# Install pwndbg as root (setup.sh requires sudo)
WORKDIR /home/pwn
RUN git clone --depth 1 https://github.com/pwndbg/pwndbg.git ./pwndbg && \
    cd ./pwndbg && \
    ./setup.sh --update && \
    chown -R pwn:pwn /home/pwn/pwndbg

# Install Python dependencies (as root to avoid permission issues)
WORKDIR /app
COPY --chown=pwn:pwn pyproject.toml README.md ./
RUN rm -rf .venv && \
    uv venv && \
    uv pip install --no-cache -e .[dev] && \
    chown -R pwn:pwn /app

# Switch to pwn user for remaining operations
USER pwn

# Copy the rest of the project source code
COPY --chown=pwn:pwn pwnmcp ./pwnmcp


#
# Stage 2: Final Runtime Image
# - Starts from a clean Ubuntu base.
# - Installs only runtime dependencies.
# - Copies all pre-built artifacts from the 'builder' stage.
#
FROM --platform=linux/amd64 ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    WORKSPACE_DIR=/workspace \
    GDB_PATH=pwndbg \
    ALLOW_DANGEROUS=true \
    PATH="/app/.venv/bin:$PATH"

# Install only runtime dependencies
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      gdb gdb-multiarch strace ltrace patchelf \
      python3 \
      libc6:i386 libstdc++6:i386 libgcc-s1:i386 zlib1g:i386 lib32z1 \
      libssl3:i386 libncurses6:i386 libreadline8:i386 libtinfo6:i386 \
      libc6-dbg libc6-dbg:i386 \
      binwalk \
      squashfs-tools \
      mtd-utils \
      device-tree-compiler \
      u-boot-tools \
      cpio \
      qemu-system-arm \
      qemu-system-mips \
      qemu-user-static \
      binutils \
      file \
      xxd \
      bsdextrautils \
      && \
    rm -rf /var/lib/apt/lists/*

# Copy the user and group info from the builder
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group
COPY --from=builder /etc/sudoers /etc/sudoers

# Create a symlink for python3 -> python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy pre-installed tools and binaries from the builder stage
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /var/lib/gems/ /var/lib/gems/

# Copy the application and virtual environment, preserving ownership
COPY --from=builder --chown=pwn:pwn /app /app
COPY --from=builder --chown=pwn:pwn /home/pwn /home/pwn
COPY --from=builder --chown=pwn:pwn /workspace /workspace

# ═══ 安装 Crypto/Reverse Python 工具 (runtime 阶段, 因为编译较重) ═══
RUN pip3 install --no-cache-dir --break-system-packages \
      pycryptodome \
      z3-solver \
      && true
# 注意: angr 体积巨大 (~1GB+), 默认不安装, 如需可取消下行注释:
# RUN pip3 install --no-cache-dir --break-system-packages angr

# Create pwndbg alias for root and other users
RUN printf '#!/usr/bin/env bash\nexec gdb "$@"\n' > /usr/local/bin/pwndbg && \
    chmod +x /usr/local/bin/pwndbg

# Fix editable install: add /app to Python path in venv
RUN find /app/.venv -name site-packages -type d -exec sh -c 'echo "/app" >> "$1/_app.pth"' _ {} \;

USER pwn
WORKDIR /app
VOLUME ["/workspace"]
EXPOSE 5500

CMD ["pwnmcp-server"]
