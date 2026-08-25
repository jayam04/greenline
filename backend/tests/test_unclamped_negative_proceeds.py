import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction
from app.api.routers.accounts import compute_transaction_cash_movement, calculate_all_account_cash_balances
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_unclamped_negative_sale_proceeds():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        bank = Account(account_name="Broker Cash", account_type="bank", currency="USD")
        session.add(bank)
        await session.commit()
        await session.refresh(bank)

        asset = Asset(symbol="PENNY", name="Penny Stock", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Deposit $500
        dep = Transaction(
            account_id=bank.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=500.0
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        await process_transaction_event(session, dep)

        # Buy 100 shares @ $1 = $100
        buy_tx = Transaction(
            account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=100.0,
            price_per_unit=1.0,
            total_amount=100.0,
            fees=5.0,
            taxes=0.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # Sell 100 shares @ $1 = $100, but with broker fee $120 -> net proceeds = 100 - 120 = -$20
        sell_tx = Transaction(
            account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2025, 1, 10),
            quantity=100.0,
            price_per_unit=1.0,
            total_amount=100.0,
            fees=120.0,
            taxes=0.0
        )
        session.add(sell_tx)
        await session.commit()
        await session.refresh(sell_tx)
        await process_transaction_event(session, sell_tx)

        # Verify compute_transaction_cash_movement returns -20.0
        cash_acc, change = compute_transaction_cash_movement(sell_tx)
        assert cash_acc == bank.account_id
        assert change == -20.0

        # Cash balance = 500 (deposit) - 105 (buy) - 20 (sell loss/fees) = 375.0
        cash_bals = await calculate_all_account_cash_balances(session)
        assert cash_bals[bank.account_id] == 375.0
