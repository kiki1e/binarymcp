"""
IDA Pro 代理路由

前端通过 backend API 间接调用 IDA Pro (经 ida-bridge 转发)。
"""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth

router = APIRouter(prefix="/api/ida", tags=["ida"])

IDA_BRIDGE_URL = os.getenv("IDA_BRIDGE_URL", "http://ida-bridge:5600")


async def _ida_request(method: str, endpoint: str, body: dict = None) -> dict:
    """向 IDA Bridge 发送请求"""
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{IDA_BRIDGE_URL}/ida/{endpoint}"
        try:
            if method == "GET":
                r = await client.get(url)
            else:
                r = await client.post(url, json=body or {})
            return r.json()
        except httpx.ConnectError:
            raise HTTPException(503, "IDA Bridge 不可达, 请检查 ida-bridge 服务")
        except Exception as e:
            raise HTTPException(502, str(e))


@router.get("/status")
async def ida_status(_: str = Depends(require_auth)):
    """检查 IDA Pro 连接状态"""
    return await _ida_request("GET", "status")


class DecompileRequest(BaseModel):
    target: str  # 函数名或地址


@router.post("/decompile")
async def decompile(body: DecompileRequest, _: str = Depends(require_auth)):
    """反编译指定函数"""
    return await _ida_request("POST", "decompile", {"target": body.target})


@router.get("/functions")
async def list_functions(_: str = Depends(require_auth)):
    """获取函数列表"""
    return await _ida_request("GET", "functions")


@router.get("/info")
async def get_info(_: str = Depends(require_auth)):
    """获取二进制基本信息"""
    return await _ida_request("GET", "info")


class DisassembleRequest(BaseModel):
    target: str


@router.post("/disassemble")
async def disassemble(body: DisassembleRequest, _: str = Depends(require_auth)):
    """获取汇编代码"""
    return await _ida_request("POST", "disassemble", {"target": body.target})


class XrefsRequest(BaseModel):
    target: str


@router.post("/xrefs")
async def xrefs(body: XrefsRequest, _: str = Depends(require_auth)):
    """获取交叉引用"""
    return await _ida_request("POST", "xrefs", {"target": body.target})
