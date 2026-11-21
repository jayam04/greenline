import os
import json
import logging
from fastapi import APIRouter, Request, Response
import httpx
from app.core.timing import time_block

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/community", tags=["community-proxy"])

COMMUNITY_SERVICE_URL = os.getenv(
    "COMMUNITY_SERVICE_URL",
    "http://community:8002" if os.getenv("IS_DOCKER") else "http://localhost:8002"
).rstrip("/")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_community_request(request: Request, path: str):
    """Transparently proxy /api/v1/community requests to community-service."""
    url = f"{COMMUNITY_SERVICE_URL}/api/v1/community/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = await request.body()
    with time_block("community_proxy_forward"):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body
                )
                # Filter out hop-by-hop headers from upstream response
                resp_headers = dict(resp.headers)
                for hop in ("content-encoding", "transfer-encoding", "connection"):
                    resp_headers.pop(hop, None)

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=resp_headers,
                    media_type=resp.headers.get("content-type")
                )
        except Exception as exc:
            logger.warning(f"[Community Proxy] Failed to forward request to {url}: {exc}")
            return Response(
                content=json.dumps({"detail": f"Community service unreachable: {str(exc)}"}),
                status_code=503,
                media_type="application/json"
            )
