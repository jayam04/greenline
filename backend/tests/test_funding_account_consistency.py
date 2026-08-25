import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, User
from app.api.routers.accounts import calculate_all_account_balances, calculate_all_account_cash_balances
from app.api.routers.portfolio import get_portfolio_summary
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_funding_account_consistency_between_accounts_and_portfolio_summary():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # 1. Create holding account (Demat) and funding account (Bank)
        demat = Account(account_name="Zerodha Demat", account_type="demat", currency="USD")
        bank = Account(account_name="HDFC Checking", account_type="bank", currency="USD")
        session.add_all([demat, bank])
        await session.commit()
        await session.refresh(demat)
        await session.refresh(bank)

        # 2. Deposit 5,000 in Bank
        dep = Transaction(
            account_id=bank.account_id,
            funding_account_id=None,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=5000.0
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        await process_transaction_event(session, dep)

        # 3. Buy 10 AAPL in Demat, funded by Bank
        asset = Asset(symbol="AAPL", name="Apple Inc", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        buy_tx = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=10.0,
            price_per_unit=200.0,
            total_amount=2000.0,
            fees=10.0,
            taxes=0.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # 4. Check account cash balances (pure liquid cash)
        cash_balances = await calculate_all_account_cash_balances(session)
        # Bank cash outlay = 2000 + 10 = 2010. Remaining in bank = 5000 - 2010 = 2990.
        assert cash_balances[bank.account_id] == 2990.0
        assert cash_balances[demat.account_id] == 0.0

        # Total account balances (cash + securities)
        total_balances = await calculate_all_account_balances(session)
        assert total_balances[bank.account_id] == 2990.0
        assert total_balances[demat.account_id] == 2010.0

        # 5. Check portfolio summary cash balance
        dummy_user = User(user_id=1, username="test_user", password_hash="hash")
        port_summary = await get_portfolio_summary(db=session, current_user=dummy_user)
        # Overall cash balance must match the sum of bank liquid cash balances
        assert port_summary.cash_balance == 2990.0
