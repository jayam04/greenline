import pytest
import time
from starlette.testclient import TestClient
from app.main import app
from app.core.timing import RequestTimingContext, current_timing_context, time_block


def test_timing_context_and_time_block():
    ctx = RequestTimingContext(
        request_id="test_req_123",
        start_time=time.perf_counter(),
        path="/test",
        method="GET"
    )
    token = current_timing_context.set(ctx)
    try:
        with time_block("dummy_calculation"):
            time.sleep(0.01)  # 10ms

        assert "dummy_calculation" in ctx.calc_timings
        assert ctx.calc_timings["dummy_calculation"] >= 5.0  # at least ~5ms
    finally:
        current_timing_context.reset(token)


def test_http_timing_headers_injected():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-process-time-ms" in response.headers
    assert "x-request-id" in response.headers
    process_time = float(response.headers["x-process-time-ms"])
    assert process_time > 0.0
