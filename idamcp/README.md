# IDA Pro MCP Bridge (kiki1e)

这是一个连接 IDA Pro 9.1 和 MCP (Claude/Cursor/Gemini) 的桥接工具。它让 AI 助手能够直接“读取”您在 IDA 中打开的二进制文件，查询伪代码、汇编和交叉引用。

## 📥 安装

1.  **安装 Python 依赖** (在项目目录下):
    ```bash
    pip install .
    ```

## 🚀 核心使用步骤 (必读)

要成功连接，必须严格遵守 **“先 IDA，后 AI”** 的顺序。

### 第一步：在 IDA Pro 中启动服务 (必须手动执行)
AI 无法自动启动 IDA，你必须手动开启数据服务：
1.  打开 **IDA Pro 9.1** 并加载您的目标文件。
2.  点击菜单栏 `File` -> `Script file...` (或按 `Alt + F7`)。
3.  选择本项目目录下的 `scripts/ida_server.py`。
4.  **验证**：IDA 底部的 Output 窗口必须显示：
    > `[IDA-MCP] Server started at http://127.0.0.1:4000`

### 第二步：配置 AI 助手

#### 方式 A: Cursor / Claude Desktop (修改配置文件)
找到您的 MCP 配置文件（通常位于 `%APPDATA%\Claude\claude_desktop_json` 或 Cursor 设置中），添加以下内容：

```json
{
  "mcpServers": {
    "ida_kiki": {
      "command": "python",
      "args": [
        "C:\\Users\\ds\\Desktop\\idamcp_kiki1e\\mcp_bridge.py"
      ]
    }
  }
}
```
*注意：请确保路径使用双反斜杠 `\\`，且路径指向您电脑上的实际位置。*

#### 方式 B: 命令行 AI (如 Gemini CLI)
直接运行桥接脚本即可，它会作为 MCP 服务器运行：
> "请运行 `python C:\Users\ds\Desktop\idamcp_kiki1e\mcp_bridge.py` 并帮我查询 main 函数的伪代码"

---

## ❓ 常见问题排查

### ❌ 报错: `MCP error -32000: Connection closed`
**原因**：AI 启动了 `mcp_bridge.py`，但它无法连接到 IDA Pro。
**解决**：
1.  检查 IDA Pro 是否已打开。
2.  **关键**：检查是否已在 IDA 中运行了 `scripts/ida_server.py`。
3.  检查 IDA Output 窗口是否有报错。

### ❌ 报错: `Function not found`
**原因**：IDA 尚未分析完毕，或函数名输入错误。
**解决**：
1.  等待 IDA 左下角的 "AU: idle" 出现（表示分析完成）。
2.  使用 `list_functions` 工具先查看可用的函数名。

---

## 🛠️ 可用工具列表

*   `check_connection`: 检查与 IDA 的连接状态。
*   `get_info`: 获取当前分析文件的架构信息 (x86/ARM/MIPS, 32/64bit)。
*   `list_functions`: 列出二进制中的所有函数名。
*   `get_pseudocode(target)`: **核心功能** - 获取 Hex-Rays 反编译的 C 伪代码。
*   `get_assembly(target)`: 获取函数的汇编指令。
*   `get_xrefs_to(target)`: 查看哪些地方调用了该函数 (交叉引用)。

## ⚠️ 前置要求
*   IDA Pro 9.x (推荐 9.1)
*   Hex-Rays Decompiler (用于伪代码功能)
*   Python 3.10+