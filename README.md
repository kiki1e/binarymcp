# BinaryMCP

AI 驱动的二进制分析平台，基于 **Model Context Protocol (MCP)** 构建。为 Claude、Cursor 等 AI 助手提供逆向工程、动态调试、密码学分析和漏洞利用的完整工具链。

## 项目结构

```
binarymcp/
├── idamcp/              # IDA Pro MCP 桥接 (Windows 本地)
│   ├── scripts/         # IDA 插件脚本 (ida_server.py)
│   └── mcp_bridge.py    # MCP 服务端
│
├── pwnmcp/              # 核心源码 (开发主仓库)
│   ├── pwnmcp/          # Python 包
│   │   ├── tools/       # MCP 工具实现
│   │   │   ├── reverse_tools.py         # Ghidra, radare2, binwalk
│   │   │   ├── crypto_tools.py          # Hash, RSA, 编码, XOR, 频率分析
│   │   │   ├── binary_exploit_tools.py  # angr, seccomp, libc, 格式化字符串
│   │   │   ├── pwn_cli_tools.py         # checksec, ROPgadget, one_gadget
│   │   │   ├── subprocess_tools.py      # 命令执行
│   │   │   ├── git_tools.py             # Git 操作
│   │   │   └── python_tools.py          # Python 脚本执行
│   │   ├── static/      # 静态分析引擎
│   │   ├── dynamic/     # 动态执行 + pwndbg 控制
│   │   ├── gdb/         # GDB MI 控制器
│   │   ├── strategy/    # 漏洞利用策略规划
│   │   ├── templates/   # pwntools 模板生成
│   │   ├── server.py    # MCP 服务器 (所有工具注册)
│   │   └── __main__.py  # 入口点
│   ├── backend/         # Web API 后端 (Docker 可选)
│   ├── frontend/        # React 前端 (Docker 可选)
│   ├── ida-bridge/      # IDA HTTP 代理 (Docker 可选)
│   └── pyproject.toml   # Python 依赖
│
├── wslmcp/              # WSL 部署包 (stdio 传输)
│   ├── install.sh       # WSL 一键安装脚本
│   ├── install.ps1      # Windows PowerShell 安装向导
│   ├── start.sh         # 启动脚本
│   ├── start_windows.bat
│   ├── mcp_config_example.json
│   ├── pwnmcp/          # 源码副本
│   └── pyproject.toml
│
└── vmmcp/               # VM 部署包 (SSE/HTTP 传输)
    ├── install_vm.sh    # VM 一键安装 (含防火墙/systemd)
    ├── start_sse.sh     # SSE 模式启动
    ├── mcp_config_example.json
    ├── pwnmcp/          # 源码副本
    ├── pyproject.toml
    ├── Dockerfile       # Docker 部署 (可选)
    ├── docker-compose.yml
    ├── backend/         # Web 后端 (可选)
    ├── frontend/        # Web 前端 (可选)
    └── ida-bridge/      # IDA 代理 (可选)
```

---

## 三种部署方式

### 1. WSL 部署 (推荐用于 Windows + Claude Desktop/Cursor)

AI 客户端通过 **stdio** 直接与 WSL 中的 pwnmcp 通信，零延迟。

```bash
# 在 PowerShell 中进入 WSL
wsl -d Ubuntu

# 安装
cd /mnt/c/Users/<你的用户名>/Desktop/binarymcp/wslmcp
chmod +x install.sh
./install.sh                  # 基础安装
./install.sh --with-all       # 安装全部 (含 Ghidra + angr)

# 启动
./start.sh
```

**MCP 客户端配置** (`mcp_config_example.json`):
```json
{
  "mcpServers": {
    "binary_pwn": {
      "command": "wsl",
      "args": ["bash", "-c", "cd /mnt/c/Users/ds/Desktop/binarymcp/wslmcp && ./start.sh"]
    }
  }
}
```

### 2. VM 部署 (推荐用于独立 Ubuntu 虚拟机)

AI 客户端通过 **SSE/HTTP** 网络连接，适合远程分析环境。

```bash
# 在 VM 中
cd /path/to/vmmcp
chmod +x install_vm.sh
./install_vm.sh               # 安装 (自动配置防火墙+systemd)
./install_vm.sh --with-all    # 安装全部

# 启动
./start_sse.sh                # http://vm-ip:5500/sse

# 或使用 systemd 服务
sudo systemctl enable pwnmcp
sudo systemctl start pwnmcp
```

