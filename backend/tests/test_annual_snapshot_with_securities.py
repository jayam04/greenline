import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, PriceHistory, User
from app.api.routers.portfolio import get_annual_snapshot
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_annual_snapshot_includes_securities_valuation():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # Create bank ($5,000 USD cash) and demat (100 AAPL @ $200 = $20,000 USD, $0 cash)
        bank = Account(account_name="Main Bank", account_type="bank", currency="USD")
        demat = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add_all([bank, demat])
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)

        today = datetime.date.today()
        # Deposit $5,000 into bank
        dep = Transaction(
            account_id=bank.account_id,
            transaction_type="deposit",
            transaction_date=today,
            total_amount=5000.0
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        await process_transaction_event(session, dep)

        # Buy 100 AAPL in demat funded by bank ($20,000)
        asset = Asset(symbol="AAPL", name="Apple Inc", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Add price history: $250 / share
        ph = PriceHistory(
            asset_id=asset.asset_id,
            price_date=today,
            close_price=250.0
        )
        session.add(ph)
        await session.commit()

        # Buy 100 shares in demat
        buy_tx = Transaction(
            account_id=demat.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=today,
            quantity=100.0,
            price_per_unit=200.0,
            total_amount=20000.0,
            fees=0.0,
            taxes=0.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # Demat securities value = 100 * 250 = 25,000 USD
        # Demat cash = -20,000 USD, Bank cash = +5,000 USD -> Total cash = -15,000 USD
        # Total Net Worth in USD = 25,000 (securities) - 15,000 (cash) = 10,000 USD

        dummy_user = User(user_id=1, username="test_user", password_hash="hash")
        annual_resp = await get_annual_snapshot(
            fiscal_year_start="01-01",
            master_currency="USD",
            db=session,
            current_user=dummy_user
        )

        assert annual_resp.investments_done == 20000.0
        # If securities were omitted, net worth would be only -15,000 instead of +10,000
        assert annual_resp.net_worth_delta == 10000.0
