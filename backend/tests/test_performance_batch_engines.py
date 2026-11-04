import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, Lot, LotSale, CashflowTransaction, CashflowPayment, CashflowItem, Category, PriceHistory, NetworthSnapshot
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import recalculate_past_snapshots
from app.api.routers.accounts import calculate_all_account_details


@pytest.mark.anyio
async def test_recalculate_all_lots_batch_preserves_fifo():
    engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        acc = Account(account_id=1, account_name="Demat", account_type="demat", currency="EUR")
        ast = Asset(asset_id=10, symbol="ABC", name="ABC Corp", asset_type="stock")
        session.add_all([acc, ast])
        await session.commit()

        # Buy 1: 10 units @ 100 on Jan 1
        t1 = Transaction(
            transaction_id=1, account_id=1, asset_id=10, transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1), quantity=10, price_per_unit=100,
            total_amount=1000, fees=0, taxes=0
        )
        # Buy 2: 10 units @ 120 on Jan 5
        t2 = Transaction(
            transaction_id=2, account_id=1, asset_id=10, transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5), quantity=10, price_per_unit=120,
            total_amount=1200, fees=0, taxes=0
        )
        # Sell: 15 units @ 150 on Jan 10 (should deplete all 10 of lot 1, and 5 of lot 2)
        t3 = Transaction(
            transaction_id=3, account_id=1, asset_id=10, transaction_type="sell",
            transaction_date=datetime.date(2025, 1, 10), quantity=15, price_per_unit=150,
            total_amount=2250, fees=0, taxes=0
        )
        session.add_all([t1, t2, t3])
        await session.commit()

        # Execute recalculate_all_lots
        await recalculate_all_lots(session)

        # Assert lots
        lots = (await session.execute(select(Lot).order_by(Lot.lot_id))).scalars().all()
        assert len(lots) == 2
        assert lots[0].quantity_original == 10
        assert lots[0].quantity_remaining == 0  # fully sold
        assert lots[1].quantity_original == 10
        assert lots[1].quantity_remaining == 5  # 5 remaining

        # Assert lot sales
        sales = (await session.execute(select(LotSale).order_by(LotSale.lot_sale_id))).scalars().all()
        assert len(sales) == 2
        # Lot 1 sale: 10 units @ 150 - cost basis 1000 = realized pnl 500
        assert sales[0].lot_id == lots[0].lot_id
        assert sales[0].quantity_sold == 10
        assert sales[0].realized_pnl == 500.0

        # Lot 2 sale: 5 units @ 150 - cost basis 600 = realized pnl 150
        assert sales[1].lot_id == lots[1].lot_id
        assert sales[1].quantity_sold == 5
        assert sales[1].realized_pnl == 150.0

    await engine.dispose()


@pytest.mark.anyio
async def test_recalculate_past_snapshots_batch():
    engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        acc = Account(account_id=1, account_name="Demat", account_type="demat", currency="EUR")
        ast = Asset(asset_id=10, symbol="ABC", name="ABC Corp", asset_type="stock")
        session.add_all([acc, ast])
        await session.commit()

        # Buy 10 units @ 100 on Jan 1
        t1 = Transaction(
            transaction_id=1, account_id=1, asset_id=10, transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1), quantity=10, price_per_unit=100,
            total_amount=1000, fees=0, taxes=0
        )
        session.add(t1)
        await session.commit()
        await recalculate_all_lots(session)

        # Price on Jan 1: 100, Price on Jan 3: 110
        session.add(PriceHistory(asset_id=10, price_date=datetime.date(2025, 1, 1), close_price=100.0, source="test"))
        session.add(PriceHistory(asset_id=10, price_date=datetime.date(2025, 1, 3), close_price=110.0, source="test"))
        await session.commit()

        # Recalculate past snapshots from Jan 1 to Jan 3
        count = await recalculate_past_snapshots(session, start_date=datetime.date(2025, 1, 1), end_date=datetime.date(2025, 1, 3))
        assert count == 3

        snaps = (await session.execute(select(NetworthSnapshot).order_by(NetworthSnapshot.snapshot_date))).scalars().all()
        assert len(snaps) == 3
        # Jan 1: 10 * 100 = 1000
        assert snaps[0].snapshot_date == datetime.date(2025, 1, 1)
        assert snaps[0].total_current_value == 1000.0
        # Jan 2: forward-fill Jan 1 price = 1000
        assert snaps[1].snapshot_date == datetime.date(2025, 1, 2)
        assert snaps[1].total_current_value == 1000.0
        # Jan 3: 10 * 110 = 1100
        assert snaps[2].snapshot_date == datetime.date(2025, 1, 3)
        assert snaps[2].total_current_value == 1100.0

    await engine.dispose()


