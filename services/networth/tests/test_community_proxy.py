import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, AsyncMock
import httpx
from app.main import app


def test_community_proxy_routes_to_community_service():
    """Verify that requests to /api/v1/community/* on networth service are proxied to community-service."""
    mock_resp = httpx.Response(
        status_code=200,
        json={"posts": [], "total": 0, "page": 1, "page_size": 50},
        headers={"content-type": "application/json"}
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_resp):
        client = TestClient(app)
        res = client.get("/api/v1/community/posts?limit=50&offset=0&sort=latest")
        assert res.status_code == 200
        data = res.json()
        assert "posts" in data
