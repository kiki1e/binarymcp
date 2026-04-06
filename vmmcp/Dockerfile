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

# Install external tools (Rizin, pwninit, checksec, one_gadget)
RUN wget -q https://github.com/rizinorg/rizin/releases/download/v0.7.3/rizin_0.7.3_amd64.deb && \
    dpkg -i rizin_0.7.3_amd64.deb && \
    rm -f rizin_0.7.3_amd64.deb

RUN wget -q https://github.com/io12/pwninit/releases/download/3.3.1/pwninit -O /usr/local/bin/pwninit && \
    chmod +x /usr/local/bin/pwninit && \
    wget https://github.com/slimm609/checksec.sh/raw/master/checksec -O /usr/local/bin/checksec && \
    chmod +x /usr/local/bin/checksec && \
    gem install one_gadget

# Create non-root user and directories
RUN useradd -m -s /bin/bash pwn && \
    mkdir -p /workspace /app && \
    chown -R pwn:pwn /workspace /app

# Switch to the user to install user-specific tools like pwndbg
USER pwn
WORKDIR /home/pwn

RUN git clone --depth 1 https://github.com/pwndbg/pwndbg.git ./pwndbg && \
    cd ./pwndbg && \
    ./setup.sh

# Switch back to root for final preparations
USER root
WORKDIR /app

# Install Python dependencies
COPY --chown=pwn:pwn pyproject.toml ./
RUN uv venv && \
    uv pip install --system --no-cache -e .[dev]

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
      qemu-user-binfmt \
      # Runtime libraries for i386 binaries
      libc6:i386 libstdc++6:i386 libgcc-s1:i386 zlib1g:i386 lib32z1 \
      libssl3:i386 libncurses6:i386 libreadline8:i386 libtinfo6:i386 \
      # Debug symbols
      libc6-dbg libc6-dbg:i386 \
      # ═══ IoT 固件分析工具 ═══
      binwalk \
      squashfs-tools \
      mtd-utils \
      device-tree-compiler \
      u-boot-tools \
      cpio \
      # ═══ 多架构 QEMU (IoT 模拟) ═══
      qemu-system-arm \
      qemu-system-mips \
      qemu-user-static \
      # ═══ 额外工具 ═══
      strings \
      xxd \
      hexdump \
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
COPY --from=builder /usr/lib/gem/ /usr/lib/gem/
COPY --from=builder /var/lib/gems/ /var/lib/gems/

# Copy Rizin installation from builder
COPY --from=builder /usr/bin/rizin /usr/bin/rizin
COPY --from=builder /usr/lib/rizin /usr/lib/rizin

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

USER pwn
WORKDIR /app
VOLUME ["/workspace"]
EXPOSE 5500

CMD ["pwnmcp-server"]
