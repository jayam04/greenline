import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import Base, User, Account, Asset, Transaction, Lot, LotSale, ApiKey
from app.db.database import get_db
from app.main import app
from app.services.auth_service import get_password_hash

@pytest.fixture
async def mcp_stocks_env():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed User, Account, Asset
    test_user = User(user_id=1, username="mcp_stock_user", password_hash=get_password_hash("password123"))
    zerodha_acc = Account(account_id=1, account_name="Zerodha", account_type="demat", currency="USD")
    bank_acc = Account(account_id=2, account_name="HDFC Bank", account_type="bank", currency="USD")
    aapl_asset = Asset(asset_id=1, symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD", exchange="NASDAQ")

    async with TestSession() as session:
        session.add_all([test_user, zerodha_acc, bank_acc, aapl_asset])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, TestSession, test_user

    app.dependency_overrides.clear()
    await test_engine.dispose()

@pytest.mark.anyio
async def test_public_mcp_openapi_endpoint_no_auth(mcp_stocks_env):
    client, session_factory, user = mcp_stocks_env

    # 1. GET /api/v1/mcp/openapi.json without auth
    res = await client.get("/api/v1/mcp/openapi.json")
    assert res.status_code == 200, res.text
    spec = res.json()
    assert spec["openapi"] == "3.1.0"
    paths = spec["paths"]
    assert "/api/v1/mcp/categories" in paths
    assert "/api/v1/mcp/cashflow" in paths
    assert "/api/v1/mcp/stocks" in paths

    # 2. GET /openapi.json without auth
    res_root = await client.get("/openapi.json")
    assert res_root.status_code == 200
    spec_root = res_root.json()
    assert spec_root["openapi"] == "3.1.0"
    assert "/api/v1/mcp/stocks" in spec_root["paths"]

    # 3. Assert all operation descriptions adhere to ChatGPT Actions 300-char limit
    for p_path, p_item in spec["paths"].items():
        for m_method, op in p_item.items():
            if m_method in ["get", "post", "put", "delete"]:
                desc = op.get("description", "")
                assert len(desc) <= 300, f"Operation {op.get('operationId')} description length ({len(desc)}) exceeds 300 chars: '{desc}'"


@pytest.mark.anyio
async def test_mcp_stocks_workflow_and_validation(mcp_stocks_env):
    client, session_factory, user = mcp_stocks_env

    # Login and create API key
    login_res = await client.post("/api/v1/auth/login", data={"username": "mcp_stock_user", "password": "password123"})
    jwt_token = login_res.json()["access_token"]
    key_res = await client.post("/api/v1/auth/api-keys", headers={"Authorization": f"Bearer {jwt_token}"}, json={"name": "Stock Agent"})
    api_key = key_res.json()["key"]
    auth_headers = {"Authorization": f"Bearer {api_key}"}

    # 1. Preliminary fetch: GET /api/v1/mcp/stocks
    fetch_res = await client.get("/api/v1/mcp/stocks", headers=auth_headers)
    assert fetch_res.status_code == 200, fetch_res.text
    fetch_data = fetch_res.json()
    assert "available_assets" in fetch_data
    assert any(a["symbol"] == "AAPL" for a in fetch_data["available_assets"])
    assert "available_accounts" in fetch_data
    assert any(acc["account_name"] == "Zerodha" for acc in fetch_data["available_accounts"])
    assert fetch_data["total_count"] == 0

    # 2. Account mismatch: Reject unknown account and list available accounts
    bad_acc_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "FakeBroker",
                "symbol": "AAPL",
                "transaction_type": "buy",
                "quantity": 10,
                "price_per_unit": 150.0
            }
        ]
    }
    bad_acc_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=bad_acc_payload)
    assert bad_acc_res.status_code == 400
    err_text = bad_acc_res.json()["detail"]
    assert "FakeBroker" in err_text
    assert "Zerodha" in err_text # Lists valid accounts

    # 3. Asset mismatch without force_create_asset: Reject and instruct to set force_create_asset=true
    bad_asset_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "Zerodha",
                "symbol": "PLTR",
                "force_create_asset": False,
                "transaction_type": "buy",
                "quantity": 20,
                "price_per_unit": 30.0
            }
        ]
    }
    bad_asset_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=bad_asset_payload)
    assert bad_asset_res.status_code == 400
    err_asset_text = bad_asset_res.json()["detail"]
    assert "PLTR" in err_asset_text
    assert "force_create_asset" in err_asset_text
    assert "AAPL" in err_asset_text # Lists known assets

    # 4. Force create asset and insert buy transaction
    force_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "Zerodha",
                "symbol": "PLTR",
                "asset_name": "Palantir Technologies Inc.",
                "asset_type": "stock",
                "exchange": "NYSE",
                "force_create_asset": True,
                "transaction_type": "buy",
                "date": "2026-09-10",
                "quantity": 20,
                "price_per_unit": 30.0,
                "fees": 2.0,
                "taxes": 1.0
            }
        ]
    }
    force_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=force_payload)
    assert force_res.status_code == 200, force_res.text
    force_data = force_res.json()
    assert len(force_data["results"]) == 1
    tx_pltr = force_data["results"][0]
    assert tx_pltr["asset_symbol"] == "PLTR"
    assert tx_pltr["asset_name"] == "Palantir Technologies Inc."
    # Total cost = 20 * 30 + 2 + 1 = 603.0
    assert tx_pltr["total_amount"] == 603.0

    # Verify asset is now in database
    async with session_factory() as session:
        pltr_db = (await session.execute(select(Asset).where(Asset.symbol == "PLTR"))).scalar_one_or_none()
        assert pltr_db is not None
        assert pltr_db.name == "Palantir Technologies Inc."

    # 5. Buy existing asset (AAPL) with fee and tax calculation
    aapl_buy_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "Zerodha",
                "symbol": "AAPL",
                "transaction_type": "buy",
                "date": "2026-09-08",
                "quantity": 10,
                "price_per_unit": 150.0,
                "fees": 5.0,
                "taxes": 2.5
            }
        ]
    }
    aapl_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=aapl_buy_payload)
    assert aapl_res.status_code == 200
    tx_aapl = aapl_res.json()["results"][0]
    # Total cost = 10 * 150 + 5 + 2.5 = 1507.50
    assert tx_aapl["total_amount"] == 1507.50

    # 6. Verify FIFO Lot creation
    async with session_factory() as session:
        lots = (await session.execute(select(Lot).where(Lot.account_id == 1))).scalars().all()
        assert len(lots) == 2
        aapl_lot = next(l for l in lots if l.buy_transaction_id == tx_aapl["transaction_id"])
        assert aapl_lot.quantity_original == 10
        assert aapl_lot.quantity_remaining == 10
        # Cost per unit = 1507.50 / 10 = 150.75
        assert round(aapl_lot.cost_per_unit, 2) == 150.75

    # 7. Sell 4 shares of AAPL with fees/taxes
    aapl_sell_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "Zerodha",
                "symbol": "AAPL",
                "transaction_type": "sell",
                "date": "2026-09-12",
                "quantity": 4,
                "price_per_unit": 180.0,
                "fees": 3.0,
                "taxes": 1.0
            }
        ]
    }
    sell_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=aapl_sell_payload)
    assert sell_res.status_code == 200
    tx_sell = sell_res.json()["results"][0]
    # Net proceeds = 4 * 180 - 3 - 1 = 716.0
    assert tx_sell["total_amount"] == 716.0

    # Verify FIFO lot depletion
    async with session_factory() as session:
        refreshed_lot = (await session.execute(select(Lot).where(Lot.buy_transaction_id == tx_aapl["transaction_id"]))).scalar_one()
        assert refreshed_lot.quantity_remaining == 6.0 # 10 - 4

    # 8. Query GET /api/v1/mcp/stocks with asset filter
    filter_res = await client.get("/api/v1/mcp/stocks?asset=AAPL", headers=auth_headers)
    assert filter_res.status_code == 200
    filter_data = filter_res.json()
    assert filter_data["total_count"] == 2 # 1 buy, 1 sell for AAPL
    assert all(tx["asset_symbol"] == "AAPL" for tx in filter_data["transactions"])

    # 9. Query GET /api/v1/mcp/stocks with account filter
    acc_filter_res = await client.get("/api/v1/mcp/stocks?account=Zerodha", headers=auth_headers)
    assert acc_filter_res.status_code == 200
    acc_data = acc_filter_res.json()
    assert all(tx["account_name"] == "Zerodha" for tx in acc_data["transactions"])

    # 10. Performance check: Backdated transaction (600+ days ago) must return within 3 seconds
    import time
    backdated_payload = {
        "operations": [
            {
                "action": "create",
                "account_name": "Zerodha",
                "symbol": "AAPL",
                "transaction_type": "buy",
                "date": "2024-01-15",
                "quantity": 2,
                "price_per_unit": 140.0,
                "fees": 1.0,
                "taxes": 0.5
            }
        ]
    }
    t_start = time.time()
    backdated_res = await client.post("/api/v1/mcp/stocks", headers=auth_headers, json=backdated_payload)
    elapsed = time.time() - t_start
    assert backdated_res.status_code == 200
    assert elapsed < 3.0, f"Backdated transaction took {elapsed:.2f}s, exceeding 3.0s limit"