@pytest.mark.anyio
async def test_calculate_all_account_details_fast_grouping():
    engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        acc1 = Account(account_id=1, account_name="Bank 1", account_type="bank", currency="EUR")
        acc2 = Account(account_id=2, account_name="Bank 2", account_type="bank", currency="EUR")
        cat = Category(category_id=1, name="Groceries", category_type="EXPENSE")
        session.add_all([acc1, acc2, cat])
        await session.commit()

        # Cashflow transaction with 2 payments
        cf = CashflowTransaction(
            cashflow_id=1, transaction_date=datetime.date(2025, 1, 1), title="Expense",
            total_amount=100.0, currency="EUR", transaction_kind="EXPENSE"
        )
        session.add(cf)
        await session.flush()

        p1 = CashflowPayment(payment_id=1, cashflow_id=1, account_id=1, amount=-60.0)
        p2 = CashflowPayment(payment_id=2, cashflow_id=1, account_id=2, amount=-40.0)
        item = CashflowItem(item_id=1, cashflow_id=1, category_id=1, amount=100.0)
        session.add_all([p1, p2, item])
        await session.commit()

        details = await calculate_all_account_details(session)
        assert details[1]["cash_balance"] == -60.0
        assert details[2]["cash_balance"] == -40.0

    await engine.dispose()


@pytest.mark.anyio
async def test_portfolio_summary_batching():
    from app.api.routers.portfolio import get_portfolio_summary
    from app.db.models import User

    engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        user = User(user_id=0, username="admin", password_hash="hash")
        acc = Account(account_id=1, account_name="Demat", account_type="demat", currency="EUR")
        ast1 = Asset(asset_id=1, symbol="OPEN_ASSET", name="Open Asset Corp", asset_type="stock", currency="EUR")
        ast2 = Asset(asset_id=2, symbol="CLOSED_ASSET", name="Closed Asset Corp", asset_type="stock", currency="EUR")
        session.add_all([user, acc, ast1, ast2])
        await session.commit()

        # Buy ast1: 10 units @ 100 on Jan 1
        t1 = Transaction(
            transaction_id=1, account_id=1, asset_id=1, transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1), quantity=10, price_per_unit=100,
            total_amount=1000
        )
        # Buy ast2: 5 units @ 50 on Jan 1
        t2 = Transaction(
            transaction_id=2, account_id=1, asset_id=2, transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1), quantity=5, price_per_unit=50,
            total_amount=250
        )
        # Sell all ast2 @ 70 on Jan 10 (closed holding with realized pnl = 5 * 20 = 100)
        t3 = Transaction(
            transaction_id=3, account_id=1, asset_id=2, transaction_type="sell",
            transaction_date=datetime.date(2025, 1, 10), quantity=5, price_per_unit=70,
            total_amount=350
        )
        session.add_all([t1, t2, t3])
        await session.commit()
        await recalculate_all_lots(session)

        # Price for ast1: 120
        session.add(PriceHistory(asset_id=1, price_date=datetime.date(2025, 1, 15), close_price=120.0, source="test"))
        # Price for ast2: 70
        session.add(PriceHistory(asset_id=2, price_date=datetime.date(2025, 1, 15), close_price=70.0, source="test"))
        await session.commit()

        summary = await get_portfolio_summary(db=session, current_user=user)
        # Check open holdings
        assert len(summary.top_holdings) == 1
        h1 = summary.top_holdings[0]
        assert h1.symbol == "OPEN_ASSET"
        assert h1.quantity_held == 10
        assert h1.current_value == 1200.0
        assert h1.unrealized_pnl == 200.0
        assert h1.currency == "EUR"

        # Check closed holdings
        assert len(summary.closed_holdings) == 1
        c1 = summary.closed_holdings[0]
        assert c1.symbol == "CLOSED_ASSET"
        assert c1.realized_pnl == 100.0
        assert c1.currency == "EUR"

    await engine.dispose()
