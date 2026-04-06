"""
IDA Pro Bridge — 轻量 HTTP 代理

将 Docker 容器内的请求转发到 Windows 主机上运行的 IDA Pro HTTP API。
IDA Pro 需要加载 ida_server.py 插件 (绑定 0.0.0.0:4000)。

Docker 容器通过 host.docker.internal 访问宿主机。
"""

import os
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("ida-bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

IDA_URL = os.getenv("IDA_URL", "http://host.docker.internal:4000")
TIMEOUT = float(os.getenv("IDA_TIMEOUT", "30"))

# 全局 httpx 客户端 (连接池复用)
http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=TIMEOUT)
    logger.info("IDA Bridge 启动 — 目标: %s", IDA_URL)
    yield
    await http_client.aclose()
    logger.info("IDA Bridge 已关闭")


app = FastAPI(title="IDA Pro Bridge", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────
# 健康检查 / IDA 连接状态
# ──────────────────────────────────────────

@app.get("/ida/status")
async def ida_status():
    """检查 IDA Pro 是否可达"""
    try:
        r = await http_client.post(f"{IDA_URL}/ping", json={})
        return {
            "status": "connected",
            "ida_url": IDA_URL,
            "ida_response": r.json(),
        }
    except httpx.ConnectError:
        return {"status": "disconnected", "ida_url": IDA_URL, "error": "无法连接到 IDA Pro"}
    except Exception as e:
        return {"status": "error", "ida_url": IDA_URL, "error": str(e)}


# ──────────────────────────────────────────
# 通用代理: 转发所有 /ida/{endpoint} 到 IDA
# ──────────────────────────────────────────

@app.post("/ida/{endpoint:path}")
async def proxy_to_ida(endpoint: str, request: Request):
    """将请求透传到 IDA Pro HTTP API"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    target = f"{IDA_URL}/{endpoint}"
    logger.debug("代理请求: POST %s — body=%s", target, body)

    try:
        r = await http_client.post(target, json=body)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"IDA Pro 不可达 ({IDA_URL})。请确保 IDA 已打开并加载了 ida_server.py 脚本。",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ──────────────────────────────────────────
# 便捷端点 (前端可直接调用)
# ──────────────────────────────────────────

@app.get("/ida/functions")
async def list_functions():
    """获取 IDA 中的函数列表"""
    try:
        r = await http_client.post(f"{IDA_URL}/functions", json={})
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/ida/decompile")
async def decompile(body: dict):
    """反编译指定函数"""
    try:
        r = await http_client.post(f"{IDA_URL}/decompile", json=body)
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/ida/disassemble")
async def disassemble(body: dict):
    """获取汇编代码"""
    try:
        r = await http_client.post(f"{IDA_URL}/disassemble", json=body)
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/ida/xrefs")
async def xrefs(body: dict):
    """获取交叉引用"""
    try:
        r = await http_client.post(f"{IDA_URL}/xrefs", json=body)
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/ida/info")
async def get_info():
    """获取二进制基本信息"""
    try:
        r = await http_client.post(f"{IDA_URL}/info", json={})
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
