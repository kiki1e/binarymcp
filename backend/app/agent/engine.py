"""
ReAct Agent 引擎 — 推理-行动循环

工作流程:
1. 接收用户消息 + 历史
2. 构建包含工具描述的 System Prompt
3. 调用 LLM, 模型输出 ReAct 格式 (Thought/Action/Observation)
4. 解析输出, 如果是 Action 则执行工具, 返回 Observation
5. 重复直到模型输出 Final Answer
"""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Optional

from app.model_router import model_router
from app.agent.tools import TOOLS, get_tool

logger = logging.getLogger(__name__)

# ── ReAct 系统提示 ──

REACT_SYSTEM_PROMPT = """你是一位 CTF 安全分析专家，擅长 PWN、逆向工程、密码学分析。
你有以下工具可以使用:

{tool_descriptions}

## 工作方式
请严格遵循以下格式回复, 每轮只输出其中一种:

### 格式 1: 调用工具
Thought: 你当前的思考过程
Action: 工具名称
Action Input: {{"参数名": "参数值"}}

### 格式 2: 给出最终答案
Thought: 总结分析过程
Final Answer: 最终答案 (包含详细分析和 exploit 脚本)

## 重要规则
- 每次只调用一个工具
- Action Input 必须是**严格有效的 JSON**, 用双引号
- 工具结果会以 Observation: 开头返回给你
- 用中文回答用户的问题
- 提供完整的 exploit 脚本或求解代码

## 示例
Thought: 我需要先检查这个文件的保护机制
Action: check_protections
Action Input: {{"file_path": "/workspace/challenges/target"}}

当工具返回结果后, 继续分析:
Thought: 分析工具返回的结果, 决定下一步
Action: 另一个工具 或 Final Answer

## 容器环境信息 (重要!)
- **所有以下工具已预装, 无需安装, 直接使用:**
  - 分析工具: file, readelf, strings, objdump, checksec, binwalk
  - 开发工具: python3, pwntools, z3-solver, gdb
  - 网络工具: curl, wget
- **32位库已预装** (libc6:i386, libc6-dbg:i386)
- **禁止执行 `container_install` 安装 pwntools/z3/32位库** — 它们已存在
- 只有确实缺少极罕见工具时才用 `container_install`
- 用 `run_command` 执行任意 shell 命令, 无需依赖远程引擎
- 用 `download_file` 下载远程依赖 (如 libc 版本)
- 工作目录在 /workspace, 分析的文件也在 /workspace 下
- 注意: IDA Pro (`ida_functions`, `ida_decompile`) 和引擎反编译 (`engine_decompile`) 通常不可用, 请直接用 `run_command` 配合 objdump/readelf/strings 分析
"""


def _build_tool_descriptions() -> str:
    lines = []
    for t in TOOLS:
        params = t.parameters.get("properties", {})
        param_desc = ", ".join(
            f"{name}: {info.get('description', '')}"
            for name, info in params.items()
        )
        lines.append(f"- {t.name}: {t.description} 参数: {param_desc}")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return REACT_SYSTEM_PROMPT.format(tool_descriptions=_build_tool_descriptions())


# ── ReAct 解析器 ──

# 兼容 "Action:" 和 "**Action:**" 等 Markdown 变体
_LABEL = r"\*{0,2}\s*"  # 可选加粗标记
ACTION_PATTERN = re.compile(
    rf"{_LABEL}Action:{_LABEL}\s*(.+?)\n\s*{_LABEL}Action\s+Input:{_LABEL}\s*(\{{.*?\}}|`.*?`|.+?)(?=\n\s*(?:{_LABEL}(?:Thought|Observation|Final Answer)|$))",
    re.DOTALL,
)
FINAL_ANSWER_PATTERN = re.compile(
    rf"{_LABEL}Final\s+Answer:{_LABEL}\s*(.+?)(?:\n\s*(?:{_LABEL}(?:Thought|Action)|$)|$)",
    re.DOTALL,
)
THOUGHT_PATTERN = re.compile(
    rf"{_LABEL}Thought:{_LABEL}\s*(.+?)(?=\n\s*(?:{_LABEL}(?:Action|Final Answer)|$))",
    re.DOTALL,
)


def _clean_json(raw: str) -> str:
    """去除 markdown 粗体标记和反引号, 提取纯净 JSON 字符串"""
    raw = raw.strip()
    raw = raw.strip("`").strip()
    raw = re.sub(r'^\s*\*+\s*', '', raw)  # 去除开头的 ** 和空格
    raw = re.sub(r'\s*\*+\s*$', '', raw)  # 去除结尾的 ** 和空格
    return raw.strip()


