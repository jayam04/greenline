import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, PriceHistory, User

@pytest.mark.anyio
async def test_custom_asset_valuations_crud():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="val_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        asset = Asset(symbol="STARTUP_EQ", name="Startup Equity", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Add manual custom valuation point
            res_add = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-10",
                "close_price": 120.0,
                "source": "manual"
            })
            assert res_add.status_code == 201
            price_id = res_add.json()["price_id"]
            assert res_add.json()["close_price"] == 120.0

            # 2. List custom valuations via GET /api/v1/prices/custom
            res_list = await ac.get("/api/v1/prices/custom")
            assert res_list.status_code == 200
            data = res_list.json()
            assert len(data) == 1
            assert data[0]["price_id"] == price_id
            assert data[0]["asset_symbol"] == "STARTUP_EQ"
            assert data[0]["close_price"] == 120.0
            assert data[0]["price_date"] == "2026-08-10"

            # 3. Delete manual custom valuation via DELETE /api/v1/prices/{price_id}
            res_del = await ac.delete(f"/api/v1/prices/{price_id}")
            assert res_del.status_code == 204

            # Verify list is now empty
            res_list2 = await ac.get("/api/v1/prices/custom")
            assert res_list2.status_code == 200
            assert len(res_list2.json()) == 0

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_manual_price_cannot_overwrite_market_price():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="market_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        asset = Asset(symbol="MKT", name="Market Stock", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Existing market price from yfinance
        ph = PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2026, 8, 15),
            close_price=150.0,
            source="yfinance"
        )
        session.add(ph)
        await session.commit()

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Attempt to overwrite existing market price with manual price
            res = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-15",
                "close_price": 999.0,
                "source": "manual"
            })
            # Must be rejected with 400 Bad Request to protect market price integrity
            assert res.status_code == 400
            assert "market" in res.json()["detail"].lower()

            # Verify market price remains intact in database
            async with TestSession() as session:
                q = await session.execute(select(PriceHistory).where(
                    PriceHistory.asset_id == asset.asset_id,
                    PriceHistory.price_date == datetime.date(2026, 8, 15)
                ))
                saved_ph = q.scalar_one()
                assert saved_ph.close_price == 150.0
                assert saved_ph.source == "yfinance"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_manual_price_boundary_validation():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="bound_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        asset = Asset(symbol="BOUND", name="Bound Asset", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Zero price
            res_zero = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-15",
                "close_price": 0.0,
                "source": "manual"
            })
            assert res_zero.status_code in [400, 422]

            # Negative price
            res_neg = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-15",
                "close_price": -50.0,
                "source": "manual"
            })
            assert res_neg.status_code in [400, 422]

            # Excessive price (> 1_000_000_000)
            res_huge = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-15",
                "close_price": 1e12,
                "source": "manual"
            })
            assert res_huge.status_code in [400, 422]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_custom_valuation_interleaving_and_market_update_protection():
    import pandas as pd
    from unittest.mock import patch
    from app.services.fifo_engine import recalculate_all_lots
    from app.services.price_engine import update_prices_for_assets
    from app.db.models import Transaction

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="interleave_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank = Account(account_name="Main Bank", account_type="bank", currency="USD")
        demat = Account(account_name="Main Demat", account_type="demat", currency="USD")
        session.add_all([bank, demat])
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)
        bank_id = bank.account_id
        demat_id = demat.account_id

        asset = Asset(symbol="INTL", name="Interleave Asset", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        asset_id = asset.asset_id

        # Deposit and buy 10 shares @ $80
        session.add(Transaction(account_id=bank_id, transaction_type="deposit", transaction_date=datetime.date(2026, 7, 1), total_amount=1000.0))
        session.add(Transaction(account_id=demat_id, funding_account_id=bank_id, asset_id=asset_id, transaction_type="buy", transaction_date=datetime.date(2026, 7, 10), quantity=10.0, price_per_unit=80.0, total_amount=800.0))

        # Historical market price on 2026-08-01: $100
        session.add(PriceHistory(asset_id=asset_id, price_date=datetime.date(2026, 8, 1), close_price=100.0, source="yfinance"))
        await session.commit()
        await recalculate_all_lots(session)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Add manual valuation on 2026-08-15: $120
            res_manual = await ac.post("/api/v1/prices/", json={
                "asset_id": asset_id,
                "price_date": "2026-08-15",
                "close_price": 120.0,
                "source": "manual"
            })
            assert res_manual.status_code == 201
            manual_price_id = res_manual.json()["price_id"]

            # 2. Check portfolio summary: latest is 120, previous is 100
            res_summary1 = await ac.get("/api/v1/portfolio/summary?target_currency=USD")
            assert res_summary1.status_code == 200
            h1 = res_summary1.json()["top_holdings"][0]
            assert h1["latest_price"] == 120.0
            assert h1["previous_price"] == 100.0
            assert h1["change_1d"] == 20.0
            assert h1["value_change_1d"] == 200.0

            # 3. Trigger market sync where market returns:
            # - 2026-08-15: 105.0 (should NOT overwrite the manual $120 price)
            # - 2026-08-16: 130.0 (new market price)
            df_mock = pd.DataFrame(
                {"Close": [105.0, 130.0]},
                index=[pd.Timestamp("2026-08-15"), pd.Timestamp("2026-08-16")]
            )
            async with TestSession() as session:
                with patch("app.services.price_engine._fetch_history_sync", return_value=df_mock):
                    with patch("app.services.dividend_engine.sync_dividends_for_asset", return_value=0):
                        await update_prices_for_assets(session, [asset_id])

                # Verify DB state
                ph_15 = (await session.execute(
                    select(PriceHistory).where(
                        PriceHistory.asset_id == asset_id,
                        PriceHistory.price_date == datetime.date(2026, 8, 15)
                    )
                )).scalar_one()
                assert ph_15.close_price == 120.0
                assert ph_15.source == "manual"

            # 4. Check portfolio summary: latest is now 130 (from 2026-08-16), previous is 120 (manual preserved!)
            res_summary2 = await ac.get("/api/v1/portfolio/summary?target_currency=USD")
            assert res_summary2.status_code == 200
            h2 = res_summary2.json()["top_holdings"][0]
            assert h2["latest_price"] == 130.0
            assert h2["previous_price"] == 120.0
            assert h2["change_1d"] == 10.0

            # 5. Delete manual valuation
            res_del = await ac.delete(f"/api/v1/prices/{manual_price_id}")
            assert res_del.status_code == 204

            # 6. Check portfolio summary: previous price now falls back to 2026-08-01 ($100)
            res_summary3 = await ac.get("/api/v1/portfolio/summary?target_currency=USD")
            assert res_summary3.status_code == 200
            h3 = res_summary3.json()["top_holdings"][0]
            assert h3["latest_price"] == 130.0
            assert h3["previous_price"] == 100.0
            assert h3["change_1d"] == 30.0
    finally:
        app.dependency_overrides.clear()


