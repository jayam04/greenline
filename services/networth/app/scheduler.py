import logging
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

async def scheduled_weekly_sunday_snapshot():
    """
    Consolidates and materializes weekly Sunday snapshots for all users at 23:59 UTC.
    """
    try:
        from .db.database import AsyncSessionLocal
        from .db.models import User
        from .services.snapshot_engine import recalculate_past_snapshots
        from .api.routers.snapshots import invalidate_user_cache
    except (ImportError, ValueError):
        from app.db.database import AsyncSessionLocal
        from app.db.models import User
        from app.services.snapshot_engine import recalculate_past_snapshots
        from app.api.routers.snapshots import invalidate_user_cache

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
                invalidate_user_cache(u_id)
        except Exception as ue:
            logger.warning(f"Error calculating Sunday snapshot for user {u_id}: {ue}")
    logger.info("[Networth Scheduler] Weekly Sunday consolidation completed.")

def start_scheduler():
    """Initializes and starts the background task scheduler."""
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
        logger.info("[Networth Scheduler] AsyncIOScheduler started for Sunday snapshots.")

def stop_scheduler():
    """Stops the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Networth Scheduler] AsyncIOScheduler stopped.")