**MCP 客户端配置**:
```json
{
  "mcpServers": {
    "binary_pwn": {
      "url": "http://YOUR_VM_IP:5500/sse"
    }
  }
}
```

### 3. IDA Pro 桥接 (Windows 本地)

在 Windows 上连接 IDA Pro 进行交互式逆向分析。

```bash
# 1. 在 IDA Pro 中: File → Script File → 加载 idamcp/scripts/ida_server.py
# 2. 在终端中:
cd idamcp
pip install .
python mcp_bridge.py
```

**MCP 客户端配置**:
```json
{
  "mcpServers": {
    "binary_ida": {
      "command": "python",
      "args": ["C:/Users/ds/Desktop/binarymcp/idamcp/mcp_bridge.py"]
    }
  }
}
```

---

## 安装选项

`install.sh` / `install_vm.sh` 支持以下参数:

| 参数 | 说明 | 大小 |
|------|------|------|
| *(无参数)* | 安装所有默认工具 | ~2GB |
| `--with-ghidra` | 额外安装 Ghidra headless + JDK 17 | +700MB |
| `--with-angr` | 额外安装 angr 符号执行引擎 | +1GB |
| `--with-all` | 安装全部可选组件 | +1.7GB |
| `--fix` | 修复模式 (重建虚拟环境) | - |

---

## MCP 工具一览

### 静态分析

| 工具 | 说明 |
|------|------|
| `analyze_binary` | 全面静态分析 (架构/保护/符号/字符串/危险函数) |
| `checksec` | 检查二进制安全属性 (NX/PIE/Canary/RELRO) |
| `r2_analyze` | radare2 全面分析 (函数/导入/字符串/段/导出) |
| `r2_decompile` | radare2 反编译函数 (自动回退 pdg→pdd→pdf) |
| `r2_command` | 执行自定义 radare2 命令 |
| `ghidra_decompile` | Ghidra headless 反编译 *(需 --enable-ghidra)* |
| `ghidra_analyze` | Ghidra 完整分析 *(需 --enable-ghidra)* |

### 动态调试 (GDB/pwndbg)

| 工具 | 说明 |
|------|------|
| `pwndbg_set_file` | 加载二进制文件到 GDB |
| `pwndbg_run` | 运行程序 (支持 starti 模式) |
| `pwndbg_break_at_main` | 智能定位 main 函数并断点 |
| `pwndbg_context` | 查看寄存器/栈/代码/回溯 |
| `pwndbg_step` | 步进 (c/n/s/ni/si) |
| `pwndbg_command` | 执行任意 GDB/pwndbg 命令 |
| `pwndbg_get_function_address` | 解析函数运行时地址 (PIE/ASLR) |
| `run_local` | 直接运行二进制文件 |
| `run_with_gdb_pattern` | 自动检测缓冲区溢出偏移量 |

### 密码学

| 工具 | 说明 |
|------|------|
| `hash_compute` | 计算哈希 (md5/sha1/sha256/sha512/sha3/blake2) |
| `hash_compute_all` | 一次性计算所有常用哈希 |
| `hash_identify` | 根据长度/格式自动识别哈希类型 |
| `hash_crack` | hashcat/john 字典破解 |
| `rsa_analyze` | RSA 自动攻击 (试除/Fermat/低指数/dp泄露) |
| `encode_decode` | 编码解码 (base64/hex/rot13/binary/morse/url) |
| `xor_analyze` | XOR 加解密 + 单字节暴力破解 |
| `frequency_analysis` | 频率分析 + Caesar 暴破 + IC 计算 |

### 漏洞利用

| 工具 | 说明 |
|------|------|
| `ropgadget` | ROPgadget 搜索 gadgets |
| `onegadget` | one_gadget 查找 |
| `patchelf` | 修改 ELF 解释器/RPATH |
| `seccomp_dump` | 转储 seccomp 沙箱规则 |
| `libc_identify` | 通过函数地址识别 libc 版本 |
| `libc_find_gadgets` | 在 libc 中查找 ROP gadgets |
| `format_string_offsets` | 自动检测格式化字符串偏移 |
| `ret2libc_calc` | 计算 ret2libc 攻击地址 |
| `suggest_strategy` | 根据分析结果建议利用策略 |
| `angr_find_path` | 符号执行寻找目标路径 *(需 --enable-angr)* |
| `angr_find_input` | 寻找触发特定输出的输入 *(需 --enable-angr)* |

