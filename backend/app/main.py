import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import User, Transaction
from app.services.auth_service import get_password_hash
from app.scheduler import start_scheduler

from app.api.routers import (
    auth, accounts, assets, transactions, portfolio, 
    snapshots, prices, benchmarks, backup,
    categories, cashflow, settings as app_settings_router, discrepancies,
    import_router, mcp_router
)

from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots
from app.services.cashflow_engine import seed_default_categories
from app.db.migrations import run_db_migrations

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
    # Run deterministic versioned schema and data migrations
    async with AsyncSessionLocal() as session:
        try:
            await run_db_migrations(session)
        except Exception as me:
            print(f"[DB Migration Error] {me}")

    # Seed default user if none exists & seed default categories
    async with AsyncSessionLocal() as session:
        user0_stmt = select(User).where(User.user_id == 0)
        user0_res = await session.execute(user0_stmt)
        user0 = user0_res.scalars().first()

        if not user0:
            admin_stmt = select(User).where(User.username == settings.DEFAULT_ADMIN_USER)
            admin_res = await session.execute(admin_stmt)
            admin_user = admin_res.scalars().first()

            if admin_user:
                from sqlalchemy import text
                await session.execute(
                    text("UPDATE users SET user_id = 0 WHERE username = :uname"),
                    {"uname": settings.DEFAULT_ADMIN_USER}
                )
                await session.commit()
                print(f"[Init] Re-mapped existing admin user '{settings.DEFAULT_ADMIN_USER}' to user_id=0")
            else:
                default_user = User(
                    user_id=0,
                    username=settings.DEFAULT_ADMIN_USER,
                    password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
                )
                session.add(default_user)
                await session.commit()
                print(f"[Init] Created default admin user: {settings.DEFAULT_ADMIN_USER} (user_id=0)")
        else:
            print(f"[Init] Verified default admin user: {user0.username} (user_id=0)")

        # Seed categories
        try:
            await seed_default_categories(session)
        except Exception as ce:
            print(f"[Init Categories Error] {ce}")
            
    try:
        asyncio.create_task(_startup_backfill())
    except Exception as be:
        print(f"[Init Backfill Task Error] {be}")

    try:
        start_scheduler()
    except Exception as se:
        print(f"[Init Scheduler Error] {se}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
app.include_router(benchmarks.router, prefix=settings.API_V1_STR)
app.include_router(backup.router, prefix=settings.API_V1_STR)
app.include_router(categories.router, prefix=settings.API_V1_STR)
app.include_router(cashflow.router, prefix=settings.API_V1_STR)
app.include_router(app_settings_router.router, prefix=settings.API_V1_STR)
app.include_router(discrepancies.router, prefix=settings.API_V1_STR)
app.include_router(import_router.router, prefix=settings.API_V1_STR)
app.include_router(mcp_router.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Investment Tracker API is running", "docs": "/docs"}

@app.get("/openapi.json", include_in_schema=False)
async def get_root_mcp_openapi(request: Request):
    from app.api.routers.mcp_router import get_mcp_openapi_json
    return await get_mcp_openapi_json(request)
