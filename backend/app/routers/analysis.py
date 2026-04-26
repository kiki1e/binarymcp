"""
赛题分析路由

上传二进制文件, 启动分析流水线, 查看分析结果, AI 对话 (含流式).
"""

import asyncio
import json
import logging
import os
import shutil
import socket
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import async_session, get_db
from app.models import Leak
from app.model_router import model_router
from app.model_router.providers import PROVIDER_ADAPTERS, OpenAICompatAdapter
from app.analysis import pipeline, ChallengeType
from app.session.store import SessionStore
from app.agent import run_agent, run_agent_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])

WORKSPACE = os.getenv("WORKSPACE_DIR", "/workspace")
SESSION_STORE = SessionStore(WORKSPACE)

# 内存中的分析任务状态
_analysis_tasks: dict[str, dict] = {}


class StartAnalysisRequest(BaseModel):
    challenge_type: str = "auto"
    model_provider: str = ""
    model_name: str = ""
    api_key: str = ""
    base_url: str = ""
    analysis_depth: str = "standard"
    target_urls: list[str] = []
    target_endpoints: list[str] = []


class AnalysisStatus(BaseModel):
    task_id: str
    status: str
    phase: str
    message: str
    challenge_type: str
    progress: float
    result: dict | None
    target_urls: list[str] = []
    target_endpoints: list[str] = []


class NcConnectRequest(BaseModel):
    target: str
    input_data: str = ""
    timeout: int = 10


# ── 原有上传/分析接口 ──

@router.post("/upload")
async def upload_challenge(
    files: list[UploadFile] = File(...),
    _: str = Depends(require_auth),
):
    task_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join(WORKSPACE, "challenges", task_id)
    os.makedirs(upload_dir, exist_ok=True)

    saved_files = []
    extracted_archives = []

    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 尝试设为可执行 (仅对 ELF/PE 等二进制有效)
        try:
            os.chmod(file_path, 0o755)
        except Exception:
            pass

        is_archive = False
        ext = os.path.splitext(file.filename)[1].lower()
        second_ext = os.path.splitext(os.path.splitext(file.filename)[0])[1].lower()

        # 压缩包自动解压
        extract_dir = None
        extracted_files = []

        if ext == ".zip":
            is_archive = True
            extract_dir = os.path.join(upload_dir, file.filename.replace(".zip", ""))
            try:
                import zipfile
                with zipfile.ZipFile(file_path) as zf:
                    for info in zf.infolist():
                        dest = os.path.normpath(os.path.join(extract_dir, info.filename))
                        if not dest.startswith(os.path.normpath(extract_dir)):
                            raise ValueError(f"Path traversal attempt: {info.filename}")
                    zf.extractall(extract_dir)
                for root, _, fnames in os.walk(extract_dir):
                    for fname in fnames:
                        extracted_files.append(os.path.join(root, fname))
                logger.info("解压 %s → %s (%d 文件)", file.filename, extract_dir, len(extracted_files))
            except Exception as e:
                logger.warning("解压 %s 失败: %s", file.filename, e)
                extracted_files = []

        elif ext in (".tar", ".gz", ".tgz") or second_ext in (".tar",):
            is_archive = True
            base = file.filename.replace(".tar.gz", "").replace(".tgz", "").replace(".tar", "").replace(".gz", "")
            extract_dir = os.path.join(upload_dir, base)
            try:
                import tarfile
                with tarfile.open(file_path, "r:*") as tf:
                    tf.extractall(extract_dir, filter="data")
                for root, _, fnames in os.walk(extract_dir):
                    for fname in fnames:
                        extracted_files.append(os.path.join(root, fname))
                logger.info("解压 %s → %s (%d 文件)", file.filename, extract_dir, len(extracted_files))
            except Exception as e:
                logger.warning("解压 %s 失败: %s", file.filename, e)
                extracted_files = []

        saved_files.append({
            "filename": file.filename,
            "file_path": file_path,
            "size": len(content),
            "is_archive": is_archive,
        })

        if extracted_files:
            extracted_archives.append({
                "archive": file.filename,
                "extract_dir": extract_dir,
                "files": extracted_files,
            })

    return {
        "task_id": task_id,
        "files": saved_files,
        "extracted": extracted_archives,
    }


