"""
赛题分析流水线

编排 engine (pwnmcp) 工具层 + IDA Pro + AI 模型,
实现 CTF 赛题的自动化分析。
"""

import asyncio
import json
import logging
import os
import time
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ENGINE_URL = os.getenv("ENGINE_URL", "http://engine:5500")
IDA_BRIDGE_URL = os.getenv("IDA_BRIDGE_URL", "http://ida-bridge:5600")


class ChallengeType(str, Enum):
    AUTO = "auto"
    PWN = "pwn"
    REVERSE = "reverse"
    CRYPTO = "crypto"
    IOT = "iot"
    WEB = "web"
    MISC = "misc"


class AnalysisPhase(str, Enum):
    PENDING = "pending"
    DETECTING = "detecting"          # 赛题类型检测
    STATIC_ANALYSIS = "static"       # 静态分析 (checksec/readelf/strings)
    DECOMPILING = "decompiling"      # 反编译 (IDA/Rizin)
    TOOL_ANALYSIS = "tool_analysis"  # 专项工具 (ROP/binwalk/angr)
    AI_ANALYSIS = "ai_analysis"      # AI 模型分析
    EXPLOIT_GEN = "exploit_gen"      # 生成 exploit
    COMPLETED = "completed"
    FAILED = "failed"


