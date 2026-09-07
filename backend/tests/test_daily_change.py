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
        user = User(username="tester1", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

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

        # Two consecutive price history records
        ph1 = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 24), close_price=200.0, source="test")
        ph2 = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=210.0, source="test")
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

            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "AAPL"
            assert holding["latest_price"] == 210.0
            assert holding["previous_price"] == 200.0
            assert holding["change_1d"] == 10.0
            assert round(holding["change_1d_pct"], 2) == 5.0
            assert holding["value_change_1d"] == 100.0

            assert data["total_value_change_1d"] == 100.0
            assert round(data["total_change_1d_pct"], 2) == 5.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_portfolio_summary_one_price_record():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tester2", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="MSFT", name="Microsoft", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        tx = Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=5.0,
            price_per_unit=300.0,
            total_amount=1500.0
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        await process_transaction_event(session, tx)
        await session.commit()

        # Only one price history record
        ph = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=320.0, source="test")
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
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/portfolio/summary")
            assert res.status_code == 200
            data = res.json()

            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "MSFT"
            assert holding["latest_price"] == 320.0
            # Fallback semantics: previous_price falls back to latest_price
            assert holding["previous_price"] == 320.0
            assert holding["change_1d"] == 0.0
            assert holding["change_1d_pct"] == 0.0
            assert holding["value_change_1d"] == 0.0
            assert data["total_value_change_1d"] == 0.0
            assert data["total_change_1d_pct"] == 0.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_portfolio_summary_no_price_records():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tester3", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="NVDA", name="Nvidia", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        tx = Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=8.0,
            price_per_unit=100.0,
            total_amount=800.0
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        await process_transaction_event(session, tx)
        await session.commit()

        # Zero price history records

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

            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "NVDA"
            assert holding["latest_price"] == 0.0
            assert holding["previous_price"] == 0.0
            assert holding["change_1d"] == 0.0
            assert holding["change_1d_pct"] == 0.0
            assert holding["value_change_1d"] == 0.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_portfolio_summary_zero_previous_price():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tester4", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="PENNY", name="Penny Stock", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        tx = Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=100.0,
            price_per_unit=1.0,
            total_amount=100.0
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        await process_transaction_event(session, tx)
        await session.commit()

        # Day 1: 0.0, Day 2: 2.0
        ph1 = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 24), close_price=0.0, source="test")
        ph2 = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=2.0, source="test")
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

            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "PENNY"
            assert holding["latest_price"] == 2.0
            assert holding["previous_price"] == 0.0
            assert holding["change_1d"] == 2.0
            # Division by zero avoided: change_1d_pct is 0.0
            assert holding["change_1d_pct"] == 0.0
            assert holding["value_change_1d"] == 200.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_portfolio_summary_multiple_assets_and_non_consecutive_dates():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tester5", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset1 = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        asset2 = Asset(symbol="TSLA", name="Tesla Inc.", asset_type="stock", currency="USD")
        session.add_all([asset1, asset2])
        await session.commit()
        await session.refresh(asset1)
        await session.refresh(asset2)

        # Asset 1: 10 shares
        tx1 = Transaction(
            account_id=account.account_id,
            asset_id=asset1.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=10.0,
            price_per_unit=150.0,
            total_amount=1500.0
        )
        # Asset 2: 5 shares
        tx2 = Transaction(
            account_id=account.account_id,
            asset_id=asset2.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=5.0,
            price_per_unit=200.0,
            total_amount=1000.0
        )
        session.add_all([tx1, tx2])
        await session.commit()
        await session.refresh(tx1)
        await session.refresh(tx2)
        await process_transaction_event(session, tx1)
        await process_transaction_event(session, tx2)
        await session.commit()

        # Asset 1 has 3 non-consecutive price records (should take 2026-08-25 as latest, 2026-08-20 as previous, ignoring 2026-08-10)
        ph1_old = PriceHistory(asset_id=asset1.asset_id, price_date=datetime.date(2026, 8, 10), close_price=170.0, source="test")
        ph1_prev = PriceHistory(asset_id=asset1.asset_id, price_date=datetime.date(2026, 8, 20), close_price=190.0, source="test")
        ph1_latest = PriceHistory(asset_id=asset1.asset_id, price_date=datetime.date(2026, 8, 25), close_price=210.0, source="test")

        # Asset 2 has 2 records with a weekend gap (Friday 2026-08-21 to Monday 2026-08-24)
        ph2_prev = PriceHistory(asset_id=asset2.asset_id, price_date=datetime.date(2026, 8, 21), close_price=250.0, source="test")
        ph2_latest = PriceHistory(asset_id=asset2.asset_id, price_date=datetime.date(2026, 8, 24), close_price=240.0, source="test")

        session.add_all([ph1_old, ph1_prev, ph1_latest, ph2_prev, ph2_latest])
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

            assert len(data["top_holdings"]) == 2
            h_map = {h["symbol"]: h for h in data["top_holdings"]}

            # AAPL: latest=210, prev=190 -> delta = +20 (+10.53%), value_change = 10 * 20 = +200
            aapl = h_map["AAPL"]
            assert aapl["latest_price"] == 210.0
            assert aapl["previous_price"] == 190.0
            assert aapl["change_1d"] == 20.0
            assert round(aapl["change_1d_pct"], 2) == round(20.0 / 190.0 * 100.0, 2)
            assert aapl["value_change_1d"] == 200.0

            # TSLA: latest=240, prev=250 -> delta = -10 (-4.0%), value_change = 5 * -10 = -50
            tsla = h_map["TSLA"]
            assert tsla["latest_price"] == 240.0
            assert tsla["previous_price"] == 250.0
            assert tsla["change_1d"] == -10.0
            assert round(tsla["change_1d_pct"], 2) == -4.0
            assert tsla["value_change_1d"] == -50.0

            # Portfolio total: +200 - 50 = +150
            assert data["total_value_change_1d"] == 150.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_price_history_rejects_duplicate_dates_per_schema():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        asset = Asset(symbol="DUP", name="Duplicate Date Asset", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        ph1 = PriceHistory(price_id=1, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=105.0, source="test")
        ph2 = PriceHistory(price_id=2, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=110.0, source="test")
        session.add_all([ph1, ph2])
        with pytest.raises(Exception) as exc_info:
            await session.commit()
        assert "UNIQUE constraint failed" in str(exc_info.value)

@pytest.mark.anyio
async def test_portfolio_summary_three_or_more_price_records():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tester6", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        account = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="MANY", name="Many Prices Asset", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        tx = Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=10.0,
            price_per_unit=100.0,
            total_amount=1000.0
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        await process_transaction_event(session, tx)
        await session.commit()

        # 4 records with distinct dates
        ph1 = PriceHistory(price_id=1, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 20), close_price=90.0, source="test")
        ph2 = PriceHistory(price_id=2, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 22), close_price=95.0, source="test")
        ph3 = PriceHistory(price_id=3, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 24), close_price=105.0, source="test")
        ph4 = PriceHistory(price_id=4, asset_id=asset.asset_id, price_date=datetime.date(2026, 8, 25), close_price=110.0, source="test")

        session.add_all([ph1, ph2, ph3, ph4])
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

            assert len(data["top_holdings"]) == 1
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "MANY"
            # Should pick ph4 (2026-08-25) as latest (110.0)
            assert holding["latest_price"] == 110.0
            # And ph3 (2026-08-24) as previous (105.0)
            assert holding["previous_price"] == 105.0
            assert holding["change_1d"] == 5.0
            assert round(holding["change_1d_pct"], 2) == round(5.0 / 105.0 * 100.0, 2)
            assert holding["value_change_1d"] == 50.0
    finally:
        app.dependency_overrides.clear()

