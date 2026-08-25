import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, PriceHistory
from app.api.routers.accounts import calculate_all_account_details
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_calculate_all_account_details_direct_valuation():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        demat = Account(account_name="Direct Demat", account_type="demat", currency="USD")
        bank = Account(account_name="Funding Bank", account_type="bank", currency="USD")
        session.add_all([demat, bank])
        await session.commit()
        await session.refresh(demat)
        await session.refresh(bank)

        # Deposit 10,000 in bank
        dep = Transaction(
            account_id=bank.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=10000.0
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        await process_transaction_event(session, dep)

        # Buy 50 NVDA @ $100 in demat funded by bank
        nvda = Asset(symbol="NVDA", name="NVIDIA Corp", asset_type="stock", currency="USD")
        session.add(nvda)
        await session.commit()
        await session.refresh(nvda)

        ph = PriceHistory(
            asset_id=nvda.asset_id,
            price_date=datetime.date(2025, 1, 5),
            close_price=120.0
        )
        session.add(ph)
        await session.commit()

        buy_tx = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=nvda.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=50.0,
            price_per_unit=100.0,
            total_amount=5000.0,
            fees=20.0,
            taxes=0.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # Calculate details
        details = await calculate_all_account_details(session)

        # Bank: cash = 10000 - 5020 = 4980.0, securities = 0.0, current_balance = 4980.0
        assert details[bank.account_id]["cash_balance"] == 4980.0
        assert details[bank.account_id]["securities_value"] == 0.0
        assert details[bank.account_id]["current_balance"] == 4980.0

        # Demat: cash = 0.0, securities = 50 * 120 = 6000.0, current_balance = 6000.0
        assert details[demat.account_id]["cash_balance"] == 0.0
        assert details[demat.account_id]["securities_value"] == 6000.0
        assert details[demat.account_id]["current_balance"] == 6000.0
