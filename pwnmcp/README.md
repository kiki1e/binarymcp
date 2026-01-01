# PwnMCP Kiki1e

`PwnMCP Kiki1e` 是一个专为 CTF PWN 解题流程设计的模型上下文协议（MCP）服务器。它将静态分析、动态执行与 `pwndbg` 交互式调试功能封装为一套强大的 API，旨在为大型语言模型（LLM）提供一个高效的后端，使其能够作为专业的 AI 逆向与漏洞利用助手。

该项目融合了 `pwn-mcp`、`pwndbg-MCP_for_WSL` 和 `pwno-mcp` 的核心优点，并集成了 `checksec`, `ROPgadget`, `one_gadget` 等常用工具，提供了一套稳定、高效且功能丰富的工具集。

## ✨ 功能特性

-   **🤖 智能静态分析**: 自动识别二进制文件的架构、保护机制（NX, PIE, Canary, RELRO）、危险函数和可疑字符串。
-   **🚀 高级动态执行**: 支持本地运行、自动生成循环模式（De Bruijn sequence）并精确计算缓冲区溢出偏移量。
-   **🐞 深度 GDB/pwndbg 集成**: 通过 GDB/MI 稳定驱动 GDB/pwndbg，提供对寄存器、栈、代码、内存、堆、ROP gadgets 等的全方位程序化访问。
-   **🛠️ 常用工具集成**: 无缝调用 `checksec`, `ROPgadget`, `one_gadget`, `patchelf` 等核心 PWN 工具。
-   **🧭 策略规划**: 基于静态分析结果，智能生成漏洞利用的攻击向量和步骤建议。
-   **✍️ 模板与报告生成**: 一键生成 `pwntools` 漏洞利用脚本、GDB 调试配置文件以及 Markdown 格式的分析报告。
-   **🔧 灵活的辅助工具**: 提供子进程执行、Git 仓库查询、Python 沙箱执行等实用工具。

---

## ⚙️ 配置

本项目通过 `.env` 文件进行集中配置，实现了环境与代码的分离。

**初次使用**:
1.  将项目根目录下的 `.env.example` 文件复制一份，并重命名为 `.env`。
    ```bash
    cp .env.example .env
    ```
2.  根据您的需求编辑 `.env` 文件。

所有配置项都可以被**命令行参数**或 **Docker Compose** 文件中的环境变量覆盖，优先级如下：
**命令行参数 > 环境变量 > `.env` 文件 > 默认值**

### 可用配置项

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Web 服务器绑定的 IP 地址。 |
| `MCP_PORT` | `5500` | MCP 主服务端口。 |
| `API_PORT` | `5501` | 附加 API 服务端口（预留）。 |
| `LOG_LEVEL` | `INFO` | 日志级别 (`DEBUG`, `INFO`, `WARNING`, `ERROR`)。 |
| `ENABLE_DEEP_STATIC` | `true` | 是否默认启用 Rizin 深度静态分析。 |
| `ENABLE_RETDEC` | `false` | 是否默认启用 RetDec 反编译工具（如果安装）。 |
| `ALLOW_DANGEROUS` | `true` | 是否允许执行 `pwndbg_command`, `run_command` 等可能修改系统状态的高危命令。 |
| `WORKSPACE_DIR` | `/workspace` | 工作区目录，用于存放二进制文件和报告（在 Docker 中）。对于本地执行，默认为 `./workspace`。 |
| `GDB_PATH` | `pwndbg` | GDB/Pwndbg 可执行文件路径。 |
| `PYTHONUNBUFFERED` | `1` | Python 输出流配置，无需修改。 |


---

## 🚀 安装与启动

由于本项目的核心工具（如 GDB/pwndbg）基于 Linux 环境，我们推荐通过 WSL 2 (Windows Subsystem for Linux) 或 Docker 来运行。

**开始之前，请先完成上述“配置”部分的说明，创建并检查您的 `.env` 文件。**

### ⭐ Windows 用户向导：使用 `install.ps1` 自动化配置 WSL

如果您是 Windows 用户，`install.ps1` 脚本是您的最佳起点。它是一个自动化配置向导，可以为您完成所有繁琐的 WSL 环境准备工作。

**此脚本会自动：**
1.  检查并帮助您安装 WSL 2。
2.  检查并帮助您从 Microsoft Store 安装 Ubuntu 发行版。
3.  **调用 `install.sh`**：在配置好的 Ubuntu 环境中，自动执行 Linux 安装脚本，完成所有后续的应用依赖安装。

**使用步骤：**
1.  **以管理员身份** 打开 PowerShell。
2.  进入项目根目录。
    ```powershell
    cd C:\path\to\your\pwnmcp_kiki1e
    ```
