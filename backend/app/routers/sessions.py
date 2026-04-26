"""
会话管理路由 — 对话历史的 CRUD
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.session.store import SessionStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])

WORKSPACE = "C:/Users/ds/AppData/Local/binarymcp/workspace"


def get_store() -> SessionStore:
    return SessionStore(WORKSPACE)


class CreateSessionRequest(BaseModel):
    name: str = "新对话"
    user_id: str = ""


@router.get("")
async def list_sessions(
    user_id: str = "",
    limit: int = 50,
    _: str = Depends(require_auth),
):
    """列出所有会话"""
    store = get_store()
    sessions = store.list_sessions(user_id=user_id, limit=limit)
    return {"sessions": sessions}


@router.post("")
async def create_session(
    body: CreateSessionRequest,
    _: str = Depends(require_auth),
):
    """创建新会话"""
    session_id = str(uuid.uuid4())[:8]
    store = get_store()
    session = store.create_session(
        session_id=session_id,
        user_id=body.user_id,
        name=body.name,
    )
    return {"session": session}


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    _: str = Depends(require_auth),
):
    """获取会话详情（含消息历史）"""
    store = get_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(404, f"会话 {session_id} 不存在")
    return {"session": session}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    _: str = Depends(require_auth),
):
    """删除会话"""
    store = get_store()
    if store.delete_session(session_id):
        return {"success": True}
    raise HTTPException(404, f"会话 {session_id} 不存在")


@router.put("/{session_id}/name")
async def rename_session(
    session_id: str,
    body: dict,
    _: str = Depends(require_auth),
):
    """重命名会话"""
    name = body.get("name", "")
    if not name:
        raise HTTPException(400, "name 不能为空")
    store = get_store()
    session = store.update_session(session_id, {"name": name})
    if not session:
        raise HTTPException(404, f"会话 {session_id} 不存在")
    return {"session": session}


@router.post("/{session_id}/clear")
async def clear_messages(
    session_id: str,
    _: str = Depends(require_auth),
):
    """清空会话消息"""
    store = get_store()
    if store.clear_messages(session_id):
        return {"success": True}
    raise HTTPException(404, f"会话 {session_id} 不存在")
