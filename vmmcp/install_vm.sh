#!/usr/bin/env bash
#
# PwnMCP Kiki1e - VM (Ubuntu 虚拟机) 专用安装脚本
# 基于 install.sh, 额外配置: 防火墙、网络、SSE 传输、systemd 服务
#

set -e

# --- 安装选项 ---
WITH_GHIDRA=false
WITH_ANGR=false
WITH_ALL=false

# --- 日志 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# --- 系统检测 ---

detect_system() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release; OS=$ID; VER=$VERSION_ID
        log_info "检测到系统: $PRETTY_NAME"
    else
        log_error "无法检测系统类型"; exit 1
    fi
    IS_WSL=false
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
        IS_WSL=true
        log_warning "检测到 WSL 环境。此脚本针对独立 VM 设计，WSL 请用 install.sh"
    fi
    log_info "VM 安装模式 (SSE/HTTP 传输)"
}

check_python() {
    log_info "检查 Python 环境..."
    if ! command_exists python3; then return 1; fi
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    log_success "检测到 Python $PYTHON_VERSION"
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        log_error "需要 Python 3.10+"; return 1
    fi
    return 0
}

ensure_env_file() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            log_info "从 .env.example 创建 .env..."
            cp .env.example .env
            # VM 默认使用 SSE 传输
            sed -i 's/TRANSPORT=stdio/TRANSPORT=sse/' .env 2>/dev/null || true
        fi
    fi
}

# --- 基础依赖 ---

