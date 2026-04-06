"""
BinaryMCP 融合平台 — 统一后端入口

集成:
- API Key 扫描/管理 (来自 apicheck)
- AI 模型路由 (新增)
- 赛题分析流水线 (新增)
- IDA Pro 代理 (新增)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.database import async_session, engine
from app.models import Base, Leak
from app.routers import auth, leaks, stats
from app.routers import keys, analysis, ida
from app.scanner.engine import ScanEngine
from app.scanner.patterns import _is_false_positive
from app.scanner.validator import validate_key, validate_openai_multi
from app.model_router import model_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)
scan_engine = ScanEngine()


async def _startup_cleanup():
    """启动时将误报 key 标记为 filtered 并批量验证 unchecked key"""
    BATCH_SIZE = 500
    async with async_session() as session:
        total_marked = 0
        offset = 0
        while True:
            rows = (await session.execute(
                select(Leak).where(Leak.key_status != "filtered")
                .order_by(Leak.id).offset(offset).limit(BATCH_SIZE)
            )).scalars().all()
            if not rows:
                break
            marked = 0
            for leak in rows:
                if _is_false_positive(leak.raw_key):
                    leak.key_status = "filtered"
                    marked += 1
            if marked:
                await session.commit()
                total_marked += marked
            offset += BATCH_SIZE
        if total_marked:
            logger.info("Startup cleanup: marked %d false-positive keys as filtered", total_marked)

    async with async_session() as session:
        unchecked = (await session.execute(
            select(Leak).where(Leak.key_status == "unchecked")
        )).scalars().all()
        if not unchecked:
            return
        logger.info("Startup: validating %d unchecked keys", len(unchecked))
        sem = asyncio.Semaphore(5)

        async def _validate(leak: Leak) -> tuple[int, str, str, str]:
            async with sem:
                if leak.provider in ("google", "openrouter"):
                    return leak.id, "unsupported", "", ""
                if leak.provider == "openai" and not leak.raw_key.startswith("sk-proj-"):
                    s, vp, vu = await validate_openai_multi(
                        leak.raw_key, leak.repo_url, leak.file_path)
                    return leak.id, s, vp, vu
                return leak.id, await validate_key(leak.provider, leak.raw_key), "", ""

        tasks = [_validate(l) for l in unchecked]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    async with async_session() as session:
        now = datetime.now(timezone.utc)
        for r in results:
            if isinstance(r, tuple):
                lid, status, v_provider, v_url = r
                leak = (await session.execute(
                    select(Leak).where(Leak.id == lid)
                )).scalar_one_or_none()
                if leak:
                    leak.key_status = status
                    leak.validated_at = now
                    if v_provider:
                        leak.verified_provider = v_provider
                    if v_url:
                        leak.verified_url = v_url
        await session.commit()
        logger.info("Startup: validation complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 数据库初始化 & 迁移 ──
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for col in ("total_events_scanned", "total_commits_scanned"):
            try:
                await conn.execute(text(
                    f"ALTER TABLE scan_state ADD COLUMN {col} INTEGER DEFAULT 0"
                ))
            except Exception:
                pass
        for col, typedef in (
            ("key_status", "VARCHAR(16) DEFAULT 'unchecked'"),
            ("validated_at", "DATETIME"),
            ("verified_provider", "VARCHAR(32) DEFAULT ''"),
            ("verified_url", "VARCHAR(512) DEFAULT ''"),
        ):
            try:
                await conn.execute(text(
                    f"ALTER TABLE leaks ADD COLUMN {col} {typedef}"
                ))
            except Exception:
                pass
        for col, typedef in (
            ("last_event_id_events", "VARCHAR(64) DEFAULT ''"),
        ):
            try:
                await conn.execute(text(
                    f"ALTER TABLE scan_state ADD COLUMN {col} {typedef}"
                ))
            except Exception:
                pass
        await conn.execute(text(
            "UPDATE leaks SET provider='minimax' WHERE raw_key LIKE 'sk-cp-%' AND provider='openai'"
        ))
        await conn.execute(text(
            "UPDATE leaks SET provider='kimi' WHERE raw_key LIKE 'sk-kimi-%' AND provider='openai'"
        ))
        _known_providers = (
            "openai", "deepseek", "dashscope", "moonshot", "anthropic",
            "google", "groq", "xai", "cerebras", "siliconflow",
            "huggingface", "github", "kimi", "minimax", "openrouter",
            "newapi", "",
        )
        placeholders = ",".join(f"'{p}'" for p in _known_providers)
        r = await conn.execute(text(
            f"UPDATE leaks SET verified_provider='newapi' "
            f"WHERE verified_provider NOT IN ({placeholders})"
        ))
        if r.rowcount:
            logger.info("Migration: %d records updated verified_provider -> newapi", r.rowcount)
        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_leaks_repo_owner_name "
                "ON leaks (repo_owner, repo_name)"
            ))
        except Exception:
            pass

    # ── 启动后台任务 ──
    async def _safe_startup_cleanup():
        try:
            await _startup_cleanup()
        except Exception as e:
            logger.error("Startup cleanup failed: %s", e)

    asyncio.create_task(_safe_startup_cleanup())
    scan_task = asyncio.create_task(scan_engine.run())

    logger.info("=" * 60)
    logger.info("BinaryMCP 融合平台启动完成")
    logger.info("  - GitHub Key 扫描: 已启动")
    logger.info("  - Model Router: 就绪")
    logger.info("  - 分析流水线: 就绪")
    logger.info("=" * 60)

    yield

    # ── 清理 ──
    await scan_engine.stop()
    scan_task.cancel()
    await model_router.close()
    logger.info("BinaryMCP 平台已关闭")


app = FastAPI(
    title="BinaryMCP - CTF Analysis Platform",
    description="融合 API Key 管理 + AI 模型路由 + 二进制赛题分析",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
# 原 apicheck 路由
app.include_router(auth.router)
app.include_router(leaks.router)
app.include_router(stats.router)
# 新增路由
app.include_router(keys.router)
app.include_router(analysis.router)
app.include_router(ida.router)
