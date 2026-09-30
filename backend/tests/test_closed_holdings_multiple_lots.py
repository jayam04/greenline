import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, PriceHistory, User
from app.services.fifo_engine import recalculate_all_lots

@pytest.mark.anyio
async def test_closed_holdings_multiple_lots_portfolio_summary():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(user_id=1, username="closed_lot_user", password_hash="hash")
        session.add(user)

        demat_acc = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(demat_acc)
        await session.commit()
        await session.refresh(user)
        await session.refresh(demat_acc)
        demat_id = demat_acc.account_id

        asset = Asset(symbol="PLTR", name="Palantir Technologies", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        asset_id = asset.asset_id

        # 1. Three separate buy transactions creating 3 distinct lots
        b1 = Transaction(
            account_id=demat_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1),
            quantity=10.0,
            price_per_unit=20.0,
            total_amount=200.0,
            fees=0.0,
            taxes=0.0
        )
        b2 = Transaction(
            account_id=demat_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=10.0,
            price_per_unit=25.0,
            total_amount=250.0,
            fees=0.0,
            taxes=0.0
        )
        b3 = Transaction(
            account_id=demat_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 10),
            quantity=20.0,
            price_per_unit=30.0,
            total_amount=600.0,
            fees=0.0,
            taxes=0.0
        )
        session.add_all([b1, b2, b3])
        await session.commit()
        await recalculate_all_lots(session)

        # 2. Sell transaction fully selling all 40 shares across all 3 lots
        s1 = Transaction(
            account_id=demat_id,
            asset_id=asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2025, 1, 20),
            quantity=40.0,
            price_per_unit=35.0,
            total_amount=1400.0,
            fees=0.0,
            taxes=0.0
        )
        session.add(s1)
        await session.commit()
        await recalculate_all_lots(session)

        # Add price history
        ph = PriceHistory(
            asset_id=asset_id,
            price_date=datetime.date(2025, 1, 20),
            close_price=35.0
        )
        session.add(ph)
        await session.commit()

    async def override_get_db():
        async with TestSession() as session:
            yield session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/portfolio/summary")
            assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
            data = res.json()
            assert len(data["closed_holdings"]) == 1
            ch = data["closed_holdings"][0]
            assert ch["symbol"] == "PLTR"
            assert ch["quantity_held"] == 0.0
            # Total cost basis = 200 + 250 + 600 = 1050
            # Sale proceeds = 1400
            # Realized PnL = 1400 - 1050 = 350
            assert ch["realized_pnl"] == 350.0
    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()