install_system_deps() {
    log_info "安装系统基础依赖..."
    local PACKAGES=(
        "python3" "python3-venv" "python3-pip" "python3-dev"
        "git" "build-essential" "gcc-multilib" "g++-multilib" "libc6-dev-i386"
        "curl" "wget" "file" "binutils" "gdb" "gdb-multiarch" "patchelf"
        "ruby-full" "ruby-dev"
        "strace" "ltrace"
        # QEMU 多架构支持
        "qemu-user" "qemu-user-static" "qemu-user-binfmt"
    )
    if [ "$OS" != "ubuntu" ] && [ "$OS" != "debian" ]; then log_error "不支持的系统: $OS"; exit 1; fi

    local WAIT_COUNT=0
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
        if [ $WAIT_COUNT -eq 0 ]; then log_warning "等待包管理器..."; fi
        sleep 5; WAIT_COUNT=$((WAIT_COUNT + 1))
        if [ $WAIT_COUNT -gt 120 ]; then log_error "等待超时"; return 1; fi
    done
    sudo apt update

    local TO_INSTALL=()
    for pkg in "${PACKAGES[@]}"; do
        if ! dpkg -l | grep -q "^ii  $pkg "; then TO_INSTALL+=("$pkg"); fi
    done
    if [ ${#TO_INSTALL[@]} -gt 0 ]; then
        log_info "需要安装: ${TO_INSTALL[*]}"
        sudo apt install -y "${TO_INSTALL[@]}"
        log_success "系统依赖安装完成"
    else
        log_success "所有系统依赖已安装"
    fi

    # 32 位支持
    if ! dpkg --print-foreign-architectures | grep -q i386; then
        log_info "启用 32 位架构支持..."
        sudo dpkg --add-architecture i386; sudo apt update
        sudo apt install -y libc6:i386 libstdc++6:i386 libc6-dbg libc6-dbg:i386 2>/dev/null || true
    fi
}

install_pwndbg() {
    log_info "检查 pwndbg..."
    if command_exists pwndbg || [ -f ~/pwndbg/gdbinit.py ]; then log_success "pwndbg 已安装"; return 0; fi
    log_info "安装 pwndbg..."
    [ -d ~/pwndbg ] || git clone https://github.com/pwndbg/pwndbg ~/pwndbg
    cd ~/pwndbg && ./setup.sh
    if [ ! -f ~/.gdbinit ] || ! grep -q "pwndbg" ~/.gdbinit; then
        echo "source ~/pwndbg/gdbinit.py" >> ~/.gdbinit
    fi
    if ! command_exists pwndbg; then
        sudo tee /usr/local/bin/pwndbg > /dev/null << 'EOF'
#!/bin/bash
exec gdb -q -x ~/pwndbg/gdbinit.py "$@"
EOF
        sudo chmod +x /usr/local/bin/pwndbg
    fi
    cd - > /dev/null; log_success "pwndbg 安装完成"
}

install_rizin() {
    if command_exists rizin; then log_success "Rizin 已安装"; return 0; fi
    log_info "安装 Rizin..."
    sudo apt install -y rizin 2>/dev/null || {
        wget -q "https://github.com/rizinorg/rizin/releases/download/v0.7.3/rizin_0.7.3_amd64.deb" -O /tmp/rizin.deb
        sudo dpkg -i /tmp/rizin.deb; rm -f /tmp/rizin.deb
    }
    log_success "Rizin 安装完成"
}

install_pwn_tools() {
    log_info "安装核心 PWN 工具..."
    command_exists one_gadget || { log_info "安装 one_gadget..."; sudo gem install one_gadget; }
    command_exists checksec || { log_info "安装 checksec..."; sudo wget -q https://github.com/slimm609/checksec.sh/raw/master/checksec -O /usr/local/bin/checksec && sudo chmod +x /usr/local/bin/checksec; }
    command_exists seccomp-tools || { log_info "安装 seccomp-tools..."; sudo gem install seccomp-tools; }
    command_exists pwninit || { log_info "安装 pwninit..."; wget -q "https://github.com/io12/pwninit/releases/download/3.3.1/pwninit" -O /tmp/pwninit && sudo mv /tmp/pwninit /usr/local/bin/pwninit && sudo chmod +x /usr/local/bin/pwninit; }
    log_success "核心 PWN 工具安装完成"
}

# ═══════════════════════════════════════════════
# 逆向工程工具
# ═══════════════════════════════════════════════

install_reverse_tools() {
    log_info "========== 安装逆向工程工具 =========="

    # radare2
    if command_exists r2; then
        log_success "radare2 已安装"
    else
        log_info "安装 radare2..."
        sudo apt install -y radare2 2>/dev/null || {
            git clone --depth 1 https://github.com/radareorg/radare2 /tmp/radare2
            cd /tmp/radare2 && sys/install.sh && cd - > /dev/null && rm -rf /tmp/radare2
        }
        log_success "radare2 安装完成"
    fi

    # binwalk
    command_exists binwalk || { sudo apt install -y binwalk; }
    log_success "binwalk 已安装"

    # firmware-mod-kit
    if [ ! -d /opt/firmware-mod-kit ]; then
        log_info "安装 firmware-mod-kit..."
        sudo apt install -y squashfs-tools mtd-utils device-tree-compiler u-boot-tools cpio zlib1g-dev liblzma-dev liblzo2-dev 2>/dev/null
        sudo git clone --depth 1 https://github.com/rampageX/firmware-mod-kit /opt/firmware-mod-kit 2>/dev/null || true
    fi
    log_success "固件分析工具安装完成"

    # Ghidra (可选)
    if [ "$WITH_GHIDRA" = true ] || [ "$WITH_ALL" = true ]; then
        if [ -d /opt/ghidra ]; then log_success "Ghidra 已安装"; else
            log_info "安装 Ghidra headless..."
            sudo apt install -y openjdk-17-jdk-headless 2>/dev/null || sudo apt install -y openjdk-17-jre-headless
            local GHIDRA_VERSION="11.2.1"
            local GHIDRA_DATE="20241105"
            wget -q --show-progress "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_DATE}.zip" -O /tmp/ghidra.zip
            sudo unzip -q /tmp/ghidra.zip -d /opt/
            sudo mv /opt/ghidra_${GHIDRA_VERSION}_PUBLIC /opt/ghidra
            sudo chmod +x /opt/ghidra/support/analyzeHeadless
            rm -f /tmp/ghidra.zip
            grep -q "GHIDRA_HOME" ~/.bashrc 2>/dev/null || echo 'export GHIDRA_HOME=/opt/ghidra' >> ~/.bashrc
            log_success "Ghidra 安装完成"
        fi
    else
        log_info "跳过 Ghidra (使用 --with-ghidra 安装)"
    fi
}

# ═══════════════════════════════════════════════
# 密码学工具
# ═══════════════════════════════════════════════

install_crypto_tools() {
    log_info "========== 安装密码学工具 =========="
    sudo apt install -y libgmp-dev libmpfr-dev libmpc-dev 2>/dev/null
    command_exists hashcat || { sudo apt install -y hashcat; }
    command_exists john || { sudo apt install -y john; }

    # rockyou.txt
    if [ ! -f /usr/share/wordlists/rockyou.txt ]; then
        sudo mkdir -p /usr/share/wordlists
        if [ -f /usr/share/wordlists/rockyou.txt.gz ]; then
            sudo gzip -d /usr/share/wordlists/rockyou.txt.gz
        else
            sudo wget -q "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt" \
                -O /usr/share/wordlists/rockyou.txt 2>/dev/null || true
        fi
    fi
    log_success "密码学工具安装完成"
}

# ═══════════════════════════════════════════════
# 二进制漏洞利用增强
# ═══════════════════════════════════════════════

install_binary_exploit_tools() {
    log_info "========== 安装二进制漏洞利用工具 =========="
    if [ "$WITH_ANGR" = true ] || [ "$WITH_ALL" = true ]; then
        log_info "安装 angr (约 1GB)..."
        source .venv/bin/activate
        pip install angr && log_success "angr 安装完成" || log_error "angr 安装失败"
    else
        log_info "跳过 angr (使用 --with-angr 安装)"
    fi
}

# ═══════════════════════════════════════════════
# VM 专有: 网络/防火墙/systemd
# ═══════════════════════════════════════════════

configure_vm_network() {
    log_info "========== 配置 VM 网络 =========="
    local MCP_PORT=${MCP_PORT:-5500}

    # 防火墙
    if command_exists ufw; then
        log_info "配置 UFW 防火墙..."
        sudo ufw allow $MCP_PORT/tcp comment "PwnMCP SSE" 2>/dev/null || true
        log_success "已允许端口 $MCP_PORT (UFW)"
    elif command_exists firewall-cmd; then
        sudo firewall-cmd --permanent --add-port=$MCP_PORT/tcp 2>/dev/null || true
        sudo firewall-cmd --reload 2>/dev/null || true
        log_success "已允许端口 $MCP_PORT (firewalld)"
    else
        log_warning "未检测到防火墙工具，请手动确保端口 $MCP_PORT 可访问"
    fi

    # 显示 IP 地址
    local VM_IP=$(hostname -I | awk '{print $1}')
    log_success "VM IP 地址: $VM_IP"
    log_info "MCP SSE 端点: http://$VM_IP:$MCP_PORT/sse"
}

create_systemd_service() {
    log_info "创建 systemd 服务文件 (可选, 开机自启)..."
    local INSTALL_DIR=$(pwd)
    local CURRENT_USER=$(whoami)

    sudo tee /etc/systemd/system/pwnmcp.service > /dev/null << SVCEOF
[Unit]
Description=PwnMCP Kiki1e - Binary Analysis MCP Server
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python -u -m pwnmcp --transport sse --host 0.0.0.0 --port 5500
Restart=on-failure
RestartSec=5
Environment=TRANSPORT=sse
Environment=GHIDRA_HOME=/opt/ghidra

[Install]
WantedBy=multi-user.target
SVCEOF

    log_success "systemd 服务文件已创建: /etc/systemd/system/pwnmcp.service"
    echo "  启用: sudo systemctl enable pwnmcp"
    echo "  启动: sudo systemctl start pwnmcp"
    echo "  状态: sudo systemctl status pwnmcp"
    echo "  日志: journalctl -u pwnmcp -f"
}

# --- Python / 项目 ---

create_venv() {
    if [ "$1" != "force" ] && [ -d .venv ]; then log_info "虚拟环境已存在"; return 0; fi
    log_info "创建 Python 虚拟环境..."
    python3 -m venv .venv
    log_success "虚拟环境创建完成"
}

install_python_deps() {
    log_info "安装 Python 依赖..."
    source .venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -e .
    log_success "Python 依赖安装完成"
}

configure_ptrace() {
    local PTRACE_SCOPE=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null || echo "0")
    if [ "$PTRACE_SCOPE" != "0" ]; then
        log_info "配置 ptrace 权限..."
        sudo sysctl -w kernel.yama.ptrace_scope=0
        echo "kernel.yama.ptrace_scope = 0" | sudo tee /etc/sysctl.d/10-ptrace.conf > /dev/null
        log_success "ptrace 权限配置完成"
    fi
}

create_workspace() {
    mkdir -p workspace 2>/dev/null || true
}

generate_start_sse_script() {
    log_info "生成 SSE 启动脚本..."
    cat > start_sse.sh << 'EOF'
#!/usr/bin/env bash
# PwnMCP Kiki1e - SSE/HTTP 启动脚本 (VM 专用)
set -e
cd "$(dirname "$0")"

if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "❌ 虚拟环境不存在，请先运行 ./install_vm.sh" >&2
    exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${MCP_PORT:-5500}"

# 构建参数
ARGS="--transport sse --host $HOST --port $PORT"
while [[ $# -gt 0 ]]; do
    case $1 in
        --enable-ghidra) ARGS="$ARGS --enable-ghidra"; shift;;
        --enable-angr) ARGS="$ARGS --enable-angr"; shift;;
        --deep-static) ARGS="$ARGS --deep-static"; shift;;
        --log-level) ARGS="$ARGS --log-level $2"; shift 2;;
        *) ARGS="$ARGS $1"; shift;;
    esac
