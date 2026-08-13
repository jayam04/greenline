import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, Lot, LotSale
from app.services.fifo_engine import process_transaction_event
from app.services.xirr_engine import calculate_xirr_for_scope

@pytest.mark.asyncio
async def test_fifo_lot_engine():
    # In-memory async SQLite engine for testing
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # Create test account & asset
        acc = Account(account_name="Test Zerodha", broker_name="Zerodha", account_type="demat")
        ast = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)
        
        # 1. Buy transaction 1: 10 units @ $150 on Day 1
        t1 = Transaction(
            account_id=acc.account_id,
            asset_id=ast.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1),
            quantity=10.0,
            price_per_unit=150.0,
            total_amount=1500.0,
            fees=10.0
        )
        session.add(t1)
        await session.commit()
        await session.refresh(t1)
        await process_transaction_event(session, t1)
        await session.commit()
        
        # 2. Buy transaction 2: 10 units @ $170 on Day 10
        t2 = Transaction(
            account_id=acc.account_id,
            asset_id=ast.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 10),
            quantity=10.0,
            price_per_unit=170.0,
            total_amount=1700.0,
            fees=10.0
        )
        session.add(t2)
        await session.commit()
        await session.refresh(t2)
        await process_transaction_event(session, t2)
        await session.commit()
        
        # 3. Sell transaction: 15 units @ $200 on Day 20
        t3 = Transaction(
            account_id=acc.account_id,
            asset_id=ast.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2025, 1, 20),
            quantity=15.0,
            price_per_unit=200.0,
            total_amount=3000.0,
            fees=15.0
        )
        session.add(t3)
        await session.commit()
        await session.refresh(t3)
        await process_transaction_event(session, t3)
        await session.commit()
        
        # Assertions
        # Check lot sales: should have 2 lot_sales records (10 from Lot 1, 5 from Lot 2)
        sales = (await session.execute(Transaction.__table__.select())).all()
        assert len(sales) == 3
        
        # Check remaining lot quantity: Lot 1 should have 0, Lot 2 should have 5 remaining
        lots = (await session.execute(Lot.__table__.select().order_by(Lot.lot_id))).all()
        assert len(lots) == 2
        assert lots[0].quantity_remaining == 0.0
        assert lots[1].quantity_remaining == 5.0
        
        # Check realized PnL
        lot_sales = (await session.execute(LotSale.__table__.select())).all()
        assert len(lot_sales) == 2
        # LotSale 1: 10 units @ cost basis 1500 -> sale 2000 -> PnL +500
        assert lot_sales[0].quantity_sold == 10.0
        assert lot_sales[0].cost_basis == 1500.0
        assert lot_sales[0].realized_pnl == 500.0
        # LotSale 2: 5 units @ cost basis 850 -> sale 1000 -> PnL +150
        assert lot_sales[1].quantity_sold == 5.0
        assert lot_sales[1].cost_basis == 850.0
        assert lot_sales[1].realized_pnl == 150.0
