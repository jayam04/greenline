import datetime
from unittest.mock import patch
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, CorporateAction, User
from app.services.dividend_engine import (
    calculate_shares_on_date,
    sync_dividends_for_asset,
    sync_all_dividends,
)

@pytest.mark.anyio
async def test_calculate_shares_on_date_with_splits_and_sells():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        account = Account(account_name="Demat 1", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 1. Buy 100 shares on 2024-01-10
        session.add(Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 1, 10),
            quantity=100.0,
            price_per_unit=150.0,
            total_amount=15000.0,
            source="manual"
        ))

        # 2. 2:1 Stock Split on 2024-06-01
        session.add(CorporateAction(
            asset_id=asset.asset_id,
            action_type="split",
            action_date=datetime.date(2024, 6, 1),
            ratio="2:1"
        ))

        # 3. Sell 50 shares on 2024-08-01
        session.add(Transaction(
            account_id=account.account_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2024, 8, 1),
            quantity=50.0,
            price_per_unit=180.0,
            total_amount=9000.0,
            source="manual"
        ))
        await session.commit()

        # Before Buy: 0 shares
        sh_0 = await calculate_shares_on_date(session, asset.asset_id, account.account_id, datetime.date(2024, 1, 1))
        assert sh_0 == 0.0

        # After Buy, Before Split: 100 shares
        sh_1 = await calculate_shares_on_date(session, asset.asset_id, account.account_id, datetime.date(2024, 3, 15))
        assert sh_1 == 100.0

        # After Split, Before Sell: 200 shares
        sh_2 = await calculate_shares_on_date(session, asset.asset_id, account.account_id, datetime.date(2024, 7, 15))
        assert sh_2 == 200.0

        # After Sell: 150 shares
        sh_3 = await calculate_shares_on_date(session, asset.asset_id, account.account_id, datetime.date(2024, 9, 15))
        assert sh_3 == 150.0

@pytest.mark.anyio
async def test_sync_dividends_for_asset_auto_creation_and_orphan_cleanup():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        account = Account(account_name="Zerodha Demat", account_type="demat", currency="USD")
        session.add(account)
        await session.commit()
        await session.refresh(account)

        asset = Asset(symbol="MSFT", name="Microsoft Corp.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        aid = asset.asset_id
        acc_id = account.account_id

        # Initial Buy: 50 shares on 2024-01-01
        buy_tx = Transaction(
            account_id=acc_id,
            asset_id=aid,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 1, 1),
            quantity=50.0,
            price_per_unit=300.0,
            total_amount=15000.0,
            source="manual"
        )
        session.add(buy_tx)

        # Pre-existing manual dividend for another date
        manual_div = Transaction(
            account_id=acc_id,
            asset_id=aid,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 12, 1),
            quantity=50.0,
            price_per_unit=1.0,
            total_amount=50.0,
            source="manual",
            notes="Custom special dividend"
        )
        session.add(manual_div)
        await session.commit()

        mocked_yfinance_dividends = [
            (datetime.date(2024, 2, 15), 0.75),  # 50 * 0.75 = 37.50
            (datetime.date(2024, 5, 15), 0.75),  # 50 * 0.75 = 37.50
            (datetime.date(2023, 11, 15), 0.75), # Held 0 -> should NOT create
        ]

        with patch("app.services.dividend_engine.fetch_yfinance_dividends", return_value=mocked_yfinance_dividends):
            changes = await sync_dividends_for_asset(session, aid)
            assert changes >= 2

        # Verify created dividend transactions
        stmt = select(Transaction).where(
            Transaction.asset_id == aid,
            Transaction.transaction_type == "dividend"
        ).order_by(Transaction.transaction_date)
        res = await session.execute(stmt)
        divs = res.scalars().all()

        # Should have 2 auto-generated + 1 manual = 3 dividends
        assert len(divs) == 3

        feb_div = next(d for d in divs if d.transaction_date == datetime.date(2024, 2, 15))
        assert feb_div.source == "yfinance_auto"
        assert feb_div.quantity == 50.0
        assert feb_div.price_per_unit == 0.75
        assert feb_div.total_amount == 37.50
        assert feb_div.funding_account_id is None

        # Verify manual entry is preserved exactly
        dec_div = next(d for d in divs if d.transaction_date == datetime.date(2024, 12, 1))
        assert dec_div.source == "manual"
        assert dec_div.notes == "Custom special dividend"

        # Now simulate selling all shares on 2024-03-01 (so May dividend held shares become 0)
        sell_tx = Transaction(
            account_id=acc_id,
            asset_id=aid,
            transaction_type="sell",
            transaction_date=datetime.date(2024, 3, 1),
            quantity=50.0,
            price_per_unit=350.0,
            total_amount=17500.0,
            source="manual"
        )
        session.add(sell_tx)
        await session.commit()

        # Re-sync dividends
        with patch("app.services.dividend_engine.fetch_yfinance_dividends", return_value=mocked_yfinance_dividends):
            await sync_dividends_for_asset(session, aid)

        # Check dividends again
        res2 = await session.execute(stmt)
        divs2 = res2.scalars().all()
        # May dividend should be auto-deleted because held shares = 0!
        assert len(divs2) == 2
        dates = [d.transaction_date for d in divs2]
        assert datetime.date(2024, 2, 15) in dates
        assert datetime.date(2024, 5, 15) not in dates
        assert datetime.date(2024, 12, 1) in dates
