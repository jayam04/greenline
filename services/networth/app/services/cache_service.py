import os
import logging
import datetime
from typing import Optional, Union
import redis.asyncio as aioredis

try:
    from ..config import settings
except (ImportError, ValueError):
    from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> Optional[aioredis.Redis]:
    """Returns the singleton async Redis client, initializing if necessary."""
    global _redis_client
    if _redis_client is None:
        redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        try:
            _redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client from {redis_url}: {e}")
            return None
    return _redis_client


def set_redis_client(client: Optional[aioredis.Redis]) -> None:
    """Sets or overrides the Redis client (used for tests and lifecycle management)."""
    global _redis_client
    _redis_client = client


async def close_redis_client() -> None:
    """Closes the active Redis client connection pool."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None


# Key Generation Helpers
def get_snapshot_key(
    user_id: int,
    account_id: Optional[int] = None,
    start_date: Optional[Union[datetime.date, datetime.datetime, str]] = None
) -> str:
    """Key format: gl:snap:{user_id}:acc:{account_id or 'all'}:start:{start_date or 'inc'}"""
    acc_part = str(account_id) if account_id is not None else "all"
    start_part = str(start_date) if start_date is not None else "inc"
    return f"gl:snap:{user_id}:acc:{acc_part}:start:{start_part}"


def get_portfolio_summary_key(user_id: int, account_id: Optional[int] = None) -> str:
    """Key format: gl:summary:{user_id}:acc:{account_id or 'all'}"""
    acc_part = str(account_id) if account_id is not None else "all"
    return f"gl:summary:{user_id}:acc:{acc_part}"


def get_annual_snapshot_key(
    user_id: int,
    fiscal_year_start: Optional[str] = "01-01",
    master_currency: Optional[str] = "EUR"
) -> str:
    """Key format: gl:annual:{user_id}:fy:{fiscal_year_start}:curr:{master_currency}"""
    fy_part = fiscal_year_start or "01-01"
    curr_part = master_currency or "EUR"
    return f"gl:annual:{user_id}:fy:{fy_part}:curr:{curr_part}"


def get_transaction_page_key(
    user_id: int,
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    account_id: Optional[int] = None,
    asset_id: Optional[int] = None,
) -> str:
    """Key format: gl:tx:{user_id}:p={page}:s={page_size}:acc={account_id or 'all'}:asset={asset_id or 'all'}"""
    p = page if page is not None else 1
    s = page_size if page_size is not None else 50
    acc = str(account_id) if account_id is not None else "all"
    ast = str(asset_id) if asset_id is not None else "all"
    return f"gl:tx:{user_id}:p={p}:s={s}:acc={acc}:asset={ast}"


def get_cashflow_page_key(
    user_id: int,
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    start_date: Optional[Union[datetime.date, datetime.datetime, str]] = None,
    end_date: Optional[Union[datetime.date, datetime.datetime, str]] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    label: Optional[str] = None,
) -> str:
    """Key format: gl:cf:{user_id}:p={page}:s={page_size}:start={start_date or 'none'}:end={end_date or 'none'}:acc={account_id or 'all'}:cat={category_id or 'all'}:label={label or 'all'}"""
    p = page if page is not None else 1
    s = page_size if page_size is not None else 50
    start = str(start_date) if start_date is not None else "none"
    end = str(end_date) if end_date is not None else "none"
    acc = str(account_id) if account_id is not None else "all"
    cat = str(category_id) if category_id is not None else "all"
    lbl = str(label).lower() if label is not None else "all"
    return f"gl:cf:{user_id}:p={p}:s={s}:start={start}:end={end}:acc={acc}:cat={cat}:label={lbl}"



# Async Cache Service Operations with Graceful Degradation
async def get_cache(key: str) -> Optional[str]:
    """Retrieves a cached JSON string from Redis, returning None on miss or error."""
    try:
        client = get_redis_client()
        if client is None:
            return None
        return await client.get(key)
    except Exception as e:
        logger.warning(f"Redis get_cache error for key '{key}': {e}")
        return None


async def set_cache(key: str, value: str, ttl_seconds: int = 300) -> None:
    """Sets a cached string with TTL in seconds, silently ignoring failures."""
    try:
        client = get_redis_client()
        if client is None:
            return
        await client.set(key, value, ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Redis set_cache error for key '{key}': {e}")


async def invalidate_pattern(pattern: str) -> None:
    """Deletes all keys matching the glob pattern using SCAN iteration."""
    try:
        client = get_redis_client()
        if client is None:
            return
        keys = []
        scanner = client.scan_iter(match=pattern, count=100)
        if hasattr(scanner, "__aiter__"):
            async for k in scanner:
                keys.append(k)
        elif hasattr(scanner, "__await__"):
            res = await scanner
            if isinstance(res, (list, tuple, set)):
                keys.extend(res)
        if keys:
            await client.delete(*keys)
    except Exception as e:
        logger.warning(f"Redis invalidate_pattern error for pattern '{pattern}': {e}")


async def invalidate_user_snapshot_cache(user_id: int) -> None:
    """
    Invalidates all snapshot, portfolio summary, and annual snapshot keys for the user.
    Also clears in-memory L1 caches if present.
    """
    await invalidate_pattern(f"gl:snap:{user_id}:*")
    await invalidate_pattern(f"gl:summary:{user_id}:*")
    await invalidate_pattern(f"gl:annual:{user_id}:*")

    # Clear legacy/local in-memory caches if loaded
    try:
        from ..api.routers.snapshots import invalidate_user_cache
        invalidate_user_cache(user_id)
    except Exception:
        try:
            from app.api.routers.snapshots import invalidate_user_cache
            invalidate_user_cache(user_id)
        except Exception:
            pass

    try:
        from ..api.routers.portfolio import invalidate_portfolio_cache
        invalidate_portfolio_cache(user_id)
    except Exception:
        try:
            from app.api.routers.portfolio import invalidate_portfolio_cache
            invalidate_portfolio_cache(user_id)
        except Exception:
            pass


async def invalidate_user_transaction_cache(user_id: int) -> None:
    """Invalidates cached transaction pages and snapshot cache for the user."""
    await invalidate_pattern(f"gl:tx:{user_id}:*")
    await invalidate_pattern(f"gl:tx*:{user_id}:*")
    await invalidate_pattern(f"greenline:tx:{user_id}:*")
    await invalidate_user_snapshot_cache(user_id)


async def invalidate_user_cashflow_cache(user_id: int) -> None:
    """Invalidates cached cashflow transaction pages and snapshot cache for the user."""
    await invalidate_pattern(f"gl:cf:{user_id}:*")
    await invalidate_pattern(f"gl:cf*:{user_id}:*")
    await invalidate_pattern(f"greenline:cashflow_tx:{user_id}:*")
    await invalidate_user_snapshot_cache(user_id)