@router.post("/start/{task_id}", response_model=AnalysisStatus)
async def start_analysis(
    task_id: str,
    body: StartAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    upload_dir = os.path.join(WORKSPACE, "challenges", task_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(404, f"Task {task_id} not found")

    files = os.listdir(upload_dir)
    if not files:
        raise HTTPException(400, "No file uploaded for this task")

    file_path = os.path.join(upload_dir, files[0])

    model_info = None
    # 优先使用请求中直接传入的 API 配置 (来自前端 localStorage)
    if body.api_key and body.model_name:
        model_info = {
            "provider": body.model_provider or "custom",
            "model": body.model_name,
            "api_key": body.api_key,
            "base_url": body.base_url or "",
        }
    elif body.model_provider and body.model_name:
        valid_keys = (await db.execute(
            select(Leak).where(
                Leak.key_status == "valid",
                (Leak.verified_provider == body.model_provider) |
                (Leak.provider == body.model_provider),
            )
        )).scalars().all()
        if valid_keys:
            model_info = {
                "provider": body.model_provider,
                "model": body.model_name,
                "api_key": valid_keys[0].raw_key,
                "base_url": valid_keys[0].verified_url or "",
            }
    else:
        valid_keys = (await db.execute(
            select(Leak).where(Leak.key_status == "valid")
        )).scalars().all()
        if valid_keys:
            available = []
            for k in valid_keys[:10]:
                provider = k.verified_provider or k.provider
                try:
                    models = await model_router.list_models_for_key(
                        provider, k.raw_key, k.verified_url or ""
                    )
                    available.append({
                        "provider": provider,
                        "api_key": k.raw_key,
                        "base_url": k.verified_url or "",
                        "models": [m["id"] for m in models],
                    })
                except Exception:
                    continue
            if available:
                task_type_map = {
                    "pwn": "vuln_identify",
                    "reverse": "deep_reverse",
                    "crypto": "crypto_solve",
                    "iot": "iot_firmware",
                    "web": "web_analyze",
                    "misc": "general",
                    "auto": "general",
                }
                task_type = task_type_map.get(body.challenge_type, "general")
                selected = await model_router.select_model(task_type, available)
                if selected:
                    model_info = selected

    _analysis_tasks[task_id] = {
        "status": "running",
        "phase": "pending",
        "message": "分析任务已启动",
        "challenge_type": body.challenge_type,
        "progress": 0.0,
        "result": None,
        "agent_steps": [],
        "agent_step_count": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target_urls": body.target_urls,
        "target_endpoints": body.target_endpoints,
    }

    async def _run():
        try:
            async def progress_cb(phase, msg):
                phase_progress = {
                    "detecting": 0.1,
                    "static": 0.3,
                    "decompiling": 0.5,
                    "tool_analysis": 0.7,
                    "ai_analysis": 0.85,
                    "completed": 1.0,
                }
                _analysis_tasks[task_id]["phase"] = phase
                _analysis_tasks[task_id]["message"] = msg
                _analysis_tasks[task_id]["progress"] = phase_progress.get(phase, 0.5)

            result = await pipeline.run(
                file_path=file_path,
                upload_dir=upload_dir,
                challenge_type=body.challenge_type,
                model_info=model_info,
                progress_callback=progress_cb,
                task_store=_analysis_tasks[task_id],
                task_id=task_id,
                target_urls=body.target_urls,
                target_endpoints=body.target_endpoints,
            )
            # 检查结果中是否有错误
            ai_phase = result.get("phases", {}).get("ai", {})
            if result.get("stopped"):
                _analysis_tasks[task_id]["status"] = "stopped"
                _analysis_tasks[task_id]["message"] = "用户已停止分析"
            elif result.get("error") or ai_phase.get("error"):
                _analysis_tasks[task_id]["status"] = "failed"
                _analysis_tasks[task_id]["message"] = result.get("error") or ai_phase.get("error", "")
            else:
                _analysis_tasks[task_id]["status"] = "completed"
            _analysis_tasks[task_id]["phase"] = "completed"
            _analysis_tasks[task_id]["progress"] = 1.0
            _analysis_tasks[task_id]["result"] = result
            _analysis_tasks[task_id]["challenge_type"] = result.get("challenge_type", body.challenge_type)
        except Exception as e:
            logger.exception("分析任务失败: %s", e)
            _analysis_tasks[task_id]["status"] = "failed"
            _analysis_tasks[task_id]["message"] = str(e)

    asyncio.create_task(_run())

    return AnalysisStatus(
        task_id=task_id,
        status="running",
        phase="pending",
        message="分析任务已启动",
        challenge_type=body.challenge_type,
        progress=0.0,
        result=None,
        target_urls=body.target_urls,
        target_endpoints=body.target_endpoints,
    )


@router.get("/{task_id}", response_model=AnalysisStatus)
async def get_analysis_status(
    task_id: str,
    _: str = Depends(require_auth),
):
    task = _analysis_tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return AnalysisStatus(
        task_id=task_id,
        status=task["status"],
        phase=task["phase"],
        message=task["message"],
        challenge_type=task["challenge_type"],
        progress=task["progress"],
        result=task["result"],
        target_urls=task.get("target_urls", []),
        target_endpoints=task.get("target_endpoints", []),
    )


@router.get("")
async def list_analyses(_: str = Depends(require_auth)):
    return {
        "tasks": [
            {
                "task_id": tid,
                "status": t["status"],
                "phase": t["phase"],
                "challenge_type": t["challenge_type"],
                "progress": t["progress"],
                "started_at": t.get("started_at"),
                "target_urls": t.get("target_urls", []),
            }
            for tid, t in _analysis_tasks.items()
        ]
    }


# ── 非流式 AI 对话 (原有) ──

class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    session_id: str = ""


@router.post("/chat")
async def chat_with_ai(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """非流式 AI 对话"""
    return await _resolve_and_call(body, db)


# ── 流式 AI 对话 (SSE) ──

class ChatStreamRequest(BaseModel):
    messages: list[dict]
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    session_id: str = ""


@router.post("/chat/stream")
async def chat_stream_ai(
    body: ChatStreamRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """流式 AI 对话 (SSE)"""
    provider = body.provider
    api_key = body.api_key
    base_url = body.base_url
    model = body.model

    logger.info("Chat stream request: provider=%s model=%s", provider, model)

    # 如果未提供完整配置, 从数据库自动选择
    if not api_key or not model:
        resolved = await _resolve_model(body.messages, db)
        if resolved:
            provider = resolved["provider"]
            api_key = resolved["api_key"]
            base_url = resolved["base_url"]
            model = resolved["model"]

    if not api_key:
        raise HTTPException(400, "无可用的 API Key, 请先在配置页面添加")

    session_id = body.session_id

    # 保存用户消息到会话
    if session_id:
        user_msg = body.messages[-1] if body.messages else {"role": "user", "content": ""}
        SESSION_STORE.add_message(session_id, "user", user_msg.get("content", ""))

    async def _stream():
        # 发送元信息
        meta = json.dumps({"type": "meta", "provider": provider, "model": model})
        yield f"data: {meta}\n\n"

        full_content = ""

        try:
            from app.model_router.providers import PROVIDER_ADAPTERS, OpenAICompatAdapter

            if provider not in PROVIDER_ADAPTERS and base_url:
                adapter = OpenAICompatAdapter(provider, base_url)
                async for chunk in adapter.chat_stream(
                    client=model_router._client,
                    api_key=api_key,
                    model=model,
                    messages=body.messages,
                    base_url=base_url,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                ):
                    if chunk.startswith('{"error"'):
                        yield f"data: {chunk}\n\n"
                        return
                    full_content += chunk
                    data = json.dumps({"type": "chunk", "content": chunk})
                    yield f"data: {data}\n\n"
            else:
                async for chunk in model_router.call_model_stream(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    messages=body.messages,
                    base_url=base_url,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                ):
                    if chunk.startswith('{"error"'):
                        yield f"data: {chunk}\n\n"
                        return
                    full_content += chunk
                    data = json.dumps({"type": "chunk", "content": chunk})
                    yield f"data: {data}\n\n"
        except Exception as e:
            logger.exception("流式对话错误: %s", e)
            err = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {err}\n\n"
            return

        # 保存助手回复到会话
        if session_id and full_content:
            SESSION_STORE.add_message(session_id, "assistant", full_content)

        # 完成信号
        done = json.dumps({"type": "done", "content": full_content})
        yield f"data: {done}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 共享逻辑 ──

async def _resolve_model(messages: list[dict], db) -> dict | None:
    """从数据库自动选择模型"""
    valid_keys = (await db.execute(
        select(Leak).where(Leak.key_status == "valid")
    )).scalars().all()
    available = []
    for k in valid_keys[:10]:
        p = k.verified_provider or k.provider
        try:
            models = await model_router.list_models_for_key(
                p, k.raw_key, k.verified_url or ""
            )
            available.append({
                "provider": p,
                "api_key": k.raw_key,
                "base_url": k.verified_url or "",
                "models": [m["id"] for m in models],
            })
        except Exception:
            continue
    selected = await model_router.select_model("general", available)
    return selected


async def _resolve_and_call(body: ChatRequest, db) -> dict:
    """解析配置并调用模型 (非流式)"""
    provider = body.provider
    api_key = body.api_key
    base_url = body.base_url
    model = body.model

    if not api_key or not model:
        selected = await _resolve_model(body.messages, db)
        if selected:
            provider = selected["provider"]
            api_key = selected["api_key"]
            base_url = selected["base_url"]
            model = selected["model"]

    if not api_key:
        raise HTTPException(400, "无可用的 API Key, 请先在 /config 页面添加")

    if provider not in PROVIDER_ADAPTERS and base_url:
        adapter = OpenAICompatAdapter(provider, base_url)
        try:
            result = await adapter.chat(
                client=model_router._client,
                api_key=api_key,
                model=model,
                messages=body.messages,
                base_url=base_url,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        except Exception as e:
            raise HTTPException(502, str(e))
    else:
        result = await model_router.call_model(
            provider=provider,
            model=model,
            api_key=api_key,
            messages=body.messages,
            base_url=base_url,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )

    if "error" in result:
        raise HTTPException(502, result["error"])

    # 保存到会话
    session_id = body.session_id
    if session_id:
        if body.messages:
            user_msg = body.messages[-1]
            SESSION_STORE.add_message(session_id, "user", user_msg.get("content", ""))
        SESSION_STORE.add_message(session_id, "assistant", result.get("content", ""))

    return result


# ── 用户提示 (Agent 交互) ──

class HintRequest(BaseModel):
    hint: str


@router.post("/{task_id}/hint")
async def send_hint(
    task_id: str,
    body: HintRequest,
    _: str = Depends(require_auth),
):
    """在 Agent 分析过程中发送提示/思路"""
    task = _analysis_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "running":
        raise HTTPException(400, "Task is not running")

    hint_queue = task.get("hint_queue")
    if not hint_queue:
        raise HTTPException(400, "Agent 尚未就绪，请稍后再试")

    await hint_queue.put(body.hint)
    logger.info("用户提示已发送到 task %s: %s", task_id, body.hint[:50])
    return {"success": True, "message": "提示已发送给 AI"}


@router.post("/{task_id}/stop")
async def stop_analysis(
    task_id: str,
    _: str = Depends(require_auth),
):
    """停止正在运行的 Agent 分析"""
    task = _analysis_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "running":
        raise HTTPException(400, "Task is not running")

    stop_event = task.get("stop_event")
    if not stop_event:
        raise HTTPException(400, "Agent 尚未就绪，请稍后再试")

    stop_event.set()
    logger.info("用户请求停止分析 task %s", task_id)
    return {"success": True, "message": "正在停止 AI 分析..."}


@router.post("/{task_id}/nc-connect")
async def nc_connect(
    task_id: str,
    body: NcConnectRequest,
    _: str = Depends(require_auth),
):
    """通过系统 nc 命令连接远程靶机，发送数据并返回响应"""
    # 解析 target: "nc host port" 或 "host port"
    parts = body.target.strip().split()
    if len(parts) >= 1 and parts[0] == "nc":
        parts = parts[1:]
    if len(parts) < 2:
        return {"error": "格式错误，请使用: host port 或 nc host port"}

    host = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        return {"error": f"端口号无效: {parts[1]}"}

    logger.info("nc-connect: 连接 %s:%d (task %s)", host, port, task_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/nc", "-w", str(body.timeout), host, str(port),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 发送数据（如果有）
        input_data = body.input_data.encode() if body.input_data else b""
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_data), timeout=body.timeout + 5
        )

        result = stdout.decode(errors="replace")
        if stderr:
            error_msg = stderr.decode(errors="replace").strip()
            if error_msg:
                logger.warning("nc-connect stderr: %s", error_msg)

        logger.info("nc-connect: 收到 %d 字节", len(result))
        return {"output": result}

    except asyncio.TimeoutError:
        return {"output": "", "error": "连接超时"}
    except FileNotFoundError:
        return {"output": "", "error": "系统 nc 命令不可用"}
    except Exception as e:
        logger.exception("nc-connect 错误: %s", e)
        return {"output": "", "error": str(e)}


# ── WebSocket 进度推送 (原有) ──

# ── ReAct Agent 模式 ──

class AgentRequest(BaseModel):
    messages: list[dict]
    file_path: str = ""
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    session_id: str = ""


@router.post("/agent")
async def agent_analyze(
    body: AgentRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """ReAct Agent 分析 — 非流式"""
    provider = body.provider
    api_key = body.api_key
    base_url = body.base_url
    model = body.model

    if not api_key or not model:
        selected = await _resolve_model(body.messages, db)
        if selected:
            provider = selected["provider"]
            api_key = selected["api_key"]
            base_url = selected["base_url"]
            model = selected["model"]

    if not api_key:
        raise HTTPException(400, "无可用的 API Key")

    results = []
    async for chunk in run_agent(
        messages=body.messages,
        file_path=body.file_path,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    ):
        results.append(chunk)

    return {"result": results}


@router.post("/agent/stream")
async def agent_analyze_stream(
    body: AgentRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """ReAct Agent 分析 — 流式 SSE"""
    provider = body.provider
    api_key = body.api_key
    base_url = body.base_url
    model = body.model

    if not api_key or not model:
        selected = await _resolve_model(body.messages, db)
        if selected:
            provider = selected["provider"]
            api_key = selected["api_key"]
            base_url = selected["base_url"]
            model = selected["model"]

    if not api_key:
        raise HTTPException(400, "无可用的 API Key")

    session_id = body.session_id
    if session_id:
        user_msg = body.messages[-1] if body.messages else {"role": "user", "content": ""}
        SESSION_STORE.add_message(session_id, "user", user_msg.get("content", ""))

    async def _stream():
        meta = json.dumps({"type": "meta", "provider": provider, "model": model, "mode": "agent"})
        yield f"data: {meta}\n\n"

        final_content = ""

        async for chunk in run_agent(
            messages=body.messages,
            file_path=body.file_path,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        ):
            yield f"data: {chunk}\n\n"
            try:
                parsed = json.loads(chunk)
                if parsed.get("type") == "text":
                    final_content += parsed.get("content", "")
            except json.JSONDecodeError:
                pass

        if session_id and final_content:
            SESSION_STORE.add_message(session_id, "assistant", final_content)

        done = json.dumps({"type": "done", "content": final_content})
        yield f"data: {done}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── WebSocket 进度推送 (含实时 Agent 步骤) ──

@router.get("/{task_id}/diagnose")
async def diagnose_network(task_id: str, _: str = Depends(require_auth)):
    """诊断 API 连接问题"""
    results = {}

    # 检查 task 配置
    task = _analysis_tasks.get(task_id)
    if task and task.get("result") and task["result"].get("phases", {}).get("ai", {}).get("error"):
        results["model_error"] = task["result"]["phases"]["ai"]["error"]

    # DNS 解析测试
    for host in ["api.deepseek.com", "api.openai.com", "api.anthropic.com"]:
        try:
            socket.getaddrinfo(host, 443)
            results[f"dns_{host}"] = "ok"
        except Exception as e:
            results[f"dns_{host}"] = f"fail: {e}"

    # 环境变量
    results["http_proxy"] = os.environ.get("http_proxy", "(not set)")
    results["https_proxy"] = os.environ.get("https_proxy", "(not set)")
    results["no_proxy"] = os.environ.get("no_proxy", "(not set)")

    return results

@router.websocket("/{task_id}/ws")
async def analysis_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        last_phase = ""
        last_step_count = 0
        last_stream_pos = 0
        while True:
            task = _analysis_tasks.get(task_id)
            if not task:
                await websocket.send_json({"error": "Task not found"})
                break

            # 发送阶段变更
            if task["phase"] != last_phase:
                await websocket.send_json({
                    "task_id": task_id,
                    "status": task["status"],
                    "phase": task["phase"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "target_urls": task.get("target_urls", []),
                })
                last_phase = task["phase"]

            # 发送新的 agent 步骤
            current_count = task.get("agent_step_count", 0)
            if current_count > last_step_count:
                steps = task.get("agent_steps", [])
                new_steps = steps[last_step_count:]
                if new_steps:
                    await websocket.send_json({
                        "type": "agent_step",
                        "step": new_steps[-1],
                        "step_index": current_count - 1,
                        "total_steps": current_count,
                    })
                    last_step_count = current_count

            # 发送实时流式 token
            stream_buffer = task.get("stream_buffer", [])
            if len(stream_buffer) > last_stream_pos:
                new_content = "".join(stream_buffer[last_stream_pos:])
                last_stream_pos = len(stream_buffer)
                if new_content:
                    await websocket.send_json({
                        "type": "stream",
                        "content": new_content,
                    })

            if task["status"] in ("completed", "failed", "stopped"):
                result_data = {
                    "task_id": task_id,
                    "status": task["status"],
                    "phase": task["phase"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "target_urls": task.get("target_urls", []),
                }
                if task["status"] in ("completed", "failed"):
                    result_data["result"] = task["result"]
                result_data["agent_steps"] = task.get("agent_steps", [])
                await websocket.send_json(result_data)
                break

            # 使用 Event 等待，替代固定间隔轮询
            step_event = task.get("step_event")
            if step_event:
                try:
                    await asyncio.wait_for(step_event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
                step_event.clear()
            else:
                await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