3.  运行配置向导。
    ```powershell
    # PowerShell 需要设置执行策略才能运行脚本
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
    .\install.ps1
    ```
4.  根据屏幕上的提示操作。脚本可能会要求您重启电脑以完成 WSL 安装。
5.  脚本执行成功后，您的 WSL 环境便已配置完毕，可以按照 **方法一** 中的步骤从 WSL 终端启动服务器。

---

### 方法一：在 WSL / Linux 中使用自动化脚本 (推荐)

此方法将直接在您的系统中安装所有必要的依赖和工具，性能最好。对于 Windows 用户，建议先通过上面的 `install.ps1` 向导完成环境配置。

**1. 进入项目目录**

首先，在您的 WSL/Linux 终端中进入项目文件夹。
```bash
# 示例路径，请替换为您的实际路径
cd /path/to/your/pwnmcp_kiki1e
```

**2. 运行自动化安装脚本**

`install.sh` 脚本会负责所有工作，包括安装系统依赖、Python 环境、pwndbg 和其他工具。
```bash
# 赋予脚本执行权限
chmod +x install.sh

# 运行脚本
./install.sh
```
> **注意**: 脚本在执行过程中会使用 `sudo`，因此可能需要您输入密码。同时，它会询问您是否安装 Rizin 等可选组件，建议全部同意（输入 `y`）以获得最完整的功能。

**3. 启动服务器**

安装完成后，脚本会自动生成一个 `start.sh` 启动器。此脚本会加载 `.env` 文件并启动服务。
```bash
./start.sh
```
当您看到 `PwnMCP Kiki1e 启动...` 或类似的输出时，服务器即已成功启动。

---

### 方法二：使用 Docker 部署

此方法可以将所有环境隔离在 Docker 容器中，具有最佳的可移植性和环境一致性。

**前提**: 请确保您已安装并运行 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

**1. 进入项目目录**
在 PowerShell 或 CMD 中进入项目文件夹。
```powershell
# 示例路径，请替换为您的实际路径
cd C:\path\to\your\pwnmcp_kiki1e
```

**2. 使用 Docker Compose 构建并运行**
这是最简单的 Docker 启动方式。`docker-compose.yml` 会自动加载 `.env` 文件中的配置。
```bash
# 构建镜像并后台启动服务
docker compose up --build -d

# 查看实时日志
docker compose logs -f

# 如需进入容器内部
docker compose exec pwnmcp-kiki1e bash
```

**3. (备选) 手动构建与运行**
```bash
# 构建镜像
docker build -t pwnmcp-kiki1e .

# 运行容器
docker run -it --rm \
  --cap-add=SYS_PTRACE --cap-add=SYS_ADMIN --security-opt seccomp=unconfined \
  --env-file .env \
  -p "$(grep MCP_PORT .env | cut -d '=' -f2):$(grep MCP_PORT .env | cut -d '=' -f2)" \
  -v "./workspace:/workspace" \
  pwnmcp-kiki1e
```

---

## 🔌 连接到 AI 客户端

要让 Claude Desktop 或 Cursor 使用此工具，您需要修改它们的 MCP 配置文件。

### 1. Claude Desktop 配置

编辑配置文件（如果文件不存在请创建）：
*   **路径**: `%APPDATA%\Claude\claude_desktop_config.json`
    *   (您可以直接在文件资源管理器地址栏输入上述路径并回车)

将以下内容添加到配置文件中（请确保修改路径为您实际的项目路径）：

```json
{
  "mcpServers": {
    "pwnmcp": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd /mnt/c/Users/ds/Desktop/pwnmcp_kiki1e && ./start.sh"
      ]
    }
  }
}
```
*注意：如果您将项目移动到了其他位置，请务必更新 `cd` 后面的路径。*

配置完成后，**完全重启 Claude Desktop** 即可生效。

### 2. Cursor 配置

Cursor 目前支持通过 `.cursor/mcp.json` 或设置界面进行配置。

1.  在 Cursor 中打开命令面板 (`Ctrl + Shift + P`)。
2.  输入并选择 **"MCP: Open Settings"** 或直接编辑配置文件。
3.  添加一个新的 MCP 服务器：
    *   **Name**: `pwnmcp`
    *   **Type**: `stdio`
    *   **Command**: `wsl`
    *   **Args**:
        *   `bash`
        *   `-c`
        *   `cd /mnt/c/Users/ds/Desktop/pwnmcp_kiki1e && ./start.sh`

配置完成后，点击刷新或重启 Cursor，您应该能在聊天中看到 MCP 工具已加载。

### 3. 与本地 AI 助手直接交互 (如 Gemini CLI)

