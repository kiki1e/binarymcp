import requests
from mcp.server.fastmcp import FastMCP

# 配置
IDA_HOST = "http://127.0.0.1:4000"

mcp = FastMCP("IDA Pro Bridge")

def _request(endpoint, payload=None):
    try:
        url = f"{IDA_HOST}{endpoint}"
        if payload:
            response = requests.post(url, json=payload, timeout=10)
        else:
            response = requests.post(url, json={}, timeout=10)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "无法连接到 IDA Pro。请确保 IDA 已打开，并加载了 scripts/ida_server.py 脚本。"}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def check_connection() -> str:
    """检查是否已连接到 IDA Pro 实例"""
    return str(_request("/ping"))

@mcp.tool()
def get_info() -> str:
    """获取当前打开文件的基本信息（架构、编译器等）"""
    return str(_request("/info"))

@mcp.tool()
def list_functions() -> str:
    """列出当前二进制文件中的所有函数（返回前100个以避免过大）"""
    res = _request("/functions")
    if "functions" in res and len(res["functions"]) > 100:
        res["note"] = "Showing first 100 functions only"
        res["functions"] = res["functions"][:100]
    return str(res)

@mcp.tool()
def get_pseudocode(function_name_or_address: str) -> str:
    """
    获取指定函数的 C 伪代码（反编译结果）。
    参数可以是函数名（如 'main'）或十六进制地址（如 '0x401000'）。
    """
    return str(_request("/decompile", {"target": function_name_or_address}))

@mcp.tool()
def get_assembly(function_name_or_address: str) -> str:
    """
    获取指定函数的汇编代码。
    参数可以是函数名（如 'main'）或十六进制地址。
    """
    return str(_request("/disassemble", {"target": function_name_or_address}))

@mcp.tool()
def get_xrefs_to(address_or_name: str) -> str:
    """
    获取指向该地址的交叉引用（谁调用了它？）。
    """
    return str(_request("/xrefs", {"target": address_or_name}))

def main():
    print("启动 IDA MCP Bridge...")
    print("请确保 IDA Pro 已运行并加载了插件。")
    mcp.run()

if __name__ == "__main__":
    main()
