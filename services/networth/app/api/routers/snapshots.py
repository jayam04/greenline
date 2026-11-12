import datetime
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, func
from sqlalchemy.orm import selectinload
from cachetools import TTLCache

try:
    from ...db.database import get_db
    from ...db.models import NetworthSnapshot, Account, User, Transaction
    from ...schemas.schemas import NetworthSnapshotResponse, TriggerRecalculateRequest
    from ...services.snapshot_engine import calculate_account_snapshots
    from ...services.background_worker import background_worker
    from ..deps import get_current_user, get_user_id
except (ImportError, ValueError):
    from app.db.database import get_db
    from app.db.models import NetworthSnapshot, Account, User, Transaction
    from app.schemas.schemas import NetworthSnapshotResponse, TriggerRecalculateRequest
    from app.services.snapshot_engine import calculate_account_snapshots
    from app.services.background_worker import background_worker
    from app.api.deps import get_current_user, get_user_id

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

# L1 in-memory TTL Cache (sub-millisecond query responses)
# Key: (user_id: int, account_id: Optional[int], start_date: Optional[datetime.date])
snapshots_cache: TTLCache = TTLCache(maxsize=2000, ttl=300)


def invalidate_user_cache(user_id: int):
    """Purges all L1 cache entries for a given user upon recalculation."""
    keys_to_del = [k for k in snapshots_cache.keys() if k[0] == user_id]
    for k in keys_to_del:
        snapshots_cache.pop(k, None)


@router.get("", response_model=List[NetworthSnapshotResponse])
@router.get("/", response_model=List[NetworthSnapshotResponse])
async def list_snapshots(
    account_id: Optional[int] = Query(None),
    start_date: Optional[datetime.date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sub-50ms snapshot timeseries endpoint (<10ms target).
    Aggregates snapshot data strictly on calendar Sundays (d.weekday() == 6),
    delivering 85.7% payload reduction.
    Supports starting date selection with SQL pushdown and automatic inception fallback.
    """
    u_id = get_user_id(current_user)
    if not isinstance(account_id, int):
        account_id = None
    if not isinstance(start_date, (datetime.date, datetime.datetime)):
        start_date = None

    # 1. Single-account snapshot timeline
    if account_id is not None:
        acc_stmt = select(Account).where(Account.account_id == account_id, Account.user_id == u_id)
        acc_res = await db.execute(acc_stmt)
        acc = acc_res.scalar_one_or_none()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found or access denied")

        cache_key = (u_id, account_id, start_date)
        if cache_key in snapshots_cache:
            return snapshots_cache[cache_key]

        acc_snaps = await calculate_account_snapshots(db, account_id=account_id, start_date=start_date)
        if start_date is not None:
            acc_snaps = [s for s in acc_snaps if s["snapshot_date"] >= start_date]

        # Enforce Sunday invariant (weekday == 6)
        sunday_snaps = [s for s in acc_snaps if s["snapshot_date"].weekday() == 6]
        res = [NetworthSnapshotResponse(**s) for s in sunday_snaps]
        snapshots_cache[cache_key] = res
        return res

    # 2. Aggregated portfolio net worth mode
    cache_key = (u_id, None, start_date)
    if cache_key in snapshots_cache:
        return snapshots_cache[cache_key]

    stmt = (
        select(NetworthSnapshot)
        .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
        .where(NetworthSnapshot.user_id == u_id)
    )

    if start_date is not None:
        # SQL pushdown of start_date
        stmt = stmt.where(NetworthSnapshot.snapshot_date >= start_date)
    else:
        # Auto-detect earliest transaction date
        min_tx_stmt = select(func.min(Transaction.transaction_date)).where(Transaction.user_id == u_id)
        min_tx = (await db.execute(min_tx_stmt)).scalar_one_or_none()
        if min_tx is not None:
            stmt = stmt.where(NetworthSnapshot.snapshot_date >= min_tx)

    stmt = stmt.order_by(asc(NetworthSnapshot.snapshot_date))
    rows = list((await db.execute(stmt)).scalars().all())

    # Guarantee strict Sunday aggregation invariant
    sunday_rows = [r for r in rows if r.snapshot_date.weekday() == 6]
    if start_date is not None:
        sunday_rows = [r for r in sunday_rows if r.snapshot_date >= start_date]

    res = [NetworthSnapshotResponse.model_validate(r) for r in sunday_rows]
    snapshots_cache[cache_key] = res
    return res


@router.post("/trigger-recalculate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_recalculate(
    payload: TriggerRecalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Enqueues a non-blocking trade recalculation job (<2ms) into the in-process background worker.
    Enforces Row-Level Security tenant isolation.
    """
    u_id = get_user_id(current_user)
    if payload.user_id != u_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot trigger recalculation for another user"
        )

    # Invalidate cache for this user
    invalidate_user_cache(u_id)
    try:
        from .portfolio import invalidate_portfolio_cache
        invalidate_portfolio_cache(u_id)
    except Exception:
        try:
            from app.api.routers.portfolio import invalidate_portfolio_cache
            invalidate_portfolio_cache(u_id)
        except Exception:
            pass

    # Enqueue recalculation in background worker
    await background_worker.enqueue_recalculate(
        user_id=u_id,
        start_date=payload.start_date,
        reason=payload.reason or "manual_trigger"
    )

    # Yield control to event loop to allow background worker to process immediately
    await asyncio.sleep(0)

    return {
        "status": "queued",
        "user_id": u_id,
        "start_date": str(payload.start_date) if payload.start_date else None
    }