### 固件分析

| 工具 | 说明 |
|------|------|
| `firmware_scan` | binwalk 扫描固件组件 |
| `firmware_extract` | 提取固件文件系统 |
| `firmware_entropy` | 熵分析 (检测加密/压缩区域) |

### 辅助工具

| 工具 | 说明 |
|------|------|
| `run_command` | 执行 shell 命令 |
| `python_run` | 执行 Python 脚本 |
| `git_status` / `git_log` | Git 操作 |
| `generate_template` | 生成 pwntools 利用模板 |
| `export_report` | 导出分析报告 (Markdown) |

### IDA Pro (idamcp 模块)

| 工具 | 说明 |
|------|------|
| `check_connection` | 检查 IDA 连接状态 |
| `get_info` | 获取二进制基本信息 |
| `list_functions` | 列出函数 |
| `get_pseudocode` | 获取 Hex-Rays 反编译结果 |
| `get_assembly` | 获取汇编代码 |
| `get_xrefs_to` | 获取交叉引用 |

---

## 已安装工具链

### 默认安装

| 类别 | 工具 |
|------|------|
| 逆向 | radare2, rizin, binwalk, firmware-mod-kit, objdump, readelf, strings |
| 调试 | GDB, gdb-multiarch, pwndbg, strace, ltrace |
| PWN | pwntools, ROPgadget, ropper, one_gadget, checksec, patchelf, seccomp-tools, pwninit |
| 密码 | pycryptodome, z3-solver, gmpy2, sympy, cryptography, hashcat, john |
| 模拟 | QEMU user/system (ARM, MIPS) |
| Python | mcp, pygdbmi, fastapi, uvicorn, psutil, rich |

### 可选安装

| 工具 | 参数 | 说明 |
|------|------|------|
| Ghidra | `--with-ghidra` | headless 反编译器 + JDK 17 (~700MB) |
| angr | `--with-angr` | 符号执行引擎 (~1GB) |

---

## 运行时参数

```bash
python -m pwnmcp [参数]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--transport` | `stdio` | 传输方式: `stdio` (本地) 或 `sse` (HTTP) |
| `--host` | `0.0.0.0` | 监听地址 (SSE 模式) |
| `--port` | `5500` | 监听端口 (SSE 模式) |
| `--workspace` | `./workspace` | 工作目录 |
| `--deep-static` | `true` | 启用深度静态分析 (Rizin) |
| `--enable-ghidra` | `false` | 启用 Ghidra 工具 |
| `--enable-angr` | `false` | 启用 angr 工具 |
| `--gdb-path` | `pwndbg` | GDB 可执行文件路径 |
| `--allow-dangerous` | `true` | 允许执行危险命令 |
| `--log-level` | `INFO` | 日志级别 |

也支持通过环境变量配置: `TRANSPORT`, `HOST`, `MCP_PORT`, `ENABLE_GHIDRA`, `ENABLE_ANGR`, `GHIDRA_HOME` 等。

---

## 使用示例

### CTF PWN: 栈溢出

```
> 分析 /workspace/chall 的安全属性和漏洞
AI 调用: checksec("/workspace/chall")
AI 调用: analyze_binary("/workspace/chall")
AI 调用: r2_decompile("/workspace/chall", "main")
→ 发现: NX 开启, 无 Canary, 存在 gets() 调用

> 找到溢出偏移量
AI 调用: run_with_gdb_pattern("/workspace/chall", 200)
→ RIP 偏移: 72 字节

> 生成利用模板
AI 调用: generate_template("/workspace/exploit.py")
```

### CTF Crypto: RSA

```
> 分析 RSA 参数: n=... e=3 c=...
AI 调用: rsa_analyze(n="...", e="3", c="...")
→ 低加密指数攻击成功, 明文: flag{...}
```

### 逆向: 固件分析

```
> 分析固件 firmware.bin
AI 调用: firmware_scan("/workspace/firmware.bin")
AI 调用: firmware_extract("/workspace/firmware.bin")
AI 调用: firmware_entropy("/workspace/firmware.bin")
→ 提取出 SquashFS 文件系统, 发现加密区域
```

---

## 许可证

MIT License
