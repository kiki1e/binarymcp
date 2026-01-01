#!/usr/bin/env bash
# PwnMCP Kiki1e 启动脚本
set -e

# 确保在项目根目录
cd "$(dirname "$0")"

# 检查虚拟环境
if [ -f .venv/bin/activate ]; then 
    source .venv/bin/activate
else 
    echo "❌ 错误: 虚拟环境不存在，请先运行 ./install.sh" >&2
    exit 1
fi

# 运行环境检查 (输出重定向到 stderr)
# 为加快启动速度防止超时，暂时注释掉检查
# python3 check_env.py >&2

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

echo "🚀 启动 PwnMCP Kiki1e..." >&2
# 使用 -u 禁用缓冲，确保及时通信
python -u -m pwnmcp $ARGS
