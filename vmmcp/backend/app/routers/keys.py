"""
API Key 管理路由

支持手动导入 Key + 自动识别 provider + 验证 + 查询可用模型。
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Leak
from app.scanner.patterns import scan_content
from app.scanner.validator import validate_key, validate_openai_multi
from app.model_router import model_router

router = APIRouter(prefix="/api/keys", tags=["keys"])


class ImportKeysRequest(BaseModel):
    keys: list[str]


class KeyInfo(BaseModel):
    id: int
    raw_key: str
    provider: str
    verified_provider: str
    key_status: str
    models: list[dict]
    validated_at: str | None


class ImportKeysResponse(BaseModel):
    imported: int
    results: list[KeyInfo]


@router.post("/import", response_model=ImportKeysResponse)
async def import_keys(
    body: ImportKeysRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """手动导入 API Key, 自动识别 provider 并验证"""
    results = []

    for raw_key in body.keys:
        raw_key = raw_key.strip()
        if not raw_key:
            continue

        # 1. 检查是否已存在
        existing = (await db.execute(
            select(Leak).where(Leak.raw_key == raw_key)
        )).scalar_one_or_none()

        if existing:
            # 已存在, 返回现有信息
            models = await _get_models_for_key(existing)
            results.append(KeyInfo(
                id=existing.id,
                raw_key=existing.raw_key,
                provider=existing.provider,
                verified_provider=existing.verified_provider or "",
                key_status=existing.key_status or "unchecked",
                models=models,
                validated_at=str(existing.validated_at) if existing.validated_at else None,
            ))
            continue

        # 2. 用正则识别 provider
        fake_content = f"KEY={raw_key}"
        matches = scan_content(fake_content)
        provider = matches[0][0] if matches else "unknown"

        # 3. 验证 Key
        if provider == "openai" and not raw_key.startswith("sk-proj-"):
            status, v_provider, v_url = await validate_openai_multi(raw_key, "", "")
        elif provider != "unknown":
            status = await validate_key(provider, raw_key)
            v_provider, v_url = "", ""
        else:
            status, v_provider, v_url = "unchecked", "", ""

        # 4. 存入数据库
        leak = Leak(
            raw_key=raw_key,
            key_hash=raw_key[:16] + "...",
            provider=provider,
            repo_owner="manual",
            repo_name="import",
            repo_url="",
            file_path="manual_import",
            leak_detected_at=datetime.now(timezone.utc),
            key_status=status,
            validated_at=datetime.now(timezone.utc),
            verified_provider=v_provider,
            verified_url=v_url,
        )
        db.add(leak)
        await db.flush()

        # 5. 获取可用模型
        effective_provider = v_provider or provider
        models = []
        if status == "valid":
            try:
                models = await model_router.list_models_for_key(
                    effective_provider, raw_key, v_url
                )
            except Exception:
                pass

        results.append(KeyInfo(
            id=leak.id,
            raw_key=raw_key,
            provider=provider,
            verified_provider=v_provider,
            key_status=status,
            models=models,
            validated_at=str(leak.validated_at),
        ))

    await db.commit()
    return ImportKeysResponse(imported=len(results), results=results)


@router.get("/{key_id}/models")
async def get_key_models(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """获取某个 Key 可用的模型列表"""
    leak = (await db.execute(
        select(Leak).where(Leak.id == key_id)
    )).scalar_one_or_none()

    if not leak:
        raise HTTPException(404, "Key not found")

    models = await _get_models_for_key(leak)
    return {"key_id": key_id, "provider": leak.verified_provider or leak.provider, "models": models}


async def _get_models_for_key(leak) -> list[dict]:
    """查询某个 Key 可用的模型"""
    if leak.key_status != "valid":
        return []

    provider = leak.verified_provider or leak.provider
    base_url = leak.verified_url or ""

    try:
        return await model_router.list_models_for_key(provider, leak.raw_key, base_url)
    except Exception:
        return []


@router.get("/available-models")
async def get_all_available_models(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """获取所有有效 Key 的可用模型 (汇总)"""
    valid_keys = (await db.execute(
        select(Leak).where(Leak.key_status == "valid")
    )).scalars().all()

    all_models = {}
    for leak in valid_keys:
        provider = leak.verified_provider or leak.provider
        try:
            models = await model_router.list_models_for_key(
                provider, leak.raw_key, leak.verified_url or ""
            )
            for m in models:
                model_id = m["id"]
                if model_id not in all_models:
                    all_models[model_id] = {
                        "id": model_id,
                        "provider": provider,
                        "owned_by": m.get("owned_by", ""),
                        "key_count": 0,
                    }
                all_models[model_id]["key_count"] += 1
        except Exception:
            continue

    return {"models": list(all_models.values()), "total": len(all_models)}
