import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from app.config import settings
from app.db.database import engine, Base, AsyncSessionLocal
from app.db.models import User, Transaction
from app.services.auth_service import get_password_hash
from app.scheduler import start_scheduler

from app.api.routers import (
    auth, accounts, assets, transactions, portfolio, 
    snapshots, prices, corporate_actions, benchmarks, backup,
    categories, cashflow, settings as app_settings_router
)

from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots
from app.services.cashflow_engine import seed_default_categories, migrate_legacy_payment_signs

async def _startup_backfill():
    async with AsyncSessionLocal() as session:
        try:
            await recalculate_all_lots(session)
            min_tx = await session.execute(select(func.min(Transaction.transaction_date)))
            earliest_date = min_tx.scalar_one_or_none()
            if earliest_date:
                await recalculate_past_snapshots(session, start_date=earliest_date)
            else:
                await generate_daily_snapshot(session)
        except Exception as e:
            print(f"[Startup Backfill] Error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure industry column exists if table was created previously
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE assets ADD COLUMN industry VARCHAR"))
        except Exception:
            pass
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE cashflow_transactions ADD COLUMN transaction_kind VARCHAR"))
        except Exception:
            pass
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN funding_account_id INTEGER"))
        except Exception:
            pass
        
    # Seed default user if none exists & seed default categories
    async with AsyncSessionLocal() as session:
        stmt = select(User)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            default_user = User(
                username=settings.DEFAULT_ADMIN_USER,
                password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
            )
            session.add(default_user)
            await session.commit()
            print(f"[Init] Created default admin user: {settings.DEFAULT_ADMIN_USER}")

        # Seed categories & migrate legacy payment signs
        try:
            await seed_default_categories(session)
            await migrate_legacy_payment_signs(session)
        except Exception as ce:
            print(f"[Init Categories / Migration Error] {ce}")
            
    asyncio.create_task(_startup_backfill())
    start_scheduler()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(accounts.router, prefix=settings.API_V1_STR)
app.include_router(assets.router, prefix=settings.API_V1_STR)
app.include_router(transactions.router, prefix=settings.API_V1_STR)
app.include_router(portfolio.router, prefix=settings.API_V1_STR)
app.include_router(snapshots.router, prefix=settings.API_V1_STR)
app.include_router(prices.router, prefix=settings.API_V1_STR)
app.include_router(corporate_actions.router, prefix=settings.API_V1_STR)
app.include_router(benchmarks.router, prefix=settings.API_V1_STR)
app.include_router(backup.router, prefix=settings.API_V1_STR)
app.include_router(categories.router, prefix=settings.API_V1_STR)
app.include_router(cashflow.router, prefix=settings.API_V1_STR)
app.include_router(app_settings_router.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Investment Tracker API is running", "docs": "/docs"}
