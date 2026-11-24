import pytest
import time
from starlette.testclient import TestClient
from app.main import app
from app.core.timing import RequestTimingContext, current_timing_context, time_block


def test_community_timing_context():
    ctx = RequestTimingContext(
        request_id="test_comm_123",
        start_time=time.perf_counter(),
        path="/test",
        method="GET"
    )
    token = current_timing_context.set(ctx)
    try:
        with time_block("community_calc"):
            time.sleep(0.01)

        assert "community_calc" in ctx.calc_timings
        assert ctx.calc_timings["community_calc"] >= 5.0
    finally:
        current_timing_context.reset(token)


def test_community_timing_headers():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-process-time-ms" in response.headers
    assert "x-request-id" in response.headers
    process_time = float(response.headers["x-process-time-ms"])
    assert process_time > 0.0