如果您使用的 AI 助手拥有**直接执行 Shell 命令**的权限（例如您当前正在使用的命令行 AI 助手），则**无需配置 MCP 服务器**。

在这种模式下，AI 助手可以直接调用本项目已安装的工具链。您只需下达自然语言指令，助手会自动执行相应的 `wsl` 命令。

**交互示例：**
*   "检查 `workspace/chall` 的保护机制。" -> *助手执行 `wsl checksec --file=workspace/chall`*
*   "在 WSL 中启动 GDB 调试 `chall` 并分析内存布局。" -> *助手执行相关的 `gdb` 指令*
*   "帮我运行 ROPgadget 搜索弹出 `rdi` 的指令。" -> *助手执行 `wsl ROPgadget --binary workspace/chall --only "pop|ret"`*

**优势：**
*   **零配置**: 只要运行了 `install.sh`，助手即可开箱即用。
*   **全权限**: 助手可以直接读取输出文件、修改利用脚本并进行实时调试，不受 MCP 协议格式的限制。

---

## 🛠️ MCP 工具参考

服务器启动后，AI 助手将可以使用以下工具来为您服务。

<details>
<summary><strong>核心与静态分析工具</strong></summary>

| 工具 ID | 描述 |
| :--- | :--- |
| `health_check()` | 检查服务器是否正常运行。 |
| `init_session(binary_path)` | 初始化一个新的分析会话（高级功能）。 |
| `load_session(session_id)` | 加载一个已存在的历史会话（高级功能）。 |
| `analyze_binary(path, deep)` | 对二进制文件进行静态分析。`deep=True` 启用 Rizin 深度分析。 |
| `suggest_strategy()` | 基于静态分析结果，生成漏洞利用策略。 |
| `calculate_offsets(pattern_dump_hex)` | 从崩溃时寄存器中的模式字符串精确计算偏移量。 |
| `checksec(file_path)` | 运行 `checksec` 检查二进制文件的安全属性，返回 JSON 结果。 |
| `ropgadget(binary_path, options)` | 运行 `ROPgadget` 在二进制文件中查找 gadgets。 |
| `onegadget(libc_path)` | 运行 `one_gadget` 在指定的 libc 文件中查找 one-gadget ROP 攻击地址。 |

</details>

<details>
<summary><strong>动态执行与 GDB/pwndbg 调试</strong></summary>

| 工具 ID | 描述 |
| :--- | :--- |
| `run_local(...)` | 在本地环境中运行二进制文件，可指定参数、输入、超时等。 |
| `run_with_gdb_pattern(...)` | 使用 GDB 和循环模式自动检测缓冲区溢出偏移量。 |
| `pwndbg_set_file(path, clean_session)` | **调试第一步**。在 GDB 中加载目标二进制文件。 |
| `pwndbg_run(args, start)` | 在 GDB 中运行程序。`start=True` 会在程序入口点暂停。 |
| `pwndbg_step(command)` | 执行 GDB 的步进命令，如 `c` (continue), `n` (next), `s` (step)。 |
| `pwndbg_context(context_type)` | 获取 pwndbg 的上下文信息（寄存器 `regs`、栈 `stack`、代码 `code` 等）。 |
| `pwndbg_command(command)` | **[高危]** 执行任意的 GDB 或 pwndbg 命令。 |
| `pwndbg_break_at_main(args)` | 智能在 `main` 函数处设置断点并运行到该位置。 |
| `pwndbg_get_function_address(name)` | 在程序运行时智能解析函数的真实地址。 |

</details>

<details>
<summary><strong>生成与辅助工具</strong></summary>

| 工具 ID | 描述 |
| :--- | :--- |
| `generate_template(...)` | 生成 `pwntools` 漏洞利用脚本模板。 |
| `generate_gdb_profile(...)` | 生成 GDB 调试脚本。 |
| `export_report()` | 导出当前分析的 Markdown 格式报告。 |
| `patchelf(...)` | **[高危]** 运行 `patchelf` 修改二进制文件的解释器或 RPATH。 |
| `run_command(command, ...)` | **[高危]** 在服务器的受控 shell 中执行任意系统命令。 |
| `python_run(code, ...)` | **[高危]** 在隔离的 Python 解释器中执行代码片段。 |
| `git_status()` / `git_log()` | 执行 Git 命令。 |

</details>

---

## 💡 典型工作流

### 流程 1: 完整分析
```text
1. init_session (or pwndbg_set_file)
2. analyze_binary (获取静态信息)
3. suggest_strategy (获取攻击思路)
4. run_with_gdb_pattern (计算偏移量)
5. ropgadget / onegadget (查找 gadgets)
6. generate_template (生成利用模板)
7. python_run (测试脚本)
8. export_report (导出报告)
```

