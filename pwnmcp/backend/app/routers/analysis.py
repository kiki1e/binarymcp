"""
赛题分析路由

上传二进制文件, 启动分析流水线, 查看分析结果。
"""

import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import async_session, get_db
from app.models import Leak
from app.model_router import model_router
from app.analysis import pipeline, ChallengeType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])

WORKSPACE = os.getenv("WORKSPACE_DIR", "/workspace")

# 内存中的分析任务状态
_analysis_tasks: dict[str, dict] = {}


class StartAnalysisRequest(BaseModel):
    challenge_type: str = "auto"  # auto/pwn/reverse/crypto/iot
    model_provider: str = ""      # 指定 provider, 空则自动选择
    model_name: str = ""          # 指定模型, 空则自动选择
    analysis_depth: str = "standard"  # quick/standard/deep


class AnalysisStatus(BaseModel):
    task_id: str
    status: str
    phase: str
    message: str
    challenge_type: str
    progress: float
    result: dict | None


# ─────────────────────────────────────
# 上传赛题
# ─────────────────────────────────────

@router.post("/upload")
async def upload_challenge(
    file: UploadFile = File(...),
    _: str = Depends(require_auth),
):
    """上传二进制文件到 workspace"""
    task_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join(WORKSPACE, "challenges", task_id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 设置可执行权限
    os.chmod(file_path, 0o755)

    return {
        "task_id": task_id,
        "filename": file.filename,
        "file_path": file_path,
        "size": len(content),
    }


# ─────────────────────────────────────
# 启动分析
# ─────────────────────────────────────

@router.post("/start/{task_id}", response_model=AnalysisStatus)
async def start_analysis(
    task_id: str,
    body: StartAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """启动赛题分析流水线"""
    # 检查文件是否存在
    upload_dir = os.path.join(WORKSPACE, "challenges", task_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(404, f"Task {task_id} not found")

    files = os.listdir(upload_dir)
    if not files:
        raise HTTPException(400, "No file uploaded for this task")

    file_path = os.path.join(upload_dir, files[0])

    # 准备模型信息
    model_info = None
    if body.model_provider and body.model_name:
        # 用户指定了模型, 从数据库找对应的 Key
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
        # 自动选择模型
        valid_keys = (await db.execute(
            select(Leak).where(Leak.key_status == "valid")
        )).scalars().all()

        if valid_keys:
            # 为每个 Key 获取模型列表
            available = []
            for k in valid_keys[:10]:  # 限制查询数量
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
                    "auto": "general",
                }
                task_type = task_type_map.get(body.challenge_type, "general")
                selected = await model_router.select_model(task_type, available)
                if selected:
                    model_info = selected

    # 初始化任务状态
    _analysis_tasks[task_id] = {
        "status": "running",
        "phase": "pending",
        "message": "分析任务已启动",
        "challenge_type": body.challenge_type,
        "progress": 0.0,
        "result": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # 后台运行分析
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
                challenge_type=body.challenge_type,
                model_info=model_info,
                progress_callback=progress_cb,
            )
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
    )


# ─────────────────────────────────────
# 查询分析状态
# ─────────────────────────────────────

@router.get("/{task_id}", response_model=AnalysisStatus)
async def get_analysis_status(
    task_id: str,
    _: str = Depends(require_auth),
):
    """获取分析任务状态和结果"""
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
    )


@router.get("")
async def list_analyses(_: str = Depends(require_auth)):
    """列出所有分析任务"""
    return {
        "tasks": [
            {
                "task_id": tid,
                "status": t["status"],
                "phase": t["phase"],
                "challenge_type": t["challenge_type"],
                "progress": t["progress"],
                "started_at": t.get("started_at"),
            }
            for tid, t in _analysis_tasks.items()
        ]
    }


# ─────────────────────────────────────
# WebSocket 实时进度
# ─────────────────────────────────────

@router.websocket("/{task_id}/ws")
async def analysis_ws(websocket: WebSocket, task_id: str):
    """WebSocket 实时推送分析进度"""
    await websocket.accept()

    try:
        last_phase = ""
        while True:
            task = _analysis_tasks.get(task_id)
            if not task:
                await websocket.send_json({"error": "Task not found"})
                break

            if task["phase"] != last_phase:
                await websocket.send_json({
                    "task_id": task_id,
                    "status": task["status"],
                    "phase": task["phase"],
                    "message": task["message"],
                    "progress": task["progress"],
                })
                last_phase = task["phase"]

            if task["status"] in ("completed", "failed"):
                await websocket.send_json({
                    "task_id": task_id,
                    "status": task["status"],
                    "phase": task["phase"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "result": task["result"],
                })
                break

            await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
