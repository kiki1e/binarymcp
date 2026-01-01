# BinaryMCP

`BinaryMCP` 是一个功能强大的二进制分析与漏洞利用辅助工具集，基于 **Model Context Protocol (MCP)** 构建。它旨在为大型语言模型（如 Claude, Cursor, Gemini）提供直接操作逆向工程工具（IDA Pro）和动态调试工具（GDB/pwndbg）的能力，从而实现 AI 驱动的自动化二进制分析。

本项目由两个核心模块组成：
- **idamcp**: 连接 IDA Pro 与 AI 助手的桥接工具，实现伪代码查询、函数列表获取及静态分析。
- **pwnmcp**: 专为 CTF PWN 设计的调试与分析服务器，集成了 GDB/pwndbg、静态分析及多种漏洞利用工具。

---

## 📁 项目结构

```text
binarymcp/
├── idamcp/           # IDA Pro MCP 桥接工具
│   ├── scripts/      # IDA 服务端脚本 (ida_server.py)
│   ├── mcp_bridge.py # MCP 桥接入口
│   └── README.md     # idamcp 详细文档
└── pwnmcp/           # Pwn 分析与调试服务器 (推荐在 WSL/Docker 运行)
    ├── pwnmcp/       # 核心源码
    ├── install.sh    # 自动化安装脚本
    ├── start.sh      # 启动脚本
    └── README.md     # pwnmcp 详细文档
```

---

## 🚀 快速开始

### 1. 安装依赖

确保您的环境中已安装 Python 3.10+。

```bash
# 进入项目目录
cd binarymcp

# 安装 idamcp 依赖
cd idamcp
pip install .

# 安装 pwnmcp 依赖 (建议在 WSL 中执行)
cd ../pwnmcp
chmod +x install.sh
./install.sh
```

### 2. 启动服务

#### IDA 静态分析 (idamcp)
1. **在 IDA Pro 中**: 手动运行 `idamcp/scripts/ida_server.py`。
2. **在终端中**: 运行 `python idamcp/mcp_bridge.py` 或将其配置到您的 AI 客户端。

#### 动态调试 (pwnmcp)
1. **在 WSL 中**: 运行 `./pwnmcp/start.sh`。

---

## 🔌 AI 客户端配置 (MCP)

### Claude Desktop / Cursor
在您的 MCP 配置文件中添加以下服务器配置：

```json
{
  "mcpServers": {
    "binary_ida": {
      "command": "python",
      "args": ["C:/Users/ds/Desktop/binarymcp/idamcp/mcp_bridge.py"]
    },
    "binary_pwn": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd /mnt/c/Users/ds/Desktop/binarymcp/pwnmcp && ./start.sh"
      ]
    }
  }
}
```

---

## 🛠️ 核心功能

### 🔍 静态分析 (IDA)
- **获取伪代码**: AI 可以直接读取 Hex-Rays 生成的 C 代码。
- **交叉引用**: 自动分析函数调用链。
- **函数列表**: 快速概览二进制结构。

### 🐞 动态调试 (Pwn)
- **GDB 集成**: 实时获取寄存器、内存和栈信息。
- **偏移计算**: 自动处理缓冲区溢出偏移。
- **工具链集成**: 内置 `checksec`, `ROPgadget`, `one_gadget` 等。
- **策略生成**: 根据分析结果建议漏洞利用思路。

---

## 📄 许可证
本项目基于 MIT 许可证。
