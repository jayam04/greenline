import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Lot, PriceHistory, Transaction, User
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_portfolio_summary_1day_price_change():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # 1. Create a test user
        user = User(
            username="daily_tester",
            password_hash="hashed_pw_test"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 2. Create demat account and asset
        account = Account(
            account_name="Trading Demat",
            account_type="demat",
            currency="USD"
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type="stock",
            currency="USD"
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 3. Create buy transaction: 10 shares bought @ $150
        tx = Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=10.0,
            price_per_unit=150.0,
            total_amount=1500.0
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        await process_transaction_event(session, tx)
        await session.commit()

        # 4. Insert 2 price history records:
        # 2026-08-24: $200 (previous day)
        # 2026-08-25: $210 (latest day) -> 1D Change: +$10 (+5%), Value 1D Delta: 10 * $10 = +$100
        ph1 = PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2026, 8, 24),
            close_price=200.0,
            source="test"
        )
        ph2 = PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2026, 8, 25),
            close_price=210.0,
            source="test"
        )
        session.add_all([ph1, ph2])
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
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/portfolio/summary")
            assert res.status_code == 200
            data = res.json()

            # Check holding metrics
            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "AAPL"
            assert holding["latest_price"] == 210.0
            assert holding["previous_price"] == 200.0
            assert holding["change_1d"] == 10.0
            assert round(holding["change_1d_pct"], 2) == 5.0
            assert holding["value_change_1d"] == 100.0

            # Check portfolio-level 1D metrics
            assert data["total_value_change_1d"] == 100.0
            assert round(data["total_change_1d_pct"], 2) == 5.0
    finally:
        app.dependency_overrides.clear()
