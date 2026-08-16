from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import AsyncSessionLocal
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import generate_daily_snapshot

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

def start_scheduler():
    # Schedule job every night at 00:00 UTC (or periodic 6 hour intervals)
    scheduler.add_job(scheduled_nightly_job, "cron", hour=0, minute=0)
    scheduler.start()
