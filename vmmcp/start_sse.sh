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
        --no-dangerous) ARGS="$ARGS --allow-dangerous false"; shift;;
        --log-level) ARGS="$ARGS --log-level $2"; shift 2;;
        --port) PORT="$2"; ARGS="--transport sse --host $HOST --port $PORT"; shift 2;;
        *) ARGS="$ARGS $1"; shift;;
    esac
done

echo "🚀 PwnMCP SSE 模式启动: http://$HOST:$PORT/sse" >&2
python -u -m pwnmcp $ARGS
