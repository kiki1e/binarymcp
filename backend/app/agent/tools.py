"""
Agent 工具定义 — CTF 分析工具集
"""

import json
import logging
import os
import subprocess
import sys
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ENGINE_URL = os.getenv("ENGINE_URL", "http://engine:5500")
IDA_BRIDGE_URL = os.getenv("IDA_BRIDGE_URL", "http://ida-bridge:5600")
_http_client: Optional[httpx.AsyncClient] = None


def _get_http() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60)
    return _http_client


async def _call_engine_tool(tool_name: str, params: dict) -> str:
    """通过 MCP SSE 协议调用 engine 工具"""
    try:
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession

        async with sse_client(url=f"{ENGINE_URL}/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, params)
                text = ""
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text += content_item.text
                    elif isinstance(content_item, dict):
                        text += str(content_item.get('text', ''))
                return text or "(empty result)"
    except Exception as e:
        logger.warning("Engine 工具 [%s] 调用失败: %s", tool_name, e)
        return f"[Engine 不可用: {e}]"


class Tool:
    """工具定义"""

    def __init__(self, name: str, description: str, parameters: dict, fn: callable):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema
        self.fn = fn

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def run(self, **kwargs) -> str:
        try:
            result = await self.fn(**kwargs)
            return str(result)
        except Exception as e:
            logger.error("工具 %s 执行失败: %s", self.name, e)
            return f"错误: {e}"


# ── 工具实现 ──

async def _check_protections(file_path: str) -> str:
    """检查二进制文件保护机制"""
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"
    try:
        result = subprocess.run(
            ["checksec", "--file=" + file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    # fallback: read ELF headers
    try:
        result = subprocess.run(
            ["readelf", "-l", file_path],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
        protections = {}
        protections["RELRO"] = "Partial RELRO" if "GNU_RELRO" in output else "No RELRO"
        protections["Stack Canary"] = "Yes" if "__stack_chk_fail" in output else "No"
        protections["NX"] = "Yes" if "GNU_STACK" in output and "RWE" not in output else "No"
        protections["PIE"] = "Yes" if "PT_LOAD" in output and "Type" in output else "No"
        return json.dumps(protections, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"无法检查保护机制: {e}"


async def _extract_strings(file_path: str, min_length: int = 6) -> str:
    """提取二进制文件中的字符串"""
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"
    try:
        result = subprocess.run(
            ["strings", "-n", str(min_length), file_path],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.split("\n")
        # 去重、过滤
        unique = sorted(set(line.strip() for line in lines if line.strip()))
        return "\n".join(unique[:200])  # 限制输出
    except Exception as e:
        return f"提取字符串失败: {e}"


async def _run_python(code: str) -> str:
    """执行 Python 代码 (用于解密/求解)"""
    try:
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr

        f_out = io.StringIO()
        f_err = io.StringIO()
        exec_globals = {"__builtins__": __builtins__}
        with redirect_stdout(f_out), redirect_stderr(f_err):
            exec(code, exec_globals)
        output = f_out.getvalue()
        error = f_err.getvalue()
        result = ""
        if output:
            result += f"标准输出:\n{output}\n"
        if error:
            result += f"标准错误:\n{error}\n"
        # 收集生成的变量
        safe_vars = {k: v for k, v in exec_globals.items()
                     if not k.startswith("_") and not callable(v)
                     and k not in ("__builtins__",)}
        if safe_vars:
            result += f"变量:\n{json.dumps({k: str(v)[:200] for k, v in safe_vars.items()}, ensure_ascii=False)}\n"
        return result.strip() or "代码执行完成（无输出）"
    except Exception as e:
        return f"执行错误: {e}"


async def _file_info(file_path: str) -> str:
    """获取文件基本信息"""
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"
    try:
        stat = os.stat(file_path)
        info = {
            "文件名": os.path.basename(file_path),
            "大小": f"{stat.st_size} bytes ({stat.st_size / 1024:.2f} KB)",
        }
        # file 命令 (尝试本地, 失败则走引擎)
        try:
            result = subprocess.run(
                ["file", file_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                info["类型"] = result.stdout.strip()
            else:
                raise FileNotFoundError
        except FileNotFoundError:
            eng_result = await _call_engine_tool("run_command", {"command": f"file {file_path}"})
            info["类型"] = eng_result.strip()
        # readelf (走引擎)
        try:
            eng_result = await _call_engine_tool("run_command", {"command": f"readelf -h {file_path}"})
            for line in eng_result.split("\n"):
                if "Machine" in line:
                    info["架构"] = line.split(":")[-1].strip()
                elif "Class" in line:
                    info["位数"] = line.split(":")[-1].strip()
        except Exception:
            pass
        return json.dumps(info, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"获取文件信息失败: {e}"


async def _search_web(query: str) -> str:
    """搜索网络获取 CTF 相关信息 (占位)"""
    return f"搜索: {query}\n（网络搜索功能需要在服务器配置）"


# ── 引擎/IDA 分析工具 (AI 自主调用) ──

async def _engine_run_command(command: str) -> str:
    """在分析引擎容器上执行任意命令"""
    return await _call_engine_tool("run_command", {"command": command})


async def _engine_analyze_binary(file_path: str) -> str:
    """对二进制文件进行深度分析 (架构/函数/段等)"""
    return await _call_engine_tool("analyze_binary", {"path": file_path})


async def _engine_checksec(file_path: str) -> str:
    """检查二进制保护机制 (checksec)"""
    return await _call_engine_tool("checksec", {"file_path": file_path})


async def _engine_ropgadget(file_path: str) -> str:
    """查找 ROP gadgets"""
    return await _call_engine_tool("ropgadget", {"binary_path": file_path})


async def _engine_decompile(file_path: str, function: str = "main") -> str:
    """反编译指定函数"""
    result = await _call_engine_tool("run_command", {
        "command": f"rizin -q -c 'aaa; s {function}; pdg' {file_path} 2>/dev/null"
    })
    return result


async def _ida_decompile(function: str = "main") -> str:
    """通过 IDA Pro 反编译函数 (需要 IDA 已连接)"""
    try:
        r = await _get_http().get(f"{IDA_BRIDGE_URL}/ida/status", timeout=10)
        if r.json().get("status") != "connected":
            return "IDA Pro 未连接"
        r = await _get_http().post(f"{IDA_BRIDGE_URL}/ida/decompile", json={"target": function}, timeout=30)
        data = r.json()
        return data.get("code", data.get("pseudocode", f"(无法反编译 {function})"))
    except Exception as e:
        return f"IDA 调用失败: {e}"


async def _ida_list_functions() -> str:
    """列出 IDA 中识别的所有函数"""
    try:
        r = await _get_http().get(f"{IDA_BRIDGE_URL}/ida/functions", timeout=10)
        funcs = r.json().get("functions", [])
        names = [f.get("name", f.get("address", "?")) for f in funcs[:80]]
        return "\n".join(names) if names else "(无函数列表)"
    except Exception as e:
        return f"IDA 调用失败: {e}"


async def _read_file(path: str, max_lines: int = 100) -> str:
    """读取文本文件内容"""
    if not os.path.exists(path):
        return f"文件不存在: {path}"
    try:
        with open(path, "r", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (超出 {max_lines} 行, 截断)")
                    break
                lines.append(line.rstrip())
            return "\n".join(lines)
    except Exception as e:
        return f"读取失败: {e}"


# ── 容器管理工具 (AI 自主安装环境) ──

# 流式命令输出缓冲区: task_id -> [output lines]
_cmd_output_buffers: dict[str, list[str]] = {}
# 当前正在为哪个 task_id 运行命令
_current_cmd_task_id: str = ""


def _set_cmd_task_id(task_id: str):
    """由分析流水线设置当前 task_id，用于流式命令输出"""
    global _current_cmd_task_id
    _current_cmd_task_id = task_id
    if task_id:
        _cmd_output_buffers[task_id] = []


def _get_cmd_output(task_id: str, clear: bool = False) -> list[str]:
    """获取指定 task 的命令输出缓冲区内容"""
    lines = _cmd_output_buffers.get(task_id, [])
    if clear:
        _cmd_output_buffers[task_id] = []
    return lines

async def _container_install(packages: str, type: str = "apt") -> str:
    """在容器中安装软件包 (apt/pip)，AI 可自主安装缺失工具"""
    try:
        if type == "apt":
            subprocess.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
            result = subprocess.run(
                ["apt-get", "install", "-y", "--no-install-recommends"] + packages.split(),
                capture_output=True, text=True, timeout=180,
            )
        elif type == "pip":
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install"] + packages.split(),
                capture_output=True, text=True, timeout=180,
            )
        else:
            return f"未知安装类型: {type}，支持 apt/pip"
        output = result.stdout[-1500:] or ""
        if result.stderr:
            output += "\n" + result.stderr[-500:]
        if result.returncode == 0:
            return f"✅ 安装成功:\n{output}"
        else:
            return f"❌ 安装失败:\n{output}"
    except subprocess.TimeoutExpired:
        return "安装超时 (180s)"
    except Exception as e:
        return f"安装失败: {e}"


async def _run_command_local(command: str) -> str:
    """在本地 (后端容器) 执行任意 shell 命令 — 文件分析、解包、网络请求等 (流式输出)"""
    import asyncio
    try:
        task_id = _current_cmd_task_id
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        parts = []
        buffer = _cmd_output_buffers.get(task_id) if task_id else None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors='replace').rstrip()
            parts.append(decoded)
            if buffer is not None:
                buffer.append(decoded)
        await proc.wait()
        output = "\n".join(parts)
        # 限制返回长度
        if len(output) > 2000:
            output = output[-2000:] + f"\n... (截断, 共 {len(output)} 字符)"
        return output.strip() or "(无输出)"
    except asyncio.TimeoutError:
        return "命令超时 (60s)"
    except Exception as e:
        return f"执行失败: {e}"


async def _download_file(url: str, output_path: str = "") -> str:
    """从 URL 下载文件到工作目录 (用于下载依赖库或工具)"""
    try:
        if not output_path:
            output_path = f"/workspace/{url.split('/')[-1]}"
        result = subprocess.run(
            ["curl", "-sSL", "-o", output_path, url],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            size = os.path.getsize(output_path)
            return f"✅ 下载成功: {output_path} ({size/1024:.1f} KB)"
        else:
            # fallback to wget
            result = subprocess.run(
                ["wget", "-q", "-O", output_path, url],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                size = os.path.getsize(output_path)
                return f"✅ 下载成功: {output_path} ({size/1024:.1f} KB)"
            return f"下载失败: {result.stderr[-300:]}"
    except Exception as e:
        return f"下载失败: {e}"


# ── 工具注册 ──

TOOLS: list[Tool] = [
    Tool(
        name="check_protections",
        description="检查二进制文件的保护机制 (Canary/NX/PIE/RELRO)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                }
            },
            "required": ["file_path"],
        },
        fn=_check_protections,
    ),
    Tool(
        name="extract_strings",
        description="提取二进制文件中的可打印字符串",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                },
                "min_length": {
                    "type": "integer",
                    "description": "最小字符串长度",
                    "default": 6,
                },
            },
            "required": ["file_path"],
        },
        fn=_extract_strings,
    ),
    Tool(
        name="file_info",
        description="获取二进制文件的基本信息 (架构、位数、类型等)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                }
            },
            "required": ["file_path"],
        },
        fn=_file_info,
    ),
    Tool(
        name="run_python",
        description="执行 Python 代码用于解密计算、z3 约束求解等",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                }
            },
            "required": ["code"],
        },
        fn=_run_python,
    ),
    Tool(
        name="search_web",
        description="搜索网络获取 CTF 相关技术信息",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                }
            },
            "required": ["query"],
        },
        fn=_search_web,
    ),
    # ── 引擎/IDA 分析工具 ──
    Tool(
        name="engine_run",
        description="在分析引擎容器上执行任意 shell 命令（如 file/strings/readelf/objdump 等）",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                }
            },
            "required": ["command"],
        },
        fn=_engine_run_command,
    ),
    Tool(
        name="engine_analyze",
        description="对二进制文件进行深度分析 (识别架构、函数、段等信息)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                }
            },
            "required": ["file_path"],
        },
        fn=_engine_analyze_binary,
    ),
    Tool(
        name="engine_checksec",
        description="检查二进制文件的安全保护机制 (NX/PIE/Canary/RELRO)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                }
            },
            "required": ["file_path"],
        },
        fn=_engine_checksec,
    ),
    Tool(
        name="engine_ropgadget",
        description="查找二进制文件中的 ROP gadgets (用于构造 ROP 链)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                }
            },
            "required": ["file_path"],
        },
        fn=_engine_ropgadget,
    ),
    Tool(
        name="engine_decompile",
        description="反编译二进制文件的指定函数 (返回伪代码)",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "二进制文件路径",
                },
                "function": {
                    "type": "string",
                    "description": "函数名 (默认 main)",
                },
            },
            "required": ["file_path"],
        },
        fn=_engine_decompile,
    ),
    Tool(
        name="ida_decompile",
        description="通过 IDA Pro 反编译函数 (比 engine_decompile 更精确, 需要 IDA 已连接)",
        parameters={
            "type": "object",
            "properties": {
                "function": {
                    "type": "string",
                    "description": "函数名, 如 main/check/verify/vuln",
                }
            },
            "required": ["function"],
        },
        fn=_ida_decompile,
    ),
    Tool(
        name="ida_functions",
        description="列出 IDA Pro 中识别的所有函数名",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        fn=_ida_list_functions,
    ),
    Tool(
        name="read_file",
        description="读取文本文件内容 (适合查看源代码/配置文件)",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "最多读取行数 (默认 100)",
                },
            },
            "required": ["path"],
        },
        fn=_read_file,
    ),
    # ── 容器管理工具 (AI 自主安装环境 & 执行命令) ──
    Tool(
        name="container_install",
        description="在容器中安装软件包 (APT 或 PIP)。若缺少分析工具先调用此工具安装，如 file/binutils/binwalk/checksec/pwntools/z3 等",
        parameters={
            "type": "object",
            "properties": {
                "packages": {
                    "type": "string",
                    "description": "包名, 多个用空格分隔, 如 'file binutils' 或 'pwntools z3-solver'",
                },
                "type": {
                    "type": "string",
                    "description": "安装方式: 'apt' 或 'pip'",
                    "enum": ["apt", "pip"],
                    "default": "apt",
                },
            },
            "required": ["packages"],
        },
        fn=_container_install,
    ),
    Tool(
        name="run_command",
        description="在后端容器中执行任意 shell 命令 — 文件分析、解包、网络请求、运行 exploit 等。注意: 当前工作目录是 /workspace",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                }
            },
            "required": ["command"],
        },
        fn=_run_command_local,
    ),
    Tool(
        name="download_file",
        description="从 URL 下载文件到工作目录 (如下载 libc.so.6 用于远程利用)",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "文件的下载 URL",
                },
                "output_path": {
                    "type": "string",
                    "description": "保存路径 (可选, 默认自动从 URL 提取文件名)",
                },
            },
            "required": ["url"],
        },
        fn=_download_file,
    ),
]


def get_tool(name: str) -> Tool | None:
    for t in TOOLS:
        if t.name == name:
            return t
    return None


def get_tool_definitions() -> list[dict]:
    """获取 OpenAI 格式的工具定义列表"""
    return [t.to_openai_tool() for t in TOOLS]
