import pytest
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Transaction, Lot, CorporateAction, PriceHistory, Asset, Account
from app.services.fifo_engine import recalculate_all_lots
from app.api.routers.corporate_actions import create_corporate_action
from app.schemas.schemas import CorporateActionCreate

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
        
        # Sell 50 shares at 20 on Jan 10
        tx2 = Transaction(
            account_id=account_id,
            asset_id=asset_id,
            transaction_type="sell",
            transaction_date=date(2023, 1, 10),
            quantity=50.0,
            price_per_unit=20.0,
            total_amount=1000.0
        )
        session.add(tx2)
        
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
        assert lots[0].quantity_remaining == 50.0
        assert lots[0].cost_per_unit == 10.0
        
        # Add corporate action: 2:1 split on Jan 5
        ca = CorporateActionCreate(
            asset_id=asset_id,
            action_type="split",
            action_date=date(2023, 1, 5),
            ratio="2:1"
        )
        await create_corporate_action(ca, session, current_user=None)
        
        # The price history should be adjusted
        ph_after = (await session.execute(select(PriceHistory).where(PriceHistory.asset_id == asset_id))).scalars().first()
        assert ph_after.close_price == 5.0 # 10 / 2
        
        # Let's check lots.
        lots_after = (await session.execute(select(Lot))).scalars().all()
        assert len(lots_after) == 1
        assert lots_after[0].quantity_remaining == 150.0
        assert lots_after[0].cost_per_unit == 5.0
