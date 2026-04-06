from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Leak, ScanState
from app.schemas import LeaderboardItem, ProviderDailyItem, StatsResponse, WeeklyItem

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    not_filtered = Leak.key_status.notin_(("filtered", "unsupported"))
    total = (await db.execute(
        select(func.count(Leak.id)).where(not_filtered)
    )).scalar() or 0

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today = (await db.execute(
        select(func.count(Leak.id)).where(
            Leak.leak_detected_at >= today_start, not_filtered
        )
    )).scalar() or 0

    repos = (await db.execute(
        select(func.count(func.distinct(Leak.repo_url))).where(not_filtered)
    )).scalar() or 0

    scan_state = (await db.execute(select(ScanState))).scalar_one_or_none()
    events_scanned = scan_state.total_events_scanned if scan_state else 0
    repos_scanned = scan_state.total_commits_scanned if scan_state else 0

    return StatsResponse(
        total_leaks=total, today_leaks=today, total_repos=repos,
        total_events_scanned=events_scanned, total_repos_scanned=repos_scanned,
    )


@router.get("/weekly", response_model=list[WeeklyItem])
async def get_weekly(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc)
    week_start = datetime.combine(
        (now - timedelta(days=6)).date(), datetime.min.time(), tzinfo=timezone.utc
    )
    date_col = func.date(Leak.leak_detected_at)
    rows = (await db.execute(
        select(date_col.label("d"), func.count(Leak.id).label("c"))
        .where(Leak.leak_detected_at >= week_start, Leak.key_status.notin_(("filtered", "unsupported")))
        .group_by(date_col)
    )).all()
    counts = {r[0]: r[1] for r in rows}

    results = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        results.append(WeeklyItem(date=day.isoformat(), count=counts.get(day.isoformat(), 0)))
    return results


@router.get("/leaderboard", response_model=list[LeaderboardItem])
async def get_leaderboard(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    rows = (await db.execute(
        select(Leak.repo_owner, func.count(Leak.id).label("cnt"))
        .where(Leak.key_status.notin_(("filtered", "unsupported")))
        .group_by(Leak.repo_owner)
        .order_by(func.count(Leak.id).desc())
        .limit(10)
    )).all()
    return [LeaderboardItem(repo_owner=r[0], leak_count=r[1]) for r in rows]


@router.get("/provider-daily", response_model=list[ProviderDailyItem])
async def get_provider_daily(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    """近7天每个 provider 每天的泄露数量"""
    now = datetime.now(timezone.utc)
    week_start = datetime.combine(
        (now - timedelta(days=6)).date(), datetime.min.time(), tzinfo=timezone.utc
    )
    date_col = func.date(Leak.leak_detected_at)
    # 优先使用 verified_provider，回退到 provider
    eff_provider = case(
        (Leak.verified_provider != "", Leak.verified_provider),
        else_=Leak.provider,
    )
    rows = (await db.execute(
        select(date_col.label("d"), eff_provider.label("p"), func.count(Leak.id).label("c"))
        .where(Leak.leak_detected_at >= week_start, Leak.key_status.notin_(("filtered", "unsupported")))
        .group_by(date_col, eff_provider)
    )).all()

    # 补全7天 x 所有provider的完整矩阵
    providers = sorted({r[1] for r in rows})
    counts: dict[tuple[str, str], int] = {(r[0], r[1]): r[2] for r in rows}
    results = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        for p in providers:
            results.append(ProviderDailyItem(date=day, provider=p, count=counts.get((day, p), 0)))
    return results


@router.get("/valid-daily", response_model=list[ProviderDailyItem])
async def get_valid_daily(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    """近7天每个 provider 每天的有效 key 数量（仅 key_status='valid'）"""
    now = datetime.now(timezone.utc)
    week_start = datetime.combine(
        (now - timedelta(days=6)).date(), datetime.min.time(), tzinfo=timezone.utc
    )
    date_col = func.date(Leak.leak_detected_at)
    eff_provider = case(
        (Leak.verified_provider != "", Leak.verified_provider),
        else_=Leak.provider,
    )
    rows = (await db.execute(
        select(date_col.label("d"), eff_provider.label("p"), func.count(Leak.id).label("c"))
        .where(Leak.leak_detected_at >= week_start, Leak.key_status == "valid")
        .group_by(date_col, eff_provider)
    )).all()

    providers = sorted({r[1] for r in rows})
    counts: dict[tuple[str, str], int] = {(r[0], r[1]): r[2] for r in rows}
    results: list[ProviderDailyItem] = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        day_total = 0
        for p in providers:
            c = counts.get((day, p), 0)
            day_total += c
            results.append(ProviderDailyItem(date=day, provider=p, count=c))
        # 每天追加一条 total 汇总行
        results.append(ProviderDailyItem(date=day, provider="total", count=day_total))
    return results
