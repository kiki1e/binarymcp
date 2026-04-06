"""主服务器入口"""

import argparse
import os
from dotenv import load_dotenv
from pwnmcp.server import run_server

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="PwnMCP Kiki1e Server")
    
    # 将字符串 'true'/'false' 转换为布尔值
    def str_to_bool(value):
        if isinstance(value, bool):
            return value
        if value.lower() in ('true', '1'):
            return True
        elif value.lower() in ('false', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    # 使用 getenv 读取环境变量，并提供回退的默认值
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="服务器主机地址")
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", 5500)), help="MCP 服务端口")
    parser.add_argument("--transport", default=os.getenv("TRANSPORT", "stdio"), choices=["stdio", "sse"], help="传输方式: stdio (本地) 或 sse (HTTP/Docker)")
    parser.add_argument("--attach-port", type=int, default=int(os.getenv("API_PORT", 5501)), help="附加 API 端口")
    parser.add_argument("--workspace", default=os.getenv("WORKSPACE_DIR", "./workspace"), help="工作区目录")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--gdb-path", default=os.getenv("GDB_PATH"), help="指定 GDB/Pwndbg 可执行文件路径")
    
    # 布尔类型的参数处理
    parser.add_argument("--deep-static", dest="deep_static", type=str_to_bool, nargs='?', const=True, 
                        default=str_to_bool(os.getenv("ENABLE_DEEP_STATIC", 'true')),
                        help="启用深度静态分析 (Rizin)")
    parser.add_argument("--retdec", dest="retdec", type=str_to_bool, nargs='?', const=True,
                        default=str_to_bool(os.getenv("ENABLE_RETDEC", 'false')),
                        help="启用 RetDec 反编译工具")
    parser.add_argument("--enable-ghidra", dest="ghidra", type=str_to_bool, nargs='?', const=True,
                        default=str_to_bool(os.getenv("ENABLE_GHIDRA", 'false')),
                        help="启用 Ghidra headless 反编译 (需要安装 Ghidra + JDK17)")
    parser.add_argument("--enable-angr", dest="angr", type=str_to_bool, nargs='?', const=True,
                        default=str_to_bool(os.getenv("ENABLE_ANGR", 'false')),
                        help="启用 angr 符号执行引擎 (需要安装 angr, ~1GB)")
    parser.add_argument("--allow-dangerous", dest="dangerous", type=str_to_bool, nargs='?', const=True,
                        default=str_to_bool(os.getenv("ALLOW_DANGEROUS", 'true')),
                        help="允许执行高危命令")

    args = parser.parse_args()

    # 将 transport 写入环境变量，供 run_server 内部读取
    os.environ["TRANSPORT"] = args.transport

    run_server(
        host=args.host,
        port=args.port,
        attach_port=args.attach_port,
        workspace=args.workspace,
        log_level=args.log_level,
        enable_deep_static=args.deep_static,
        enable_retdec=args.retdec,
        enable_ghidra=args.ghidra,
        enable_angr=args.angr,
        gdb_path=args.gdb_path,
        allow_dangerous=args.dangerous,
    )

if __name__ == "__main__":
    main()
