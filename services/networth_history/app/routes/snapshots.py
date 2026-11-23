import hmac
import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.routers.snapshots import list_snapshots
from app.schemas.schemas import NetworthSnapshotResponse, TriggerRecalculateRequest
from ..worker import history_worker

router = APIRouter(prefix="/snapshots", tags=["snapshots"])
SERVICE_TOKEN = os.getenv("NETWORTH_HISTORY_SERVICE_TOKEN", "")


def _authorize(service_token: Optional[str], user_id: Optional[int]) -> int:
    if not SERVICE_TOKEN:
        raise HTTPException(status_code=503, detail="Networth history service token is not configured")
    if not service_token or not hmac.compare_digest(service_token, SERVICE_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid service credentials")
    if user_id is None or user_id < 0:
        raise HTTPException(status_code=400, detail="Authenticated user context is required")
    return user_id


@router.get("", response_model=List[NetworthSnapshotResponse])
@router.get("/", response_model=List[NetworthSnapshotResponse])
async def get_snapshots(
    account_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    x_greenline_user_id: Optional[int] = Header(None, alias="X-Greenline-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _authorize(x_service_token, x_greenline_user_id)
    return await list_snapshots(
        account_id=account_id, start_date=start_date,
        db=db, current_user=user_id,
    )


@router.post("/trigger-recalculate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_recalculation(
    payload: TriggerRecalculateRequest,
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    x_greenline_user_id: Optional[int] = Header(None, alias="X-Greenline-User-Id"),
):
    user_id = _authorize(x_service_token, x_greenline_user_id)
    if payload.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot recalculate another user's history")
    await history_worker.enqueue_recalculate(
        user_id=user_id,
        start_date=payload.start_date,
        reason=payload.reason or "manual_trigger",
    )
    return {
        "status": "queued",
        "user_id": user_id,
        "start_date": str(payload.start_date) if payload.start_date else None,
    }
