import datetime
import logging

import httpx

try:
    from ..config import settings
except (ImportError, ValueError):
    from app.config import settings

logger = logging.getLogger(__name__)


async def request_history_recalculation(
    user_id: int,
    start_date: datetime.date | None = None,
    reason: str = "financial_change",
) -> bool:
    """Ask networth-history to queue a recalculation after the source commit."""
    token = settings.NETWORTH_HISTORY_SERVICE_TOKEN
    if not token:
        logger.error("Networth history enqueue skipped: service token is not configured")
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                f"{settings.NETWORTH_HISTORY_URL.rstrip('/')}/api/v1/internal/recalculations",
                headers={"X-Service-Token": token},
                json={
                    "user_id": user_id,
                    "start_date": start_date.isoformat() if start_date else None,
                    "reason": reason,
                },
            )
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Networth history enqueue failed for user=%s; nightly rebuild will repair it", user_id)
        return False