def _parse_action(text: str) -> Optional[dict]:
    """从模型输出中解析 Action (主解析 + 行级回退)"""
    # 主解析: 正则
    m = ACTION_PATTERN.search(text)
    if m:
        action_name = m.group(1).strip()
        action_input_raw = m.group(2).strip()
        action_input_raw = _clean_json(action_input_raw)
        try:
            action_input = json.loads(action_input_raw)
        except json.JSONDecodeError:
            # 尝试从 raw text 中提取 JSON 对象
            json_match = re.search(r'\{.*?\}', action_input_raw, re.DOTALL)
            if json_match:
                try:
                    action_input = json.loads(json_match.group())
                except (json.JSONDecodeError, ValueError):
                    action_input = {"input": action_input_raw}
            else:
                action_input = {"input": action_input_raw}
        return {"name": action_name, "input": action_input}

    # 回退: 逐行解析 (忽略空格和 markdown 标记)
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines):
        # 匹配 "Action:" 行
        if re.match(r"\*{0,2}\s*Action:\s*\*{0,2}\s*(\S+)", line):
            m = re.match(r"\*{0,2}\s*Action:\s*\*{0,2}\s*(\S+)", line)
            if m:
                action_name = m.group(1)
                # 找后续行中的 Action Input:
                for j in range(i + 1, min(i + 5, len(lines))):
                    input_line = lines[j]
                    if "Action Input:" in input_line or "Action_Input:" in input_line:
                        # 提取 JSON 部分
                        raw = input_line.split(":", 1)[1].strip() if ":" in input_line else ""
                        raw = _clean_json(raw)
                        try:
                            action_input = json.loads(raw)
                        except (json.JSONDecodeError, ValueError):
                            action_input = {"input": raw}
                        logger.info("回退解析成功: %s -> %s", action_name, action_input)
                        return {"name": action_name, "input": action_input}
                # 如果没找到 Action Input 行, 用整段文本匹配
                remaining = "\n".join(lines[i + 1:])
                # 尝试提取 JSON 块
                json_match = re.search(r"\{.*?\}", remaining, re.DOTALL)
                if json_match:
                    try:
                        action_input = json.loads(json_match.group())
                        return {"name": action_name, "input": action_input}
                    except json.JSONDecodeError:
                        pass
                return {"name": action_name, "input": {"input": remaining[:200]}}

    logger.warning("Agent 输出中未找到 Action (共 %d 行, 前200字符: %s)", len(lines), text[:200])
    return None


def _parse_final_answer(text: str) -> Optional[str]:
    m = FINAL_ANSWER_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


def _parse_thought(text: str) -> Optional[str]:
    m = THOUGHT_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


# ── Agent 执行 ──

