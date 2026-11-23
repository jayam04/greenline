import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Account, CashflowTransaction, Transaction, User
from app.services.snapshot_engine import recalculate_past_snapshots


async def earliest_activity_date(db: AsyncSession, user_id: int) -> datetime.date:
    tx_date = (await db.execute(
        select(func.min(Transaction.transaction_date)).where(Transaction.user_id == user_id)
    )).scalar_one_or_none()
    cashflow_date = (await db.execute(
        select(func.min(CashflowTransaction.transaction_date)).where(CashflowTransaction.user_id == user_id)
    )).scalar_one_or_none()
    account_created = (await db.execute(
        select(func.min(Account.created_at)).where(Account.user_id == user_id)
    )).scalar_one_or_none()
    dates = [value for value in (tx_date, cashflow_date) if value is not None]
    if account_created is not None:
        dates.append(account_created.date() if isinstance(account_created, datetime.datetime) else account_created)
    return min(dates) if dates else datetime.date.today()


async def rebuild_user_history(
    db: AsyncSession,
    user_id: int,
    start_date: datetime.date | None = None,
    *,
    full_rebuild: bool = False,
    end_date: datetime.date | None = None,
) -> int:
    end_date = end_date or datetime.date.today()
    start_date = await earliest_activity_date(db, user_id) if full_rebuild or start_date is None else start_date
    if full_rebuild:
        existing = (await db.execute(
            select(User.user_id).where(User.user_id == user_id)
        )).scalar_one_or_none()
        if existing is None:
            return 0
        from app.db.models import NetworthSnapshot

        snapshots = list((await db.execute(
            select(NetworthSnapshot)
            .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
            .where(NetworthSnapshot.user_id == user_id)
        )).scalars().all())
        for snapshot in snapshots:
            await db.delete(snapshot)
        await db.flush()

    return await recalculate_past_snapshots(
        db,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        cadence="daily",
    )


async def rebuild_all_users(db: AsyncSession, end_date: datetime.date | None = None) -> int:
    user_ids = (await db.execute(select(User.user_id).order_by(User.user_id))).scalars().all()
    count = 0
    for user_id in user_ids:
        count += await rebuild_user_history(db, user_id, full_rebuild=True, end_date=end_date)
    return count
