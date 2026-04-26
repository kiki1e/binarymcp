"""
自定义 Provider 管理路由
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.model_router import model_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/providers", tags=["providers"])


class RegisterProviderRequest(BaseModel):
    name: str
    base_url: str


@router.get("")
async def list_providers(_: str = Depends(require_auth)):
    """列出所有已注册的 Provider"""
    return {"providers": model_router.list_providers()}


@router.post("/register")
async def register_provider(
    body: RegisterProviderRequest,
    _: str = Depends(require_auth),
):
    """注册自定义 Provider (OpenAI 兼容模式)"""
    if not body.name or not body.base_url:
        raise HTTPException(400, "name 和 base_url 不能为空")
    if model_router.register_provider(body.name, body.base_url):
        return {"success": True, "message": f"Provider '{body.name}' 已注册"}
    raise HTTPException(400, f"Provider '{body.name}' 注册失败")


@router.delete("/{provider_name}")
async def remove_provider(
    provider_name: str,
    _: str = Depends(require_auth),
):
    """移除自定义 Provider"""
    if model_router.remove_provider(provider_name):
        return {"success": True, "message": f"Provider '{provider_name}' 已移除"}
    raise HTTPException(400, f"Provider '{provider_name}' 不存在或是内置 provider，不可移除")
