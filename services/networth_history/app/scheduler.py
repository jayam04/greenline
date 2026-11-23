import logging
import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.database import AsyncSessionLocal
from .worker import history_worker

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def nightly_full_rebuild(raise_errors: bool = False):
    try:
        user_count, snapshot_count = await history_worker.rebuild_all_users()
        logger.info(
            "Nightly net-worth history rebuild completed for %s users and %s snapshots",
            user_count, snapshot_count,
        )
    except Exception:
        logger.exception("Nightly net-worth history rebuild failed")
        if raise_errors:
            raise


async def compare_legacy_snapshots():
    """Log parity for existing weekly points before the proxy begins serving reads."""
    from sqlalchemy import text, select
    from app.db.models import NetworthSnapshot

    async with AsyncSessionLocal() as db:
        users = (await db.execute(text(
            "SELECT DISTINCT user_id FROM ADMIN.networth_snapshots ORDER BY user_id"
        ))).scalars().all()
        for user_id in users:
            legacy = (await db.execute(text(
                "SELECT snapshot_date, net_worth FROM ADMIN.networth_snapshots WHERE user_id = :user_id"
            ), {"user_id": user_id})).all()
            current = (await db.execute(
                select(NetworthSnapshot.snapshot_date, NetworthSnapshot.net_worth)
                .where(NetworthSnapshot.user_id == user_id)
            )).all()
            current_by_date = {snapshot_date: float(value) for snapshot_date, value in current}
            legacy_by_date = {
                snapshot_date.date() if isinstance(snapshot_date, datetime.datetime) else snapshot_date: float(value)
                for snapshot_date, value in legacy
            }
            mismatches = [
                (snapshot_date, value, current_by_date[snapshot_date])
                for snapshot_date, value in legacy_by_date.items()
                if snapshot_date in current_by_date
                and abs(value - current_by_date[snapshot_date]) > 0.01
            ]
            logger.info(
                "Legacy snapshot parity user=%s compared=%s mismatches=%s",
                user_id,
                sum(1 for snapshot_date in legacy_by_date if snapshot_date in current_by_date),
                len(mismatches),
            )


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(
        nightly_full_rebuild,
        "cron",
        hour=0,
        minute=30,
        id="networth-history-full-rebuild",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
