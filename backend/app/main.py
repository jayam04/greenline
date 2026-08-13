import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.config import settings
from app.db.database import engine, Base, AsyncSessionLocal
from app.db.models import User
from app.services.auth_service import get_password_hash
from app.scheduler import start_scheduler

from app.api.routers import (
    auth, accounts, assets, transactions, portfolio, 
    snapshots, prices, corporate_actions, benchmarks
)

from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed default user if none exists
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

        # Recalculate FIFO lots & snapshots on startup to ensure total consistency
        await recalculate_all_lots(session)
        await generate_daily_snapshot(session)
            
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

@app.get("/")
def root():
    return {"message": "Investment Tracker API is running", "docs": "/docs"}
