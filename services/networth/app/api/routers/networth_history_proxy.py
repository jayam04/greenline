import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api.deps import get_current_user, get_user_id
from app.config import settings
from app.schemas.schemas import TriggerRecalculateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/snapshots", tags=["snapshots-proxy"])


async def _request_history(path: str, user_id: int, method: str = "GET", params=None, body=None):
    token = settings.NETWORTH_HISTORY_SERVICE_TOKEN
    if not token:
        return Response(
            content=json.dumps({"detail": "Networth history service is not configured"}),
            status_code=503,
            media_type="application/json",
        )
    url = f"{settings.NETWORTH_HISTORY_URL.rstrip('/')}/api/v1/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.request(
                method,
                url,
                params=params,
                json=body,
                headers={
                    "X-Service-Token": token,
                    "X-Greenline-User-Id": str(user_id),
                },
            )
        headers = dict(upstream.headers)
        for key in ("content-encoding", "transfer-encoding", "connection", "content-length"):
            headers.pop(key, None)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=headers,
            media_type=upstream.headers.get("content-type"),
        )
    except Exception as exc:
        logger.warning("Networth history request failed: %s", exc)
        return Response(
            content=json.dumps({"detail": "Networth history service unavailable"}),
            status_code=503,
            media_type="application/json",
        )


@router.get("")
@router.get("/")
async def proxy_snapshots(
    account_id: int | None = None,
    start_date: str | None = None,
    current_user=Depends(get_current_user),
):
    return await _request_history(
        "snapshots", get_user_id(current_user),
        params={k: v for k, v in {"account_id": account_id, "start_date": start_date}.items() if v is not None},
    )


@router.post("/trigger-recalculate", status_code=status.HTTP_202_ACCEPTED)
async def proxy_recalculation(
    payload: TriggerRecalculateRequest,
    current_user=Depends(get_current_user),
):
    user_id = get_user_id(current_user)
    if payload.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot recalculate another user's history")
    return await _request_history(
        "internal/recalculations", user_id, method="POST", body=payload.model_dump(mode="json")
    )