done

echo "🚀 PwnMCP SSE 模式启动: http://$HOST:$PORT/sse" >&2
python -u -m pwnmcp $ARGS
EOF
    chmod +x start_sse.sh
    log_success "SSE 启动脚本创建完成: ./start_sse.sh"
}

test_installation() {
    log_info "测试安装..."
    source .venv/bin/activate
    python3 -c "import pwnmcp; print(f'pwnmcp loaded')" 2>/dev/null && log_success "pwnmcp 模块正常" || log_error "pwnmcp 导入失败"
}

show_summary() {
    local VM_IP=$(hostname -I | awk '{print $1}')
    local MCP_PORT=${MCP_PORT:-5500}
    echo
    echo "=========================================="
    log_success "VM 安装完成！"
    echo "=========================================="
    echo
    echo "🌐 VM 连接信息:"
    echo "  IP 地址: $VM_IP"
    echo "  MCP 端点: http://$VM_IP:$MCP_PORT/sse"
    echo
    echo "🚀 启动方式:"
    echo "  ./start_sse.sh                        # SSE 模式 (推荐)"
    echo "  ./start_sse.sh --enable-ghidra        # 启用 Ghidra"
    echo "  ./start_sse.sh --enable-angr          # 启用 angr"
    echo "  sudo systemctl start pwnmcp           # systemd 服务"
    echo
    echo "📋 Claude Desktop / Cursor MCP 配置:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "binary_pwn": {'
    echo "        \"url\": \"http://$VM_IP:$MCP_PORT/sse\""
    echo '      }'
    echo '    }'
    echo '  }'
    echo
}

