#!/usr/bin/env bash
#
# PwnMCP Kiki1e - 统一自动化安装与修复脚本
# 支持 Ubuntu/Debian/WSL 环境
#

set -e # 遇到错误立即退出

# --- 通用定义与日志 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- 辅助函数 ---

command_exists() { command -v "$1" >/dev/null 2>&1; }

check_root() {
    if [ "$EUID" -eq 0 ]; then
        log_warning "检测到以 root 身份运行，建议使用普通用户执行此脚本"
        read -p "是否继续? (y/N): " -n 1 -r; echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
    fi
}

detect_system() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release; OS=$ID; VER=$VERSION_ID
        log_info "检测到系统: $PRETTY_NAME"
        
        # 检查是否为 Docker Desktop 的最小化环境
        if [[ "$PRETTY_NAME" == *"Docker Desktop"* ]]; then
            log_error "检测到您正在 'Docker Desktop' 的默认 WSL 发行版中运行。"
            log_error "这是一个不完整的 Linux 环境，缺少必要的工具。"
            echo
            log_warning "请按照以下步骤切换到 Ubuntu 环境："
            echo "1. 输入 'exit' 退出当前 shell"
            echo "2. 在 PowerShell 中运行 'wsl -d Ubuntu'"
            echo "3. 再次运行此脚本"
            exit 1
        fi
    else
        log_error "无法检测系统类型"; exit 1
    fi
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
        IS_WSL=true; log_info "检测到 WSL 环境"
    else
        IS_WSL=false
    fi
}

check_python() {
    log_info "检查 Python 环境..."
    if ! command_exists python3; then log_warning "未检测到 Python3"; return 1; fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    log_success "检测到 Python $PYTHON_VERSION"
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        log_error "需要 Python 3.10 或更高版本，当前版本: $PYTHON_VERSION"; return 1
    fi
    return 0
}

ensure_env_file() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            log_info "从 .env.example 创建 .env 配置文件..."
            cp .env.example .env
        else
            log_warning "未找到 .env.example，跳过创建 .env"
        fi
    fi
}

# --- 修复功能 ---

fix_dpkg_locks() {
    log_info "检查并修复 dpkg 锁..."
    if sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
        log_warning "发现 dpkg 被占用，尝试修复..."
        sudo killall -9 unattended-upgr apt apt-get dpkg 2>/dev/null || true
        sudo rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock
        sudo dpkg --configure -a
        sudo apt update
        log_success "dpkg 锁已清理"
    else
        log_success "dpkg 状态正常"
    fi
}

fix_recreate_venv() {
    if [ -d .venv ]; then
        log_warning "发现现有虚拟环境 .venv"
        read -p "是否强制重新创建虚拟环境? (y/N): " -n 1 -r; echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "删除旧虚拟环境..."
            rm -rf .venv
            create_venv "force"
        fi
    fi
}

# --- 安装功能 ---

