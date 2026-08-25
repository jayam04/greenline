import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, PriceHistory, User
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.fifo_engine import process_transaction_event

@pytest.mark.anyio
async def test_generate_daily_snapshot_multicurrency_and_funding():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # USD Bank account and EUR Demat account
        # FX_RATES_TO_EUR: USD = 0.92, EUR = 1.0
        usd_bank = Account(account_name="US Bank", account_type="bank", currency="USD")
        eur_demat = Account(account_name="EU Demat", account_type="demat", currency="EUR")
        session.add_all([usd_bank, eur_demat])
        await session.commit()
        await session.refresh(usd_bank)
        await session.refresh(eur_demat)

        # Deposit $10,000 USD into usd_bank
        # 10,000 USD * 0.92 = 9,200 EUR
        dep = Transaction(
            account_id=usd_bank.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=10000.0
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        await process_transaction_event(session, dep)

        # Buy 100 EUR stock in eur_demat, funded by usd_bank (say $1000 USD)
        asset = Asset(symbol="SAP", name="SAP SE", asset_type="stock", currency="EUR")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        ph = PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2025, 1, 5),
            close_price=100.0
        )
        session.add(ph)
        await session.commit()

        # Buy 10 SAP @ 100 EUR = 1000 EUR
        # Funded from usd_bank: $1000 USD outlay (920 EUR)
        buy_tx = Transaction(
            account_id=eur_demat.account_id,
            funding_account_id=usd_bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 1, 5),
            quantity=10.0,
            price_per_unit=100.0,
            total_amount=1000.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # Daily snapshot as of 2025-01-06
        snap = await generate_daily_snapshot(session, snapshot_date=datetime.date(2025, 1, 6))

        # USD Bank cash remaining = 10,000 - 1,000 = 9,000 USD
        # EUR Demat securities = 10 * 100 EUR = 1,000 EUR
        assert round(snap.cash_balance, 2) == 9000.0
        assert round(snap.total_current_value, 2) == 1000.0
        assert round(snap.net_worth, 2) == 10000.0

        # And verify list_snapshots normalizes USD to EUR: 9,000 * 0.92 + 1,000 * 1.0 = 8,280 + 1,000 = 9,280 EUR
        dummy_user = User(user_id=1, username="test_user", password_hash="hash")
        from app.api.routers.snapshots import list_snapshots
        aggregated = await list_snapshots(account_id=None, db=session, current_user=dummy_user)
        assert len(aggregated) > 0
        latest_agg = aggregated[-1]
        assert round(latest_agg.cash_balance, 2) == 8280.0
        assert round(latest_agg.total_current_value, 2) == 1000.0
        assert round(latest_agg.net_worth, 2) == 9280.0
