import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, Lot, PriceHistory, NetworthSnapshot
from app.services.fifo_engine import process_transaction_event
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots, calculate_account_snapshots

@pytest.mark.anyio
async def test_date_specific_snapshot_calculation():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # Create test account & asset
        acc = Account(account_name="Test Demat", broker_name="Zerodha", account_type="demat", currency="USD")
        ast = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", exchange="NASDAQ")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)

        # Day 1 (2025-01-01): Deposit $10,000
        t_dep = Transaction(
            account_id=acc.account_id,
            asset_id=None,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=10000.0
        )
        session.add(t_dep)
        await session.commit()

        # Day 5 (2025-01-05): Buy 10 AAPL @ $150 = $1,500 total amount
        t_buy = Transaction(
            account_id=acc.account_id,
            asset_id=ast.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=10.0,
            price_per_unit=150.0,
            total_amount=1500.0,
            fees=10.0
        )
        session.add(t_buy)
        await session.commit()
        await session.refresh(t_buy)
        await process_transaction_event(session, t_buy)
        await session.commit()

        # Add price history for AAPL on Day 10 (2025-01-10) @ $180
        ph = PriceHistory(asset_id=ast.asset_id, price_date=datetime.date(2025, 1, 10), close_price=180.0, source="yfinance")
        session.add(ph)
        await session.commit()

        # Generate snapshot for Day 4 (before buy)
        snap_d4 = await generate_daily_snapshot(session, datetime.date(2025, 1, 4))
        assert snap_d4.total_invested == 10000.0
        assert snap_d4.cash_balance == 10000.0
        assert snap_d4.total_current_value == 0.0
        assert snap_d4.net_worth == 10000.0

        # Generate snapshot for Day 5 (day of buy)
        snap_d5 = await generate_daily_snapshot(session, datetime.date(2025, 1, 5))
        assert snap_d5.cash_balance == 8490.0  # 10000 - 1500 - 10
        assert snap_d5.total_current_value == 1510.0  # 10 * 151.0 (cost per unit fallback inclusive of fees)
        assert snap_d5.net_worth == 10000.0  # 8490 cash + 1510 stock

        # Generate snapshot for Day 10 (price updated to $180)
        snap_d10 = await generate_daily_snapshot(session, datetime.date(2025, 1, 10))
        assert snap_d10.cash_balance == 8490.0
        assert snap_d10.total_current_value == 1800.0  # 10 * 180
        assert snap_d10.total_unrealized_pnl == 290.0  # 1800 - 1510
        assert snap_d10.net_worth == 10290.0  # 8490 + 1800

@pytest.mark.anyio
async def test_recalculate_past_snapshots_range():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        acc = Account(account_name="Test Demat 2", broker_name="Zerodha", account_type="demat")
        ast = Asset(symbol="MSFT", name="Microsoft", asset_type="stock")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)

        # Deposit $5,000 on 2025-01-01
        t_dep = Transaction(
            account_id=acc.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=5000.0
        )
        session.add(t_dep)
        await session.commit()

        # Recalculate snapshots from 2025-01-01 to 2025-01-05
        await recalculate_past_snapshots(session, start_date=datetime.date(2025, 1, 1), end_date=datetime.date(2025, 1, 5))

        # Check snapshots exist for all 5 days
        snaps_stmt = select(NetworthSnapshot).order_by(NetworthSnapshot.snapshot_date)
        snaps_res = await session.execute(snaps_stmt)
        snaps = snaps_res.scalars().all()
        assert len(snaps) == 5
        for snap in snaps:
            assert snap.cash_balance == 5000.0
            assert snap.net_worth == 5000.0

@pytest.mark.anyio
async def test_historical_asset_backfill_from_past_date():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # Account created today
        acc = Account(account_name="Account Created Today", account_type="demat")
        ast = Asset(symbol="NVDA", name="NVIDIA Corp", asset_type="stock")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)

        # Transaction 120 days ago (approx 4 months ago)
        past_date = datetime.date.today() - datetime.timedelta(days=120)
        t_buy = Transaction(
            account_id=acc.account_id,
            asset_id=ast.asset_id,
            transaction_type="buy",
            transaction_date=past_date,
            quantity=10.0,
            price_per_unit=100.0,
            total_amount=1000.0
        )
        session.add(t_buy)
        await session.commit()
        await session.refresh(t_buy)
        await process_transaction_event(session, t_buy)
        await session.commit()

        # Recalculate past snapshots from past_date to today
        count = await recalculate_past_snapshots(session, start_date=past_date)
        assert count == 121  # 120 days + today

        # Check snapshot for past_date
        snap_stmt = select(NetworthSnapshot).where(NetworthSnapshot.snapshot_date == past_date)
        snap_res = await session.execute(snap_stmt)
        snap = snap_res.scalar_one_or_none()
        assert snap is not None
        assert snap.total_current_value == 1000.0

@pytest.mark.anyio
async def test_funding_account_timeline_start_date():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # Bank account created today (e.g. Jupiter)
        bank = Account(account_name="Funding Bank", account_type="bank", created_at=datetime.date(2026, 8, 25))
        demat = Account(account_name="Demat", account_type="demat", created_at=datetime.date(2026, 8, 25))
        ast = Asset(symbol="STOCK", name="Stock", asset_type="stock")
        session.add_all([bank, demat, ast])
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)
        await session.refresh(ast)

        # Purchase 20 days ago funded from bank
        past_date = datetime.date(2026, 8, 5)
        t_buy = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=ast.asset_id,
            transaction_type="buy",
            transaction_date=past_date,
            quantity=10.0,
            price_per_unit=100.0,
            total_amount=1000.0
        )
        session.add(t_buy)
        await session.commit()

        # Compute account snapshots for bank
        bank_snaps = await calculate_account_snapshots(session, account_id=bank.account_id, end_date=datetime.date(2026, 8, 25))
        assert len(bank_snaps) > 0
        assert bank_snaps[0]["snapshot_date"] == past_date
        assert bank_snaps[0]["cash_balance"] == -1000.0

