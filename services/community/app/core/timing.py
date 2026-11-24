import os
import time
import uuid
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("greenline.community.timing")

ENABLE_TIMING_LOGS = os.getenv("ENABLE_TIMING_LOGS", "true").lower() in ("true", "1", "yes")
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").lower() in ("true", "1", "yes")
SLOW_QUERY_THRESHOLD_MS = float(os.getenv("SLOW_QUERY_THRESHOLD_MS", "50.0"))


@dataclass
class RequestTimingContext:
    request_id: str
    start_time: float
    path: str
    method: str
    client_ip: str = ""
    db_queries: List[Dict[str, Any]] = field(default_factory=list)
    db_time_ms: float = 0.0
    db_query_count: int = 0
    pool_checkout_ms: float = 0.0
    auth_time_ms: Optional[float] = None
    auth_method: Optional[str] = None
    calc_timings: Dict[str, float] = field(default_factory=dict)


current_timing_context: ContextVar[Optional[RequestTimingContext]] = ContextVar(
    "current_timing_context", default=None
)


def get_current_timing_context() -> Optional[RequestTimingContext]:
    return current_timing_context.get()


@contextmanager
def time_block(name: str):
    """Context manager to profile execution duration of internal calculation blocks."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        ctx = current_timing_context.get()
        if ctx:
            ctx.calc_timings[name] = ctx.calc_timings.get(name, 0.0) + elapsed_ms
            if ENABLE_TIMING_LOGS:
                logger.info(f"[CALC {ctx.request_id}] {name} completed in {elapsed_ms:.2f}ms")


def record_db_query(statement: str, duration_ms: float):
    """Record execution of an individual SQL statement into the active request context."""
    ctx = current_timing_context.get()
    clean_sql = " ".join(statement.split())
    if len(clean_sql) > 120:
        clean_sql = f"{clean_sql[:117]}..."

    if ctx:
        ctx.db_time_ms += duration_ms
        ctx.db_query_count += 1
        ctx.db_queries.append({"sql": clean_sql, "duration_ms": duration_ms})
        req_id = ctx.request_id
    else:
        req_id = "background"

    if duration_ms >= SLOW_QUERY_THRESHOLD_MS:
        logger.warning(f"[SLOW QUERY {req_id}] {duration_ms:.2f}ms | {clean_sql}")
    elif LOG_SQL_QUERIES and ENABLE_TIMING_LOGS:
        logger.info(f"[DB {req_id}] {duration_ms:.2f}ms | {clean_sql}")


def record_pool_checkout(duration_ms: float):
    """Record database connection pool checkout / pre-ping duration."""
    ctx = current_timing_context.get()
    if ctx:
        ctx.pool_checkout_ms += duration_ms
        req_id = ctx.request_id
    else:
        req_id = "background"

    if (duration_ms >= SLOW_QUERY_THRESHOLD_MS or LOG_SQL_QUERIES) and ENABLE_TIMING_LOGS:
        logger.info(f"[DB POOL {req_id}] Connection checkout in {duration_ms:.2f}ms")


def record_auth_time(duration_ms: float, method: str, user_id: Any = None):
    """Record authentication resolution duration."""
    ctx = current_timing_context.get()
    if ctx:
        ctx.auth_time_ms = duration_ms
        ctx.auth_method = method
        if ENABLE_TIMING_LOGS:
            logger.info(
                f"[AUTH {ctx.request_id}] User resolved in {duration_ms:.2f}ms "
                f"(method={method}, user_id={user_id})"
            )


class TimingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware measuring end-to-end request duration and injecting timing headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method

        ctx = RequestTimingContext(
            request_id=req_id,
            start_time=time.perf_counter(),
            path=path,
            method=method,
            client_ip=client_ip
        )
        token = current_timing_context.set(ctx)

        if ENABLE_TIMING_LOGS and not path.endswith("/health"):
            logger.info(f"--> [REQ {req_id}] {method} {path} from {client_ip}")

        try:
            response = await call_next(request)
        finally:
            total_ms = (time.perf_counter() - ctx.start_time) * 1000.0
            current_timing_context.reset(token)

        # Inject diagnostic headers for frontend inspection
        response.headers["X-Process-Time-Ms"] = f"{total_ms:.2f}"
        response.headers["X-Request-ID"] = req_id

        if ENABLE_TIMING_LOGS and not path.endswith("/health"):
            status_code = response.status_code
            calc_parts = [f"{k}={v:.1f}ms" for k, v in ctx.calc_timings.items()]
            calc_str = f" | Calc: {', '.join(calc_parts)}" if calc_parts else ""
            auth_str = f" | Auth: {ctx.auth_time_ms:.1f}ms" if ctx.auth_time_ms is not None else ""
            pool_str = f" | Pool: {ctx.pool_checkout_ms:.1f}ms" if ctx.pool_checkout_ms > 0 else ""

            logger.info(
                f"<-- [SUMMARY {req_id}] {method} {path} -> {status_code} | "
                f"Total: {total_ms:.1f}ms | DB: {ctx.db_time_ms:.1f}ms ({ctx.db_query_count} queries)"
                f"{pool_str}{auth_str}{calc_str}"
            )

        return response
