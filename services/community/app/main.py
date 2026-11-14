from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

try:
    from .config import settings
    from .api.routers import posts_router, comments_router, pseudonyms_router
except (ImportError, ValueError):
    from app.config import settings
    from app.api.routers import posts_router, comments_router, pseudonyms_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include Community routers under /api/v1/community
app.include_router(posts_router, prefix=settings.API_V1_STR)
app.include_router(comments_router, prefix=settings.API_V1_STR)
app.include_router(pseudonyms_router, prefix=settings.API_V1_STR)

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
    return {"status": "ok", "service": "community"}


@app.get("/")
async def root():
    """Root info endpoint."""
    return {
        "message": "Greenline Community Microservice is running",
        "service": "community",
        "docs": "/docs"
    }
