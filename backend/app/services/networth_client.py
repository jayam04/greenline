import logging
import datetime
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def get_networth_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        base_url = getattr(settings, "NETWORTH_SERVICE_URL", "http://localhost:8001")
        _client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=0.5, read=2.0, write=1.0, pool=3.0)
        )
    return _client


async def close_networth_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


async def notify_snapshot_recalculate(
    user_id: int,
    start_date: Optional[datetime.date] = None,
    reason: str = "trade_event",
    auth_token: Optional[str] = None
) -> bool:
    """
    Non-blocking notification to Networth microservice.
    Gracefully handles offline/unreachable service without throwing exceptions.
    """
    if not auth_token:
        logger.debug(f"[NetworthClient] No auth token provided for user_id={user_id}. Skipping remote notification.")
        return False

    headers = {}
    cleaned_token = auth_token.strip()
    if not cleaned_token.lower().startswith("bearer "):
        cleaned_token = f"Bearer {cleaned_token}"
    headers["Authorization"] = cleaned_token

    payload = {
        "user_id": user_id,
        "start_date": str(start_date) if start_date else None,
        "reason": reason
    }

    try:
        client = get_networth_client()
        resp = await client.post("/api/v1/snapshots/trigger-recalculate", json=payload, headers=headers)
        if resp.status_code in (200, 202):
            logger.debug(f"[NetworthClient] Enqueued recalculation for user_id={user_id}")
            return True
        logger.warning(f"[NetworthClient] Recalculate trigger returned HTTP {resp.status_code}: {resp.text}")
        return False
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as e:
        logger.info(f"[NetworthClient] Networth service offline or unreachable ({e}). Continuing gracefully.")
        return False
    except Exception as e:
        logger.warning(f"[NetworthClient] Unexpected error calling Networth service: {e}. Continuing gracefully.")
        return False
