import pytest
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Transaction, Lot, PriceHistory, Asset, Account
from app.services.fifo_engine import recalculate_all_lots

@pytest.mark.anyio
async def test_fifo_recalculate_with_corporate_action():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # Setup asset, account, transaction
        account = Account(account_name="Test Acc", account_type="demat")
        session.add(account)
        asset = Asset(symbol="PRIV", name="Private Asset", asset_type="Private Equity")
        session.add(asset)
        await session.flush()
        
        asset_id = asset.asset_id
        account_id = account.account_id

        # Buy 100 shares at 10 on Jan 1
        tx = Transaction(
            account_id=account_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=date(2023, 1, 1),
            quantity=100.0,
            price_per_unit=10.0,
            total_amount=1000.0
        )
        session.add(tx)
        
        # Add Price History on Jan 1
        ph = PriceHistory(
            asset_id=asset_id,
            price_date=date(2023, 1, 1),
            close_price=10.0
        )
        session.add(ph)
        
        await session.commit()
        
        # Recalculate without corp action first to make sure normal works
        await recalculate_all_lots(session)
        
        lots = (await session.execute(select(Lot))).scalars().all()
        assert len(lots) == 1
        assert lots[0].quantity_remaining == 100.0
        assert lots[0].cost_per_unit == 10.0
        
        # Add corporate action: 2:1 split on Jan 5 (adds 100 shares)
        tx_split = Transaction(
            account_id=account_id,
            asset_id=asset_id,
            transaction_type="split",
            transaction_date=date(2023, 1, 5),
            quantity=100.0,
            price_per_unit=0.0,
            total_amount=0.0
        )
        session.add(tx_split)
        await session.commit()
        
        await recalculate_all_lots(session)
        
        # Let's check lots.
        lots_after = (await session.execute(select(Lot))).scalars().all()
        assert len(lots_after) == 2
        assert lots_after[0].quantity_remaining == 100.0
        assert lots_after[0].cost_per_unit == 10.0
        assert lots_after[1].quantity_remaining == 100.0
        assert lots_after[1].cost_per_unit == 0.0
