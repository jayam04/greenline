from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

try:
    from .config import settings
    from .api.routers import snapshots, portfolio
    from .services.background_worker import background_worker
    from .scheduler import start_scheduler, stop_scheduler
except (ImportError, ValueError):
    from app.config import settings
    from app.api.routers import snapshots, portfolio
    from app.services.background_worker import background_worker
    from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Microservice lifespan management
    background_worker.start()
    start_scheduler()
    yield
    await background_worker.stop()
    stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.include_router(snapshots.router, prefix=settings.API_V1_STR)
app.include_router(portfolio.router, prefix=settings.API_V1_STR)

# GZip middleware for compressing responses > 1000 bytes
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware
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


@app.get("/health")
async def healthcheck():
    """Service health check endpoint."""
    return {"status": "ok", "service": "networth"}


@app.get("/")
async def root():
    """Root info endpoint."""
    return {
        "message": "Networth & Analytics Microservice is running",
        "service": "networth",
        "docs": "/docs"
    }
