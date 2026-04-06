"""
配置生成助手
用于生成 Claude Desktop 或 Cursor 的 MCP 配置文件内容
"""
import os
import sys
import json

def get_wsl_path():
    """获取当前目录在 WSL 中的绝对路径"""
    try:
        # 获取当前工作目录
        cwd = os.getcwd()
        return cwd
    except Exception as e:
        return f"/unknown/path ({e})"

def generate_config():
    wsl_path = get_wsl_path()
    
    config = {
        "mcpServers": {
            "pwnmcp": {
                "command": "wsl",
                "args": [
                    "bash",
                    "-c",
                    f"cd {wsl_path} && ./start.sh"
                ]
            }
        }
    }
    
    print("\n=== Claude Desktop / Cursor 配置 ===")
    print("请将以下内容复制到您的配置文件中：\n")
    print(json.dumps(config, indent=2))
    print("\n=====================================")
    print(f"当前 WSL 路径: {wsl_path}")

if __name__ == "__main__":
    generate_config()