# --- 主逻辑 ---

main_install() {
    echo "=========================================="
    echo "  PwnMCP Kiki1e VM 安装脚本"
    echo "  (逆向 + 密码 + 二进制 + 网络配置)"
    echo "=========================================="
    echo
    detect_system; ensure_env_file

    if ! check_python; then install_system_deps; fi

    if [ ! -f "pyproject.toml" ]; then log_error "请在项目根目录运行此脚本"; exit 1; fi

    install_system_deps
    install_pwndbg
    install_rizin
    install_pwn_tools
    install_reverse_tools
    install_crypto_tools
    create_venv
    install_python_deps
    install_binary_exploit_tools
    configure_ptrace
    create_workspace
    configure_vm_network
    generate_start_sse_script
    create_systemd_service
    test_installation
    show_summary
}

# --- 入口 ---

trap 'log_error "安装过程中发生错误"; exit 1' ERR

for arg in "$@"; do
    case $arg in
        --with-ghidra) WITH_GHIDRA=true ;;
        --with-angr)   WITH_ANGR=true ;;
        --with-all)    WITH_ALL=true ;;
        --help|-h)
            echo "用法: ./install_vm.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --with-ghidra  安装 Ghidra headless (约 700MB)"
            echo "  --with-angr    安装 angr 符号执行 (约 1GB)"
            echo "  --with-all     安装所有可选组件"
            exit 0
            ;;
    esac
done

main_install