### 流程 2: 快速调试
```text
1. pwndbg_set_file (加载文件)
2. pwndbg_run(start=True) (在入口点断下)
3. pwndbg_context (查看上下文)
4. pwndbg_step('n') (单步步过)
5. pwndbg_command('telescope $rsp 20') (查看栈)
```

---

## 📁 项目结构

根据 `pyproject.toml`, `Dockerfile` 和实际文件结构确认。

```
pwnmcp_kiki1e/
├── install.sh            # WSL/Linux 自动化安装脚本
├── start.sh              # WSL/Linux 启动脚本 (由 install.sh 自动生成)
├── Dockerfile            # Docker 镜像定义
├── docker-compose.yml    # Docker Compose 配置
├── pyproject.toml        # Python 项目与依赖配置 (PEP 621)
├── README.md             # 本文档
├── workspace/            # 默认工作目录, 存放目标程序、报告等
├── tests/                # Pytest 测试目录
└── pwnmcp/               # Python 核心源码
    ├── __main__.py       # 命令行启动入口 (python -m pwnmcp)
    ├── server.py         # FastAPI 服务与 MCP 工具定义
    ├── core/             # 核心数据模型、异常、会话管理
    ├── gdb/              # GDB/pwndbg 控制器 (gdb_controller.py)
    ├── static/           # 静态分析模块 (static_analyzer.py)
    ├── dynamic/          # 动态执行模块 (dynamic_executor.py)
    ├── strategy/         # 攻击策略生成
    ├── tools/            # 辅助工具模块 (pwn_cli_tools.py)
    └── templates/        # 报告和脚本模板
```

---

## 🐛 故障排查

-   **GDB 无法附加进程 (Permission Denied)**
    -   **WSL/Linux**: 您的 ptrace 权限可能受限。`install.sh` 脚本会尝试自动修复。如果问题仍在，请手动执行：`sudo sysctl -w kernel.yama.ptrace_scope=0`
    -   **Docker**: 确保启动容器时添加了 `--cap-add=SYS_PTRACE` 和 `--security-opt seccomp=unconfined` 参数。`docker-compose.yml` 已为您正确配置。

-   **命令未找到 (e.g., `pwndbg`, `rizin`)**
    -   **本地/WSL**: 请确保您已成功运行 `install.sh` 脚本，并且没有跳过任何可选组件的安装。
    -   **Docker**: 如果您手动构建，请检查 `Dockerfile` 的构建日志确保所有工具都已正确安装。

-   **dpkg 被锁定 (dpkg frontend lock)**
    -   这是由于 Ubuntu/Debian 的自动更新进程正在后台运行。`install.sh` 会自动等待其完成。如果等待超时，您可以手动终止它：`sudo killall unattended-upgr`，然后重新运行安装脚本。

---

## 🧹 卸载指南

请根据您的需求选择合适的卸载层级。

### 层级 1：仅移除项目

此操作会删除项目文件和 Python 虚拟环境，但会保留您已安装的 WSL、Ubuntu 系统和系统级的依赖工具。

1.  **删除项目文件夹**: 在 Windows 文件资源管理器中，直接删除整个项目文件夹（例如 `C:\Users\ds\Desktop\pwnmcp_kiki1e`）。

### 层级 2：移除项目和 Ubuntu on WSL

如果您希望移除为本项目安装的 Ubuntu 环境，可以执行此操作。

1.  **查看已安装的 WSL 发行版**: 在 Windows PowerShell 或 CMD 中，运行以下命令查看确切的发行版名称。
    ```powershell
    wsl --list --verbose
    ```

2.  **注销并卸载 Ubuntu**: 使用上一步中看到的名称替换 `<distro_name>`。
    ```powershell
    # 警告：此命令将永久删除该 Ubuntu 发行版及其中的所有数据！
    wsl --unregister <distro_name>
    ```
    例如: `wsl --unregister Ubuntu-22.04`

### 层级 3：完全禁用 WSL

如果您希望从 Windows 系统中彻底移除 WSL 功能。

1.  **以管理员身份打开 PowerShell**。
2.  执行以下命令禁用相关 Windows 功能。
    ```powershell
    # 禁用 Windows Subsystem for Linux
    dism.exe /online /disable-feature /featurename:Microsoft-Windows-Subsystem-Linux /norestart

    # 禁用虚拟机平台
    dism.exe /online /disable-feature /featurename:VirtualMachinePlatform /norestart
    ```
3.  **重启电脑** 以使变更完全生效。

---

## 📄 许可证

本项目基于 **MIT** 许可证。