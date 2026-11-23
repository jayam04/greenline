import hmac
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..worker import history_worker

router = APIRouter(prefix="/internal", tags=["internal"])
SERVICE_TOKEN = os.getenv("NETWORTH_HISTORY_SERVICE_TOKEN", "")


class RecalculationRequest(BaseModel):
    user_id: int = Field(ge=0)
    start_date: Optional[date] = None
    reason: str = "financial_change"


@router.post("/recalculations", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_recalculation(
    payload: RecalculationRequest,
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    if not SERVICE_TOKEN:
        raise HTTPException(status_code=503, detail="Networth history service token is not configured")
    if not x_service_token or not hmac.compare_digest(x_service_token, SERVICE_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid service credentials")

    await history_worker.enqueue_recalculate(
        user_id=payload.user_id,
        start_date=payload.start_date,
        reason=payload.reason,
    )
    return {
        "status": "queued",
        "user_id": payload.user_id,
        "start_date": str(payload.start_date) if payload.start_date else None,
    }
