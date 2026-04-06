"""
赛题分析流水线

编排 engine (pwnmcp) 工具层 + IDA Pro + AI 模型,
实现 CTF 赛题的自动化分析。
"""

import asyncio
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
    """与 pwnmcp engine 容器通信的客户端"""

    def __init__(self):
        self._client = httpx.AsyncClient(base_url=ENGINE_URL, timeout=120)

    async def close(self):
        await self._client.aclose()

    async def _call_tool(self, tool_name: str, params: dict) -> dict:
        """通过 MCP SSE 调用 engine 的工具 (简化: 直接 HTTP POST)"""
        # 注意: MCP SSE 协议需要通过 JSON-RPC 调用
        # 这里使用 MCP SDK 的 client 方式
        try:
            r = await self._client.post(
                "/mcp/v1/tools/call",
                json={"name": tool_name, "arguments": params},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error("Engine 工具调用失败 [%s]: %s", tool_name, e)
            return {"error": str(e)}

    async def analyze_binary(self, file_path: str) -> dict:
        return await self._call_tool("analyze_binary", {"path": file_path})

    async def checksec(self, file_path: str) -> dict:
        return await self._call_tool("checksec", {"path": file_path})

    async def ropgadget(self, file_path: str) -> dict:
        return await self._call_tool("ropgadget", {"path": file_path})

    async def suggest_strategy(self, file_path: str) -> dict:
        return await self._call_tool("suggest_strategy", {"path": file_path})

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

        # ELF/PE 二进制
        is_binary = any(t in file_info for t in ["elf", "executable", "pe32", "mach-o"])
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
            crypto_hints = ["aes", "rsa", "des", "encrypt", "decrypt", "cipher", "hmac",
                            "sha", "md5", "prime", "mod", "pow(", "gmpy", "pycryptodome"]
            if any(h in content for h in crypto_hints):
                return ChallengeType.CRYPTO
            return ChallengeType.REVERSE

        # 默认归类为 Crypto (纯数据文件)
        return ChallengeType.CRYPTO

    # ─────────────────────────────────────
    # 主分析流程
    # ─────────────────────────────────────

    async def run(
        self,
        file_path: str,
        challenge_type: str = "auto",
        model_info: Optional[dict] = None,
        progress_callback=None,
    ) -> dict:
        """
        执行完整分析流水线。

        Args:
            file_path: 二进制文件路径
            challenge_type: 赛题类型 (auto 自动检测)
            model_info: {"provider", "model", "api_key"} 用于 AI 分析
            progress_callback: async fn(phase, message) 进度回调

        Returns:
            分析结果字典
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
            # Phase 0: 赛题类型检测
            if challenge_type == "auto":
                await notify("detecting", "正在检测赛题类型...")
                detected = await self.detect_type(file_path)
                challenge_type = detected.value
                result["challenge_type"] = challenge_type
                result["phases"]["detect"] = {"type": challenge_type}
                await notify("detecting", f"检测结果: {challenge_type}")

            # Phase 1: 静态分析
            await notify("static", "正在进行静态分析...")
            static_result = await self._phase_static(file_path, challenge_type)
            result["phases"]["static"] = static_result

            # Phase 2: 反编译
            await notify("decompiling", "正在反编译...")
            decompile_result = await self._phase_decompile(file_path, challenge_type)
            result["phases"]["decompile"] = decompile_result

            # Phase 3: 专项工具分析
            await notify("tool_analysis", "正在运行专项分析工具...")
            tool_result = await self._phase_tools(file_path, challenge_type)
            result["phases"]["tools"] = tool_result

            # Phase 4: AI 分析 (如果提供了模型信息)
            if model_info:
                await notify("ai_analysis", "正在进行 AI 深度分析...")
                ai_result = await self._phase_ai(
                    challenge_type, result["phases"], model_info
                )
                result["phases"]["ai"] = ai_result

            result["completed_at"] = time.time()
            result["duration"] = result["completed_at"] - result["started_at"]
            return result

        except Exception as e:
            logger.exception("分析流水线异常: %s", e)
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
            result["strategy"] = await self.engine.suggest_strategy(file_path)

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
