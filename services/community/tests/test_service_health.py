import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_endpoint(community_client: AsyncClient):
    """GET /health returns 200 OK with service identifier."""
    res = await community_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "community"}


@pytest.mark.anyio
async def test_root_endpoint(community_client: AsyncClient):
    """GET / returns 200 OK with service name."""
    res = await community_client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "community"
    assert "Greenline Community Microservice" in data["message"]