class EngineClient:
    """与 pwnmcp engine 容器通信的客户端 (MCP SSE 协议)"""

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=120)

    async def close(self):
        await self._http.aclose()

    async def _call_tool(self, tool_name: str, params: dict) -> dict:
        """通过 MCP SSE 协议调用 engine 的工具"""
        try:
            from mcp.client.sse import sse_client
            from mcp.client.session import ClientSession

            async with sse_client(url=f"{ENGINE_URL}/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, params)
                    # 提取文本内容
                    text = ""
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            text += content_item.text
                        elif isinstance(content_item, dict):
                            text += str(content_item.get('text', ''))
                    return {"result": text}
        except Exception as e:
            logger.error("Engine 工具调用失败 [%s]: %s", tool_name, e)
            return {"error": str(e)}

    async def analyze_binary(self, file_path: str) -> dict:
        return await self._call_tool("analyze_binary", {"path": file_path})

    async def checksec(self, file_path: str) -> dict:
        return await self._call_tool("checksec", {"file_path": file_path})

    async def ropgadget(self, file_path: str) -> dict:
        return await self._call_tool("ropgadget", {"binary_path": file_path})

    async def suggest_strategy(self) -> dict:
        return await self._call_tool("suggest_strategy", {})

    async def run_command(self, command: str) -> dict:
        return await self._call_tool("run_command", {"command": command})


class IDAClient:
    """与 IDA Bridge 通信的客户端"""

    def __init__(self):
        self._client = httpx.AsyncClient(base_url=IDA_BRIDGE_URL, timeout=30)

    async def close(self):
        await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            r = await self._client.get("/ida/status")
            data = r.json()
            return data.get("status") == "connected"
        except Exception:
            return False

    async def get_functions(self) -> list:
        try:
            r = await self._client.get("/ida/functions")
            return r.json().get("functions", [])
        except Exception:
            return []

    async def decompile(self, target: str) -> str:
        try:
            r = await self._client.post("/ida/decompile", json={"target": target})
            data = r.json()
            return data.get("code", data.get("pseudocode", ""))
        except Exception as e:
            return f"IDA 反编译失败: {e}"

    async def get_info(self) -> dict:
        try:
            r = await self._client.get("/ida/info")
            return r.json()
        except Exception:
            return {}


class AnalysisPipeline:
    """赛题自动分析流水线"""

    def __init__(self):
        self.engine = EngineClient()
        self.ida = IDAClient()

    async def close(self):
        await self.engine.close()
        await self.ida.close()

    # ─────────────────────────────────────
    # 赛题类型自动检测
    # ─────────────────────────────────────

    async def detect_type(self, file_path: str) -> ChallengeType:
        """根据文件特征自动判断赛题类型"""
        # 1. 使用 file 命令获取文件类型
        file_result = await self.engine.run_command(f"file {file_path}")
        file_info = str(file_result).lower()

        # IoT 固件检测
        firmware_signatures = ["firmware", "u-boot", "squashfs", "jffs2", "cramfs", "ubifs"]
        if any(sig in file_info for sig in firmware_signatures):
            return ChallengeType.IOT

        # binwalk 快速检测
        binwalk_result = await self.engine.run_command(f"binwalk -q {file_path} 2>/dev/null | head -20")
        binwalk_info = str(binwalk_result).lower()
        if any(sig in binwalk_info for sig in ["squashfs", "jffs2", "firmware", "uimage"]):
            return ChallengeType.IOT

        # ELF/PE 二进制 (也检查扩展名, 防止 file 命令失败)
        ext = os.path.splitext(file_path)[1].lower()
        ext_binary = ext in (".exe", ".elf", ".dll", ".so", ".o", ".bin", "")
        is_binary = ext_binary or any(t in file_info for t in ["elf", "executable", "pe32", "mach-o", "ms windows", "pe32+"])
        if is_binary:
            # 检查危险函数 → PWN
            strings_result = await self.engine.run_command(
                f"strings {file_path} | grep -iE '(gets|scanf|strcpy|sprintf|system|execve)' | head -10"
            )
            dangerous = str(strings_result).strip()

            # 检查 flag 检查特征 → Reverse
            flag_result = await self.engine.run_command(
                f"strings {file_path} | grep -iE '(flag|correct|wrong|right|input|enter|password|key)' | head -10"
            )
            flag_hints = str(flag_result).strip()

            if dangerous and not flag_hints:
                return ChallengeType.PWN
            if flag_hints and not dangerous:
                return ChallengeType.REVERSE
            # 都有: 如果有 gets/strcpy 等明显溢出函数 → PWN
            if "gets" in dangerous or "strcpy" in dangerous:
                return ChallengeType.PWN
            return ChallengeType.REVERSE

        # Python/脚本文件
        if any(t in file_info for t in ["python", "script", "text"]):
            content_result = await self.engine.run_command(f"head -50 {file_path}")
            content = str(content_result).lower()
            # Web 检测: HTML/Flask/Django/FastAPI/Express
            web_hints = ["<!doctype html", "<html", "flask", "django", "fastapi",
                         "express", "routes", "app.get", "app.post", "request.",
                         "render_template", "url_for", "@app.route"]
            if any(h in content for h in web_hints):
                return ChallengeType.WEB
            crypto_hints = ["aes", "rsa", "des", "encrypt", "decrypt", "cipher", "hmac",
                            "sha", "md5", "prime", "mod", "pow(", "gmpy", "pycryptodome"]
            if any(h in content for h in crypto_hints):
                return ChallengeType.CRYPTO
            return ChallengeType.REVERSE

        # HTML 文件 → Web
        if any(t in file_info for t in ["html", "htm"]):
            return ChallengeType.WEB

        # 数据文件 / 未知类型 → Misc
        if any(t in file_info for t in ["data", "empty", "unknown"]):
            return ChallengeType.MISC

        # 默认归类为 Crypto (纯数据文件)
        return ChallengeType.CRYPTO

    # ─────────────────────────────────────
    # 主分析流程 (Agent 驱动)
    # ─────────────────────────────────────

    async def run(
        self,
        file_path: str,
        challenge_type: str = "auto",
        model_info: Optional[dict] = None,
        progress_callback=None,
        task_store: Optional[dict] = None,
        task_id: str = "",
        upload_dir: str = "",
        target_urls: list[str] = None,
        target_endpoints: list[str] = None,
    ) -> dict:
        """
        由 AI Agent 自主驱动的分析流水线。

        AI 自主决定调用哪些分析工具、以什么顺序分析，而不是执行固定的 5 阶段流程。
        task_store 是 _analysis_tasks[task_id] 引用，用于实时推送 agent 步骤。
        task_id 用于流式命令输出追踪。
        upload_dir / target_urls / target_endpoints 来自前端多文件上传和地址输入。
        """
        result = {
            "file_path": file_path,
            "challenge_type": challenge_type,
            "phases": {},
            "started_at": time.time(),
        }

        async def notify(phase: str, msg: str):
            if progress_callback:
                await progress_callback(phase, msg)

        try:
            await notify("detecting", "正在启动 AI 分析 Agent...")

            # 快速检测赛题类型 (仅用于显示)
            if challenge_type == "auto":
                try:
                    detected = await self.detect_type(file_path)
                    challenge_type = detected.value
                    result["challenge_type"] = challenge_type
                    result["phases"]["detect"] = {"type": challenge_type}
                    await notify("detecting", f"检测类型: {challenge_type}")
                except Exception:
                    pass

            # 无 API Key 则无法继续
            if not model_info or not model_info.get("api_key"):
                result["phases"]["ai"] = {"content": "", "error": "未配置 API Key, 请在 /config 页面添加"}
                result["completed_at"] = time.time()
                result["duration"] = result["completed_at"] - result["started_at"]
                return result

            await notify("ai_analysis", "AI Agent 正在自主分析...")

            # 收集初始文件信息 (给 agent 提供起点)
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            # 构建额外上下文: 目录文件清单 + 远程地址
            extra_context = ""
            if upload_dir and os.path.isdir(upload_dir):
                all_files = []
                extracted_files = []
                for root, _, fnames in os.walk(upload_dir):
                    for fname in fnames:
                        full = os.path.join(root, fname)
                        rel = os.path.relpath(full, upload_dir)
                        try:
                            sz = os.path.getsize(full)
                            all_files.append(f"  - {rel} ({sz} bytes)")
                        except Exception:
                            all_files.append(f"  - {rel}")
                        # 提取目录中的文件单独标记
                        if os.path.relpath(root, upload_dir).startswith("extracted"):
                            extracted_files.append(rel)
                if len(all_files) > 1:
                    extra_context += f"\n工作目录包含 {len(all_files)} 个文件:\n" + "\n".join(all_files[:30])
                    if len(all_files) > 30:
                        extra_context += f"\n  ... (共 {len(all_files)} 个文件, 仅显示前30)"
                    if extracted_files:
                        extra_context += f"\n\n注意: 其中 {len(extracted_files)} 个文件来自压缩包解压, 可以直接分析"

            if target_urls:
                extra_context += f"\n\n远程目标地址:"
                for u in target_urls:
                    extra_context += f"\n  - {u}"
            if target_endpoints:
                extra_context += f"\n\nAPI 接口:"
                for ep in target_endpoints:
                    extra_context += f"\n  - {ep}"

            # 使用推理-行动循环给 AI 完全控制权
            from app.agent.engine import run_agent

            sys_content = f"""你是 CTF 赛题分析专家，正在分析文件: {file_name}
                (路径: {file_path}, 大小: {file_size / 1024:.1f} KB, 推测类型: {challenge_type})

                你有以下工具可用:
                - file_info / check_protections / extract_strings — 本地文件分析
                - engine_analyze / engine_checksec / engine_run — 远程引擎深度分析
                - engine_decompile / engine_ropgadget — 反编译与 ROP
                - ida_functions / ida_decompile — IDA Pro 反编译
                - run_python — 执行 Python 代码 (z3 约束求解/解密)
                - read_file — 查看源代码/文本
                - search_web — 搜索技术资料
                - container_install(包名, apt/pip) — 自动安装缺失工具
                - run_command(命令) — 执行任意 shell 命令
                - download_file(URL) — 下载文件到工作目录

                提示: **所有工具已预装** (file/readelf/strings/checksec/pwntools/z3/32位库)，无需 container_install，直接使用即可。
                请按需自主选择工具进行分析，不要按固定顺序。完成分析后给出:
                1. 赛题类型和基本信息
                2. 漏洞/算法分析
                3. 完整的 exploit 脚本或求解代码
                4. Flag (如能获取)"""

            if extra_context:
                sys_content += "\n\n" + extra_context

            agent_messages = [
                {"role": "user", "content": sys_content + f"\n\n请分析文件 {file_name}，使用可用工具自主决定分析流程。"},
            ]

            agent_content_parts = []
            agent_phases = {}
            agent_steps = []
            step_counter = 0
            agent_stopped = False

            # 创建 hint 队列 + 步骤事件 + 停止事件 + 流式缓冲区
            import asyncio
            hint_queue: asyncio.Queue = asyncio.Queue()
            step_event = asyncio.Event()
            stop_event = asyncio.Event()
            if task_store is not None:
                task_store["hint_queue"] = hint_queue
                task_store["step_event"] = step_event
                task_store["stop_event"] = stop_event
                task_store["stream_buffer"] = []
                # 立即推送连接步骤
                task_store["agent_steps"] = [{"type": "thought", "content": "正在连接 AI 模型..."}]
                task_store["agent_step_count"] = 1
                step_event.set()

            # 设置命令流式输出上下文
            from app.agent.tools import _set_cmd_task_id
            if task_store:
                _set_cmd_task_id(task_id)

            async for chunk in run_agent(
                messages=agent_messages,
                provider=model_info["provider"] if model_info else "",
                model=model_info["model"] if model_info else "",
                api_key=model_info["api_key"] if model_info else "",
                base_url=model_info.get("base_url", "") if model_info else "",
                temperature=0.3,
                max_tokens=8192,
                file_path=file_path,
                hint_queue=hint_queue,
                stop_event=stop_event,
            ):
                try:
                    parsed = json.loads(chunk)
                    ctype = parsed.get("type", "")
                    content = parsed.get("content", "")

                    # 收集步骤用于前端展示
                    step = {"type": ctype}
                    if ctype == "thought":
                        step["content"] = content
                        await notify("ai_analysis", f"🤔 {content[:80]}")
                    elif ctype == "action":
                        step["name"] = parsed.get("name", "")
                        step["input"] = parsed.get("input", "")
                        await notify("tool_analysis", f"🔧 {step['name']}({step['input'][:50]})")
                    elif ctype == "observation":
                        step["content"] = content[:300]  # 只存摘要
                        step["full_length"] = len(content)
                        await notify("tool_analysis", f"📊 得到结果 ({len(content)} 字符)")
                    elif ctype == "text":
                        agent_content_parts.append(content)
                        step["content"] = content
                        await notify("ai_analysis", "✍️ 正在生成分析报告...")
                    elif ctype == "error":
                        logger.warning("Agent 错误: %s", content)
                        step["content"] = content

                    elif ctype == "hint":
                        step["content"] = content
                        await notify("ai_analysis", f"💡 收到用户提示: {content[:50]}")

                    elif ctype == "stream":
                        # 实时 token — 推送到 stream_buffer 供 WS 推送
                        if task_store is not None and content:
                            task_store["stream_buffer"].append(content)
                            step_event.set()  # 唤醒 WS 立即推送
                        continue  # 不添加到 agent_steps

                    elif ctype == "stopped":
                        agent_stopped = True
                        logger.info("Agent 被用户停止: %s", content)
                        break  # 退出 for 循环 (不再处理后续 chunk)

                    if ctype in ("thought", "action", "observation", "text", "error", "hint"):
                        agent_steps.append(step)
                        step_counter += 1
                        # 实时推送到 task_store 供 WebSocket 读取
                        if task_store is not None:
                            task_store["agent_steps"] = agent_steps.copy()
                            task_store["agent_step_count"] = step_counter
                            step_event.set()  # 立即通知 WS 有新步骤

                    agent_phases[ctype] = agent_phases.get(ctype, 0) + 1
                except json.JSONDecodeError:
                    pass

            full_content = "\n".join(agent_content_parts)
            result["phases"]["ai"] = {
                "content": full_content,
                "model": model_info.get("model", "") if model_info else "",
                "agent_stats": agent_phases,
                "agent_steps": agent_steps,
            }

            if agent_stopped:
                result["stopped"] = True
                logger.info("Agent 分析被用户停止, 保存部分结果")

            # 也保存一些静态信息供前端展示
            if os.path.exists(file_path):
                try:
                    file_result = await self.engine.run_command(f"file {file_path}")
                    result["phases"]["static"] = {
                        "binary_info": {"result": str(file_result)},
                    }
                except Exception:
                    pass

            result["completed_at"] = time.time()
            result["duration"] = result["completed_at"] - result["started_at"]
            return result

        except Exception as e:
            logger.exception("Agent 分析异常: %s", e)
            result["error"] = str(e)
            return result

    # ─────────────────────────────────────
    # 各阶段实现
    # ─────────────────────────────────────

    async def _phase_static(self, file_path: str, ctype: str) -> dict:
        """静态分析阶段"""
        tasks = {
            "binary_info": self.engine.analyze_binary(file_path),
            "checksec": self.engine.checksec(file_path),
        }

        if ctype == "iot":
            tasks["binwalk"] = self.engine.run_command(f"binwalk {file_path}")
            tasks["firmware_strings"] = self.engine.run_command(
                f"strings {file_path} | head -100"
            )

        results = {}
        for name, coro in tasks.items():
            try:
                results[name] = await coro
            except Exception as e:
                results[name] = {"error": str(e)}

        return results

    async def _phase_decompile(self, file_path: str, ctype: str) -> dict:
        """反编译阶段"""
        result = {}

        # 尝试 IDA Pro (如果可用)
        ida_available = await self.ida.is_available()
        if ida_available:
            result["source"] = "ida"
            functions = await self.ida.get_functions()
            result["functions"] = functions[:50]  # 前50个函数

            # 反编译 main 函数和其他关键函数
            key_funcs = [f for f in functions if f.get("name") in ("main", "_main", "vuln", "vulnerable", "check", "verify")]
            if not key_funcs and functions:
                key_funcs = functions[:5]  # 取前5个

            decompiled = {}
            for func in key_funcs:
                name = func.get("name", "unknown")
                code = await self.ida.decompile(name)
                decompiled[name] = code

            result["decompiled"] = decompiled
        else:
            # 回退到 Rizin
            result["source"] = "rizin"
            rizin_result = await self.engine.run_command(
                f"rizin -q -c 'aaa; s main; pdg' {file_path} 2>/dev/null"
            )
            result["decompiled"] = {"main": str(rizin_result)}

        return result

    async def _phase_tools(self, file_path: str, ctype: str) -> dict:
        """专项工具分析阶段"""
        result = {}

        if ctype == "pwn":
            result["ropgadget"] = await self.engine.ropgadget(file_path)
            result["strategy"] = await self.engine.suggest_strategy()

        elif ctype == "reverse":
            # strings + ltrace 提示
            result["strings"] = await self.engine.run_command(
                f"strings {file_path} | head -50"
            )

        elif ctype == "crypto":
            # 尝试读取源代码
            result["source_code"] = await self.engine.run_command(
                f"cat {file_path}"
            )

        elif ctype == "iot":
            result["binwalk_extract"] = await self.engine.run_command(
                f"binwalk -e -C /workspace/firmware_extract {file_path} 2>&1 | head -30"
            )
            result["extracted_listing"] = await self.engine.run_command(
                "find /workspace/firmware_extract -type f | head -50 2>/dev/null"
            )

        return result

    async def _phase_ai(self, ctype: str, collected_data: dict, model_info: dict) -> dict:
        """AI 深度分析阶段"""
        from app.model_router import model_router
        from app.model_router.prompts import (
            build_pwn_prompt,
            build_reverse_prompt,
            build_crypto_prompt,
            build_iot_prompt,
            build_general_prompt,
        )

        # 提取关键信息
        static = collected_data.get("static", {})
        decompile = collected_data.get("decompile", {})
        tools = collected_data.get("tools", {})

        binary_facts = static.get("binary_info", {})
        decompiled_code = ""
        if isinstance(decompile.get("decompiled"), dict):
            decompiled_code = "\n\n".join(
                f"// {name}\n{code}" for name, code in decompile["decompiled"].items()
            )
        else:
            decompiled_code = str(decompile.get("decompiled", ""))

        # 根据赛题类型构建 Prompt
        if ctype == "pwn":
            gadgets = str(tools.get("ropgadget", ""))
            messages = build_pwn_prompt(binary_facts, decompiled_code, gadgets)
        elif ctype == "reverse":
            strings_info = str(tools.get("strings", ""))
            messages = build_reverse_prompt(binary_facts, decompiled_code, strings_info)
        elif ctype == "crypto":
            source = str(tools.get("source_code", ""))
            messages = build_crypto_prompt({"algorithm": "auto-detect"}, source)
        elif ctype == "iot":
            firmware_info = {
                "extracted_files": str(tools.get("extracted_listing", "")),
            }
            messages = build_iot_prompt(firmware_info, binary_facts, decompiled_code)
        else:
            messages = build_general_prompt("请分析这个赛题", str(collected_data)[:5000])

        # 调用 AI 模型
        ai_response = await model_router.call_model(
            provider=model_info["provider"],
            model=model_info["model"],
            api_key=model_info["api_key"],
            messages=messages,
            base_url=model_info.get("base_url", ""),
        )

        return ai_response


# 全局单例
pipeline = AnalysisPipeline()
