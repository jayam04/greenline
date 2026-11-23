import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.database import AsyncSessionLocal
from app.services.price_engine import update_prices_for_assets
from app.services.backup_service import check_and_trigger_autobackup

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def scheduled_nightly_job():
    """Runs nightly price synchronization; networth-history rebuilds snapshots separately."""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("[Scheduler] Running nightly price sync...")
            await update_prices_for_assets(session)
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
