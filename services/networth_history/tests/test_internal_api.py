import datetime

import httpx
import pytest

from services.networth_history.app.main import app
from services.networth_history.app.routes import internal
from services.networth_history.app.routes import snapshots as snapshots_routes
from app.db.database import get_db


@pytest.mark.anyio
async def test_internal_recalculation_requires_service_token(monkeypatch):
    monkeypatch.setattr(internal, "SERVICE_TOKEN", "test-service-token")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.post(
            "/api/v1/internal/recalculations",
            json={"user_id": 17, "start_date": "2025-04-03", "reason": "cashflow_updated"},
        )
        accepted = await client.post(
            "/api/v1/internal/recalculations",
            headers={"X-Service-Token": "test-service-token"},
            json={"user_id": 17, "start_date": "2025-04-03", "reason": "cashflow_updated"},
        )

    assert denied.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json() == {"status": "queued", "user_id": 17, "start_date": "2025-04-03"}


@pytest.mark.anyio
async def test_internal_recalculation_enqueues_user_and_effective_date(monkeypatch):
    calls = []

    async def record_enqueue(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(internal, "SERVICE_TOKEN", "test-service-token")
    monkeypatch.setattr(internal.history_worker, "enqueue_recalculate", record_enqueue)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/internal/recalculations",
            headers={"X-Service-Token": "test-service-token"},
            json={"user_id": 17, "start_date": "2025-04-03", "reason": "trade_deleted"},
        )

    assert response.status_code == 202
    assert calls == [{
        "user_id": 17,
        "start_date": datetime.date(2025, 4, 3),
        "reason": "trade_deleted",
    }]


@pytest.mark.anyio
async def test_snapshot_read_requires_service_token_and_uses_gateway_user_context(monkeypatch):
    calls = []

    async def record_list(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    db_session = object()

    async def override_db():
        yield db_session

    monkeypatch.setattr(snapshots_routes, "SERVICE_TOKEN", "test-service-token")
    monkeypatch.setattr(snapshots_routes, "list_snapshots", record_list)
    app.dependency_overrides[get_db] = override_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            denied = await client.get(
                "/api/v1/snapshots", headers={"X-Greenline-User-Id": "17"}
            )
            accepted = await client.get(
                "/api/v1/snapshots",
                headers={"X-Service-Token": "test-service-token", "X-Greenline-User-Id": "17"},
            )
    finally:
        app.dependency_overrides.clear()

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json() == []
    assert calls == [((), {
        "account_id": None,
        "start_date": None,
        "db": db_session,
        "current_user": 17,
    })]
