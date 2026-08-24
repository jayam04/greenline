import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base, get_db
from app.db.models import User, Asset
from app.api.deps import get_current_user
from app.main import app
from app.api.routers.assets import _bg_fetch_asset_price_history

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def test_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionMaker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionMaker() as session:
        yield session, SessionMaker

@pytest.fixture
async def client(test_db_session):
    session, session_maker = test_db_session
    mock_user = User(user_id=1, username="testadmin")

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session, session_maker

    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_lookup_asset_metadata_threadpool(client):
    ac, session, _ = client
    mock_info = {
        "longName": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "quoteType": "EQUITY",
        "isin": "US0378331005",
    }

    with patch("app.api.routers.assets._fetch_yf_ticker_info", return_value=mock_info) as mock_fetch:
        resp = await ac.get("/api/v1/assets/lookup?symbol=AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["exchange"] == "NASDAQ"
        assert data["sector"] == "Technology"
        assert data["asset_type"] == "stock"
        assert data["isin"] == "US0378331005"
        mock_fetch.assert_called_once_with("AAPL")

@pytest.mark.anyio
async def test_search_assets_threadpool_and_local(client):
    ac, session, _ = client
    
    # 1. Add local asset
    local_ast = Asset(symbol="RELIANCE.NS", name="Reliance Industries", asset_type="stock", exchange="NSE", currency="INR")
    session.add(local_ast)
    await session.commit()

    mock_quotes = [
        {
            "symbol": "RELIANCE.NS", # Duplicate in online search, should be deduped
            "longname": "Reliance Industries Ltd",
            "exchange": "NSI",
            "quoteType": "EQUITY"
        },
        {
            "symbol": "RELINFRA.NS",
            "shortname": "Reliance Infrastructure",
            "exchange": "NSI",
            "quoteType": "EQUITY"
        }
    ]

    with patch("app.api.routers.assets._search_yf_quotes", return_value=mock_quotes) as mock_search:
        resp = await ac.get("/api/v1/assets/search?q=Reliance")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2
        
        # Local asset first
        assert results[0]["symbol"] == "RELIANCE.NS"
        assert results[0]["in_master"] is True
        assert results[0]["asset_id"] == local_ast.asset_id

        # Online result second
        assert results[1]["symbol"] == "RELINFRA.NS"
        assert results[1]["in_master"] is False
        assert results[1]["asset_id"] is None
        mock_search.assert_called_once_with("Reliance", 8)

@pytest.mark.anyio
async def test_get_or_create_asset_background_price_fetch(client):
    ac, session, _ = client
    mock_info = {
        "longName": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Software—Infrastructure",
        "currency": "USD",
        "quoteType": "EQUITY"
    }

    with patch("app.api.routers.assets._fetch_yf_ticker_info", return_value=mock_info) as mock_info_fetch, \
         patch("app.api.routers.assets._bg_fetch_asset_price_history") as mock_bg_task:
        
        resp = await ac.post("/api/v1/assets/get-or-create", json={"symbol": "MSFT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "MSFT"
        assert data["name"] == "Microsoft Corporation"
        assert data["asset_id"] is not None

        # Threadpool enrichment was called
        mock_info_fetch.assert_called_once_with("MSFT")
        # Background task was queued
        mock_bg_task.assert_called_once_with(data["asset_id"], "MSFT")

@pytest.mark.anyio
async def test_get_or_create_existing_asset(client):
    ac, session, _ = client
    existing = Asset(symbol="GOOGL", name="Alphabet Inc.", asset_type="stock")
    session.add(existing)
    await session.commit()
    await session.refresh(existing)

    with patch("app.api.routers.assets._fetch_yf_ticker_info") as mock_info_fetch, \
         patch("app.api.routers.assets._bg_fetch_asset_price_history") as mock_bg_task:
        resp = await ac.post("/api/v1/assets/get-or-create", json={"symbol": "GOOGL"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_id"] == existing.asset_id
        mock_info_fetch.assert_not_called()
        mock_bg_task.assert_not_called()

@pytest.mark.anyio
async def test_create_asset_with_background_task(client):
    ac, session, _ = client
    payload = {
        "symbol": "AMZN",
        "name": "Amazon.com Inc.",
        "asset_type": "stock",
        "exchange": "NASDAQ",
        "currency": "USD"
    }

    with patch("app.api.routers.assets._bg_fetch_asset_price_history") as mock_bg_task:
        resp = await ac.post("/api/v1/assets/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "AMZN"
        assert data["asset_id"] is not None
        mock_bg_task.assert_called_once_with(data["asset_id"], "AMZN")

@pytest.mark.anyio
async def test_bg_fetch_asset_price_history_handles_exceptions():
    with patch("app.api.routers.assets.AsyncSessionLocal") as mock_session_local, \
         patch("app.api.routers.assets.fetch_asset_price_history", side_effect=Exception("Network Timeout")) as mock_fetch:
        
        mock_session = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        # Should not raise exception
        await _bg_fetch_asset_price_history(1, "AAPL")
        mock_fetch.assert_called_once_with(mock_session, 1, "AAPL")