async def run_agent(
        messages: list[dict],
        provider: str,
        model: str,
        api_key: str,
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        file_path: str = "",
        hint_queue: Optional[asyncio.Queue] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[str, None]:
        """
        ReAct Agent 主循环 (流式, 无限轮, 直到 Final Answer 或收到停止信号)

        逐块 yield:
          {"type": "stream", "content": "..."}  — 实时 token
          {"type": "thought", "content": "..."}
          {"type": "action", "name": "...", "input": "..."}
          {"type": "observation", "content": "..."}
          {"type": "text", "content": "..."}
          {"type": "hint", "content": "..."}
          {"type": "stopped", "content": "..."}
        """
        # 构建带工具的系统提示
        sys_prompt = _build_system_prompt()
        sys_prompt += "\n\n分析步数无上限, 请充分分析直到得出最终答案或 Flag。"
        if file_path:
            sys_prompt += f"\n\n当前分析的二进制文件路径: {file_path}\n"

        # 消息历史
        agent_messages = [{"role": "system", "content": sys_prompt}]
        for msg in messages:
            if msg.get("role") != "system":
                agent_messages.append(msg)

        if file_path:
            agent_messages.append({
                "role": "user",
                "content": f"[系统] 当前分析的二进制文件路径: {file_path}",
            })

        iteration = 0

        while True:
            iteration += 1
            logger.debug("Agent iteration %d", iteration)

            # 检查停止信号 (迭代间)
            if stop_event is not None and stop_event.is_set():
                logger.info("Agent 收到停止信号, 在第 %d 轮退出", iteration)
                yield json.dumps({"type": "stopped", "content": f"用户在第 {iteration} 轮停止分析"})
                return

            # 检查用户提示 (迭代间)
            if hint_queue is not None:
                try:
                    while not hint_queue.empty():
                        hint = hint_queue.get_nowait()
                        agent_messages.append({"role": "user", "content": f"【用户提示】{hint}"})
                        yield json.dumps({"type": "hint", "content": hint})
                        logger.info("Agent 收到用户提示: %s", hint[:50])
                except asyncio.QueueEmpty:
                    pass

            # ── 流式调用 LLM ──
            full_content = ""
            stream_interrupted = False

            try:
                stream = model_router.call_model_stream(
                    provider=provider, model=model, api_key=api_key,
                    messages=agent_messages, base_url=base_url,
                    temperature=temperature, max_tokens=max_tokens,
                )
                async for token in stream:
                    # 确保 token 是字符串 (某些模型可能返回非字符串 content)
                    if not isinstance(token, str):
                        token = str(token)

                    # 检查 token 是否是错误 JSON
                    try:
                        parsed = json.loads(token)
                        if isinstance(parsed, dict) and "error" in parsed:
                            logger.warning("Agent 第%d轮流式错误: %s", iteration, parsed["error"])
                            yield json.dumps({"type": "error", "content": parsed["error"]})
                            return
                    except (json.JSONDecodeError, TypeError):
                        pass

                    full_content += token
                    yield json.dumps({"type": "stream", "content": token})

                    # 流式过程中检查停止信号
                    if stop_event is not None and stop_event.is_set():
                        logger.info("Agent 第%d轮被用户中断", iteration)
                        stream_interrupted = True
                        break

                    # 流式过程中收集 hint (不中断生成, 下一轮注入)
                    if hint_queue is not None:
                        try:
                            while not hint_queue.empty():
                                hint = hint_queue.get_nowait()
                                agent_messages.append({"role": "user", "content": f"【用户提示】{hint}"})
                                yield json.dumps({"type": "hint", "content": hint})
                                logger.info("Agent 收到用户提示(流式): %s", hint[:50])
                        except asyncio.QueueEmpty:
                            pass

            except Exception as e:
                logger.error("Agent 第%d轮流式调用失败: %s", iteration, e)
                yield json.dumps({"type": "error", "content": str(e)})
                return

            if stream_interrupted:
                yield json.dumps({"type": "stopped", "content": f"用户在第 {iteration} 轮停止分析"})
                return

            if not full_content.strip():
                logger.warning("Agent 第%d轮流式返回空内容", iteration)
                yield json.dumps({"type": "error", "content": "模型返回空响应"})
                return

            logger.debug("Agent 第%d轮完成 (%d字符)", iteration, len(full_content))

            # 检查是否有 Final Answer
            final_answer = _parse_final_answer(full_content)
            if final_answer:
                thought = _parse_thought(full_content)
                if thought:
                    yield json.dumps({"type": "thought", "content": thought})
                yield json.dumps({"type": "text", "content": final_answer})
                return

            # 检查是否有 Action
            action = _parse_action(full_content)
            if action:
                thought = _parse_thought(full_content)
                if thought:
                    yield json.dumps({"type": "thought", "content": thought})
                yield json.dumps({
                    "type": "action",
                    "name": action["name"],
                    "input": json.dumps(action["input"], ensure_ascii=False),
                })

                # 执行工具
                tool = get_tool(action["name"])
                if tool:
                    params = action.get("input", {})
                    if isinstance(params, dict) and "input" in params and len(params) == 1 and isinstance(params["input"], str):
                        try:
                            parsed = json.loads(params["input"])
                            if isinstance(parsed, dict):
                                params = parsed
                        except (json.JSONDecodeError, ValueError):
                            pass
                    try:
                        result = await tool.run(**params)
                    except TypeError as e:
                        result = f"参数错误: {e}"
                    except Exception as e:
                        result = f"执行错误: {e}"
                else:
                    result = f"未知工具: {action['name']}，可用工具: {[t.name for t in TOOLS]}"

                yield json.dumps({"type": "observation", "content": result[:2000]})

                # 将工具结果加入消息历史
                agent_messages.append({"role": "assistant", "content": full_content})
                agent_messages.append({"role": "user", "content": f"Observation:\n{result[:2000]}"})
            else:
                yield json.dumps({"type": "text", "content": full_content})
                return


async def run_agent_stream(
    messages: list[dict],
    provider: str,
    model: str,
    api_key: str,
    base_url: str = "",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    file_path: str = "",
) -> AsyncGenerator[str, None]:
    """
    流式 ReAct Agent — 逐块 yield 文本内容 (SSE 友好)
    """
    async for chunk in run_agent(
        messages=messages,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        file_path=file_path,
    ):
        yield chunk
