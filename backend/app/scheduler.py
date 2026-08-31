from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import AsyncSessionLocal
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.backup_service import check_and_trigger_autobackup

scheduler = AsyncIOScheduler()

async def scheduled_nightly_job():
    async with AsyncSessionLocal() as session:
        try:
            print("[Scheduler] Running nightly price sync and snapshot generation...")
            await update_prices_for_assets(session)
            await generate_daily_snapshot(session)
            print("[Scheduler] Nightly job completed successfully.")
        except Exception as e:
            print(f"[Scheduler] Error running nightly job: {e}")

async def scheduled_autobackup_job():
    async with AsyncSessionLocal() as session:
        try:
            await check_and_trigger_autobackup(session)
        except Exception as e:
            print(f"[Scheduler] Error checking auto-backup: {e}")

def start_scheduler():
    # Schedule job every night at 00:00 UTC (or periodic 6 hour intervals)
    scheduler.add_job(scheduled_nightly_job, "cron", hour=0, minute=0)
    # Schedule hourly check for auto-backup interval
    scheduler.add_job(scheduled_autobackup_job, "interval", hours=1)
    scheduler.start()
