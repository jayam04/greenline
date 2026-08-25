import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, Lot, LotSale
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_fifo_account_isolation_prevents_cross_account_lot_consumption():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # 1. Create two separate accounts
        acc_a = Account(account_name="Brokerage A", account_type="demat", currency="USD")
        acc_b = Account(account_name="Brokerage B", account_type="demat", currency="USD")
        session.add_all([acc_a, acc_b])
        await session.commit()
        await session.refresh(acc_a)
        await session.refresh(acc_b)

        # 2. Create an asset
        asset = Asset(symbol="NVDA", name="NVIDIA Corp", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 3. Buy 10 shares in Account A
        buy_a = Transaction(
            account_id=acc_a.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 1),
            quantity=10.0,
            price_per_unit=100.0,
            total_amount=1000.0,
            fees=5.0,
            taxes=0.0
        )
        session.add(buy_a)
        await session.commit()
        await session.refresh(buy_a)
        await process_transaction_event(session, buy_a)

        # Verify Account A has lot with 10 shares
        lot_a_res = await session.execute(select(Lot).where(Lot.account_id == acc_a.account_id))
        lot_a = lot_a_res.scalar_one()
        assert lot_a.quantity_remaining == 10.0

        # 4. Sell 5 shares in Account B (which has 0 shares)
        sell_b = Transaction(
            account_id=acc_b.account_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2025, 2, 1),
            quantity=5.0,
            price_per_unit=120.0,
            total_amount=600.0,
            fees=5.0,
            taxes=0.0
        )
        session.add(sell_b)
        await session.commit()
        await session.refresh(sell_b)
        await process_transaction_event(session, sell_b)

        # 5. Verify Account A's lot was NOT touched
        await session.refresh(lot_a)
        assert lot_a.quantity_remaining == 10.0

        # Verify no lot sales were recorded against Account A's lot
        sales_res = await session.execute(select(LotSale).where(LotSale.lot_id == lot_a.lot_id))
        assert len(sales_res.scalars().all()) == 0
