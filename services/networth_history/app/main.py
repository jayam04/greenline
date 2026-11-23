from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services import cache_service
from .routes.internal import router as internal_router
from .routes.snapshots import router as snapshots_router
from .scheduler import compare_legacy_snapshots, nightly_full_rebuild, start_scheduler, stop_scheduler
from .worker import history_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    history_worker.start()
    start_scheduler()
    # Populate the isolated schema before this service begins serving snapshot reads.
    await nightly_full_rebuild(raise_errors=True)
    await compare_legacy_snapshots()
    yield
    stop_scheduler()
    await history_worker.stop()
    await cache_service.close_redis_client()


app = FastAPI(title="Networth History Service", lifespan=lifespan)
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "networth-history"}