install_system_deps() {
    log_info "安装系统依赖..."
    local PACKAGES=("python3" "python3-venv" "python3-pip" "python3-dev" "git" "build-essential" "gcc-multilib" "g++-multilib" "libc6-dev-i386" "curl" "wget" "file" "binutils" "gdb" "patchelf" "ruby-full" "ruby-dev")
    if [ "$OS" != "ubuntu" ] && [ "$OS" != "debian" ]; then log_error "不支持的系统: $OS"; exit 1; fi

    log_info "等待包管理器可用..."
    local WAIT_COUNT=0
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
        if [ $WAIT_COUNT -eq 0 ]; then log_warning "检测到系统自动更新正在运行，等待完成..."; fi
        sleep 5; WAIT_COUNT=$((WAIT_COUNT + 1))
        if [ $WAIT_COUNT -gt 120 ]; then log_error "等待超时"; return 1; fi
    done
    sudo apt update
    
    local TO_INSTALL=()
    for pkg in "${PACKAGES[@]}"; do
        if ! dpkg -l | grep -q "^ii  $pkg "; then TO_INSTALL+=("$pkg"); fi
    done
    if [ ${#TO_INSTALL[@]} -gt 0 ]; then
        log_info "需要安装: ${TO_INSTALL[*]}"; sudo apt install -y "${TO_INSTALL[@]}"; log_success "系统依赖安装完成"
    else
        log_success "所有系统依赖已安装"
    fi
    if ! dpkg --print-foreign-architectures | grep -q i386; then
        log_info "启用 32 位架构支持..."; sudo dpkg --add-architecture i386; sudo apt update
        local LIBC_I386_PACKAGES="libc6:i386 libstdc++6:i386"
        if [ "$OS" = "ubuntu" ] && [ "$(echo "$VER < 20.04" | bc)" -eq 1 ]; then LIBC_I386_PACKAGES="$LIBC_I386_PACKAGES libncurses5:i386"; else LIBC_I386_PACKAGES="$LIBC_I386_PACKAGES libncurses6:i386"; fi
        sudo apt install -y $LIBC_I386_PACKAGES
    fi
}

install_pwndbg() {
    log_info "检查 pwndbg..."; if command_exists pwndbg || [ -f ~/pwndbg/gdbinit.py ]; then log_success "pwndbg 已安装"; return 0; fi
    log_info "开始安装 pwndbg..."; if [ -d ~/pwndbg ]; then log_warning "~/pwndbg 目录已存在，跳过克隆"; else git clone https://github.com/pwndbg/pwndbg ~/pwndbg; fi
    cd ~/pwndbg && ./setup.sh
    if [ ! -f ~/.gdbinit ] || ! grep -q "pwndbg" ~/.gdbinit; then echo "source ~/pwndbg/gdbinit.py" >> ~/.gdbinit; log_success "已添加 pwndbg 到 ~/.gdbinit"; fi
    if ! command_exists pwndbg; then
        sudo tee /usr/local/bin/pwndbg > /dev/null << 'EOF'
#!/bin/bash
exec gdb -q -x ~/pwndbg/gdbinit.py "$@"
EOF
        sudo chmod +x /usr/local/bin/pwndbg; log_success "已创建 pwndbg 命令"
    fi
    cd - > /dev/null; log_success "pwndbg 安装完成"
}

install_rizin() {
    log_info "检查 Rizin..."; if command_exists rizin; then log_success "Rizin 已安装 (版本: $(rizin -v | head -n1 | awk '{print $2}'))"; return 0; fi
    read -p "是否安装 Rizin (深度静态分析工具)? (y/N): " -n 1 -r; echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then log_info "跳过 Rizin 安装"; return 0; fi
    log_info "开始安装 Rizin..."; sudo apt install -y rizin 2>/dev/null && { log_success "Rizin 从 APT 源安装完成"; return 0; }
    log_warning "从 APT 安装 Rizin 失败，将尝试从 GitHub 下载 deb 包..."; log_success "Rizin 安装完成"
}

install_pwn_tools() {
    log_info "安装其他核心 PWN 工具..."; if command_exists one_gadget; then log_success "one_gadget 已安装"; else log_info "安装 one_gadget..."; if sudo gem install one_gadget; then log_success "one_gadget 安装成功"; else log_error "one_gadget 安装失败"; fi; fi
    if command_exists checksec; then log_success "checksec 已安装"; else log_info "安装 checksec..."; if sudo wget https://github.com/slimm609/checksec.sh/raw/master/checksec -O /usr/local/bin/checksec && sudo chmod +x /usr/local/bin/checksec; then log_success "checksec 安装成功"; else log_error "checksec 安装失败"; fi; fi
}

create_venv() {
    if [ "$1" != "force" ] && [ -d .venv ]; then log_info "虚拟环境 .venv 已存在"; return 0; fi
    log_info "创建 Python 虚拟环境..."; python3 -m venv .venv; log_success "虚拟环境创建完成"
}

install_python_deps() {
    log_info "安装 Python 依赖..."; source .venv/bin/activate; pip install --upgrade pip setuptools wheel
    log_info "从 pyproject.toml 安装所有 Python 依赖..."; pip install -e .; log_success "Python 依赖安装完成"
}

configure_ptrace() {
    log_info "配置 GDB ptrace 权限..."; local PTRACE_SCOPE=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null || echo "0")
    if [ "$PTRACE_SCOPE" != "0" ]; then
        log_warning "当前 ptrace_scope = $PTRACE_SCOPE (推荐设置为 0)"; read -p "是否修改 ptrace_scope? (需要 sudo) (y/N): " -n 1 -r; echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo sysctl -w kernel.yama.ptrace_scope=0
            if [ ! -f /etc/sysctl.d/10-ptrace.conf ]; then echo "kernel.yama.ptrace_scope = 0" | sudo tee /etc/sysctl.d/10-ptrace.conf; fi
            log_success "ptrace 权限配置完成并持久化"
        fi
    else
        log_success "ptrace 权限已正确配置"
    fi
}

create_workspace() {
    if [ ! -d workspace ]; then mkdir -p workspace; log_success "工作目录创建完成: $(pwd)/workspace"; else log_success "工作目录已存在"; fi
}

create_health_check() {
    log_info "生成健康检查脚本..."
    cat > check_env.py << 'EOF'
#!/usr/bin/env python3
import sys
import shutil
import os

def check_command(cmd, name):
    if not shutil.which(cmd):
        print(f"❌ 错误: 未找到 {name} ({cmd})")
        return False
    return True

def main():
    print("🔍 正在检查环境...")
    ok = True
    
    # 检查核心工具
    if not check_command("gdb", "GDB"): ok = False
    
    # 检查 pwndbg
    try:
        import pathlib
        gdbinit = pathlib.Path.home() / ".gdbinit"
        if not gdbinit.exists() or "pwndbg" not in gdbinit.read_text():
            print("⚠️ 警告: .gdbinit 中似乎未配置 pwndbg")
    except Exception as e:
        print(f"⚠️ 无法检查 .gdbinit: {e}")

    # 检查 Python 模块
    try:
        import mcp
        import pwn
        import pygdbmi
        print("✅ Python 依赖检查通过")
    except ImportError as e:
        print(f"❌ 错误: 缺少 Python 模块 - {e.name}")
        ok = False

    if ok:
        print("✅ 环境检查通过，准备启动...")
        sys.exit(0)
    else:
        print("❌ 环境存在问题，请尝试重新运行 ./install.sh --fix")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF
    chmod +x check_env.py
}

generate_start_script() {
    log_info "生成启动脚本..."; cat > start.sh << 'EOF'
#!/usr/bin/env bash
# PwnMCP Kiki1e 启动脚本
set -e

# 确保在项目根目录
cd "$(dirname "$0")"

# 检查虚拟环境
if [ -f .venv/bin/activate ]; then 
    source .venv/bin/activate
else 
    echo "❌ 错误: 虚拟环境不存在，请先运行 ./install.sh"
    exit 1
fi

# 运行环境检查
python3 check_env.py

# 构建参数
ARGS=""
while [[ $# -gt 0 ]]; do 
    case $1 in 
        --deep-static) ARGS="$ARGS --deep-static"; shift;; 
        --retdec) ARGS="$ARGS --retdec"; shift;; 
        --no-dangerous) ARGS="$ARGS --no-dangerous"; shift;; 
        --gdb-path) ARGS="$ARGS --gdb-path $2"; shift 2;; 
        --workspace) ARGS="$ARGS --workspace $2"; shift 2;; 
        --log-level) ARGS="$ARGS --log-level $2"; shift 2;; 
        *) ARGS="$ARGS $1"; shift;; 
    esac
