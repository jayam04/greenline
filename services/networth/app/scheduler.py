import logging
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots
from app.services.backup_service import check_and_trigger_autobackup

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def scheduled_nightly_job():
    """Runs nightly price synchronization and historical net worth snapshot generation."""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("[Scheduler] Running nightly price sync and snapshot generation...")
            await update_prices_for_assets(session)
            await generate_daily_snapshot(session)
            logger.info("[Scheduler] Nightly job completed successfully.")
        except Exception as e:
            logger.error(f"[Scheduler] Error running nightly job: {e}")


async def scheduled_autobackup_job():
    """Evaluates auto-backup schedule and triggers snapshot if due."""
    async with AsyncSessionLocal() as session:
        try:
            await check_and_trigger_autobackup(session)
        except Exception as e:
            logger.error(f"[Scheduler] Error checking auto-backup: {e}")


async def scheduled_weekly_sunday_snapshot():
    """
    Consolidates and materializes weekly Sunday snapshots for all users at 23:59 UTC.
    """
    try:
        from app.api.routers.snapshots import invalidate_user_cache
    except Exception:
        invalidate_user_cache = None

    logger.info("[Networth Scheduler] Running weekly Sunday snapshot consolidation...")
    today = datetime.datetime.now(datetime.timezone.utc).date()
    async with AsyncSessionLocal() as session:
        try:
            users_res = await session.execute(select(User.user_id))
            user_ids = users_res.scalars().all()
        except Exception as e:
            logger.error(f"[Networth Scheduler] Error retrieving users for weekly consolidation: {e}")
            return

    for u_id in user_ids:
        try:
            async with AsyncSessionLocal() as u_session:
                await recalculate_past_snapshots(u_session, start_date=today, end_date=today, user_id=u_id)
                if invalidate_user_cache:
                    invalidate_user_cache(u_id)
        except Exception as ue:
            logger.warning(f"Error calculating Sunday snapshot for user {u_id}: {ue}")
    logger.info("[Networth Scheduler] Weekly Sunday consolidation completed.")


def start_scheduler():
    """Initializes and starts the background task scheduler with idempotent jobs."""
    scheduler.add_job(
        scheduled_nightly_job,
        "cron",
        hour=0,
        minute=0,
        id="nightly_job",
        replace_existing=True
    )
    scheduler.add_job(
        scheduled_autobackup_job,
        "interval",
        hours=1,
        id="autobackup_job",
        replace_existing=True
    )
    scheduler.add_job(
        scheduled_weekly_sunday_snapshot,
        "cron",
        day_of_week="sun",
        hour=23,
        minute=59,
        timezone="UTC",
        id="weekly_sunday_snapshot",
        replace_existing=True
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("[Scheduler] AsyncIOScheduler started successfully.")


def stop_scheduler():
    """Stops the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] AsyncIOScheduler stopped.")


def reschedule_autobackup_job(interval_hours: int = 1, enabled: bool = True):
    """
    Dynamically adjusts or pauses the autobackup scheduled job upon configuration updates.
    """
    try:
        existing = scheduler.get_job("autobackup_job")
        if existing:
            existing.remove()

        if enabled:
            scheduler.add_job(
                scheduled_autobackup_job,
                "interval",
                hours=max(1, interval_hours),
                id="autobackup_job",
                replace_existing=True
            )
    except Exception as e:
        logger.error(f"[Scheduler] Failed to reschedule autobackup job: {e}")
