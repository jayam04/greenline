import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base, get_db
from app.db.models import User, Account, Asset, Transaction, Lot, PriceHistory
from app.api.deps import get_current_user
from app.main import app

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
        yield session

@pytest.fixture
async def client(test_db_session):
    session = test_db_session
    mock_user = User(user_id=1, username="testuser")

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session

    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_annual_snapshot_calculates_net_worth_delta_from_price_movement(client):
    ac, session = client

    # 1. Create USD investment account
    acc = Account(account_name="Brokerage", account_type="demat", currency="USD")
    asset = Asset(symbol="AAPL", name="Apple Inc", asset_type="stock", currency="USD")
    session.add_all([acc, asset])
    await session.commit()
    await session.refresh(acc)
    await session.refresh(asset)

    # 2. Buy 10 shares @ $100 on 2025-11-01 (prior year) with $10,000 initial deposit
    dep_tx = Transaction(
        account_id=acc.account_id,
        transaction_type="deposit",
        transaction_date=datetime.date(2025, 11, 1),
        total_amount=10000.0,
    )
    session.add(dep_tx)
    await session.flush()

    buy_tx = Transaction(
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        transaction_type="buy",
        transaction_date=datetime.date(2025, 11, 2),
        quantity=10.0,
        price_per_unit=100.0,
        total_amount=1000.0,
    )
    session.add(buy_tx)
    await session.flush()

    lot = Lot(
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        buy_transaction_id=buy_tx.transaction_id,
        buy_date=datetime.date(2025, 11, 2),
        quantity_original=10.0,
        quantity_remaining=10.0,
        cost_per_unit=100.0,
    )
    session.add(lot)

    # Historical price as of end of 2025: $100
    ph1 = PriceHistory(
        asset_id=asset.asset_id,
        price_date=datetime.date(2025, 12, 31),
        close_price=100.0,
    )
    # Current price in 2026: $150 (50% stock appreciation)
    ph2 = PriceHistory(
        asset_id=asset.asset_id,
        price_date=datetime.date(2026, 6, 1),
        close_price=150.0,
    )
    session.add_all([ph1, ph2])
    await session.commit()

    # Query annual snapshot for CY in USD
    resp = await ac.get("/api/v1/portfolio/annual_snapshot?master_currency=USD&fiscal_year_start=01-01")
    assert resp.status_code == 200
    data = resp.json()

    # Net savings from cashflow is 0.0 (no income/expense logged)
    assert data["net_savings"] == 0.0

    # Start NW was $9,000 cash + 10 * $100 = $10,000
    # Current NW is $9,000 cash + 10 * $150 = $10,500
    # Net worth delta should be +$500 (+5.0%)
    assert data["net_worth_delta"] == 500.0
    assert data["net_worth_delta_pct"] == 5.0
    assert data["currency"] == "USD"