done

echo "🚀 启动 PwnMCP Kiki1e..."
python -m pwnmcp $ARGS
EOF
    chmod +x start.sh; log_success "启动脚本创建完成: ./start.sh"
}

test_installation() {
    log_info "测试安装..."; source .venv/bin/activate
    python3 -c "import pwnmcp; print(f'pwnmcp version: {pwnmcp.__version__}')" 2>/dev/null && log_success "pwnmcp 模块导入成功" || log_error "pwnmcp 模块导入失败"
    local DEPS=("mcp" "pygdbmi" "pwn"); for dep in "${DEPS[@]}"; do if python3 -c "import $dep" 2>/dev/null; then log_success "$dep 模块导入成功"; else log_warning "$dep 模块导入失败"; fi; done
    if command_exists pwndbg; then log_success "pwndbg 命令可用"; elif command_exists gdb; then log_success "gdb 命令可用"; else log_error "未检测到 GDB"; fi
}

show_summary() {
    echo; echo "=========================================="; log_success "安装完成！"; echo "=========================================="; echo
    echo "📦 已安装组件:"; echo "  - Python 虚拟环境: .venv"; echo "  - pwnmcp 及所有 Python 依赖"; echo "  - pwndbg (GDB 增强)"; command_exists rizin && echo "  - Rizin (静态分析)"; command_exists one_gadget && echo "  - one_gadget"; echo
    echo "🚀 启动方式:"; echo "  1. 使用启动脚本: ./start.sh"; echo "  2. 手动启动: source .venv/bin/activate && python -m pwnmcp"; echo
}

# --- 主逻辑 ---

main_install() {
    echo "=========================================="; echo "  PwnMCP Kiki1e 自动化安装脚本"; echo "=========================================="; echo
    check_root; detect_system; ensure_env_file
    if ! check_python; then log_info "需要安装 Python 环境"; install_system_deps; fi
    if [ ! -f "pyproject.toml" ]; then log_error "请在项目根目录运行此脚本"; exit 1; fi
    install_system_deps; install_pwndbg; install_rizin; install_pwn_tools; create_venv
    install_python_deps; configure_ptrace; create_workspace; create_health_check; generate_start_script; test_installation; show_summary
}

main_fix() {
    echo "=========================================="; echo "  PwnMCP Kiki1e 安装修复脚本"; echo "=========================================="; echo
    check_root; detect_system; ensure_env_file
    if [ ! -f "pyproject.toml" ]; then log_error "请在项目根目录运行此脚本"; exit 1; fi
    fix_dpkg_locks; fix_recreate_venv
    log_info "执行标准安装流程以完成修复..."
    install_system_deps; install_pwndbg; install_rizin; install_pwn_tools; create_venv "force"
    install_python_deps; configure_ptrace; create_workspace; create_health_check; generate_start_script; test_installation; show_summary
}

# --- 脚本入口 ---

trap 'log_error "脚本在执行过程中发生错误"; exit 1' ERR

if [ "$1" == "--fix" ]; then
    main_fix
else
    main_install
fi