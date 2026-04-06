"""
PwnMCP Kiki1e - 统一的 PWN MCP 服务器

整合了以下项目的功能:
- pwn-mcp: 静态分析、漏洞利用策略规划
- pwndbg-MCP_for_WSL: GDB/pwndbg 交互式调试
- pwno-mcp: 完整的 GDB Machine Interface 控制

支持 Docker 和 WSL 部署
"""

__version__ = "1.0.0"
__author__ = "kiki1e"

from pwnmcp.core.exceptions import PwnMcpError

__all__ = ["PwnMcpError", "__version__"]
