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

        # Verify created expected dividend records in Table B
        from app.db.models import ExpectedDividend
        exp_stmt = select(ExpectedDividend).where(
            ExpectedDividend.asset_id == aid
        ).order_by(ExpectedDividend.ex_date)
        res = await session.execute(exp_stmt)
        exp_divs = res.scalars().all()

        # Should have 2 expected dividends in Table B
        assert len(exp_divs) == 2
        feb_exp = next(d for d in exp_divs if d.ex_date == datetime.date(2024, 2, 15))
        assert feb_exp.eligible_shares == 50.0
        assert feb_exp.dividend_rate == 0.75
        assert feb_exp.expected_amount == 37.50
        assert feb_exp.status == "UNMATCHED"

        # Verify Table C has ONLY the manual dividend (never auto-inserted)
        stmt = select(Transaction).where(
            Transaction.asset_id == aid,
            Transaction.transaction_type == "dividend"
        ).order_by(Transaction.transaction_date)
        divs = (await session.execute(stmt)).scalars().all()
        assert len(divs) == 1
        assert divs[0].source == "manual"
        assert divs[0].notes == "Custom special dividend"

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

        # Check Table B expected dividends again
        res2 = await session.execute(exp_stmt)
        exp_divs2 = res2.scalars().all()
        # May dividend should be auto-deleted from Table B because held shares = 0 and unlinked!
        assert len(exp_divs2) == 1
        assert exp_divs2[0].ex_date == datetime.date(2024, 2, 15)

@pytest.mark.anyio
async def test_calculate_shares_on_ex_date_boundary_and_deterministic_matching():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        bank = Account(account_name="Bank 1", account_type="bank", currency="USD")
        demat = Account(account_name="Demat 1", account_type="demat", currency="USD")
        session.add_all([bank, demat])
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)

        asset = Asset(symbol="GOOGL", name="Alphabet Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 1. Buy 100 shares on 2024-05-01
        session.add(Transaction(
            account_id=demat.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 5, 1),
            quantity=100.0,
            price_per_unit=100.0,
            total_amount=10000.0,
            source="manual"
        ))

        # 2. On ex-date 2024-06-01:
        # - Sell 50 shares
        session.add(Transaction(
            account_id=demat.account_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2024, 6, 1),
            quantity=50.0,
            price_per_unit=110.0,
            total_amount=5500.0,
            source="manual"
        ))
        # - Buy 200 shares
        session.add(Transaction(
            account_id=demat.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 6, 1),
            quantity=200.0,
            price_per_unit=110.0,
            total_amount=22000.0,
            source="manual"
        ))
        # - 2:1 Split effective on ex-date
        session.add(CorporateAction(
            asset_id=asset.asset_id,
            action_type="split",
            action_date=datetime.date(2024, 6, 1),
            ratio="2:1"
        ))

        # 3. Add two existing transactions in Table C:
        # tx1: $25 dividend on 2024-06-10 (unrelated amount)
        tx_other = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 6, 10),
            quantity=25.0,
            price_per_unit=1.0,
            total_amount=25.0,
            source="manual"
        )
        # tx2: $200 dividend on 2024-06-15 (matching amount: 200 shares * $1.00)
        tx_match = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 6, 15),
            quantity=200.0,
            price_per_unit=1.0,
            total_amount=200.0,
            source="manual"
        )
        session.add_all([tx_other, tx_match])
        await session.commit()

        # Check share calculations:
        # Standard holdings at end of day 2024-06-01: (100 * 2) - 50 + 200 = 350.0
        standard_shares = await calculate_shares_on_date(session, asset.asset_id, demat.account_id, datetime.date(2024, 6, 1))
        assert standard_shares == 350.0

        # Dividend eligible shares for ex-date 2024-06-01:
        # Held prior to ex-date: 100 shares * 2 (split on ex-date) = 200.0 shares.
        # Buys on ex-date not eligible; sells on ex-date do not disqualify.
        eligible_shares = await calculate_shares_on_date(session, asset.asset_id, demat.account_id, datetime.date(2024, 6, 1), for_dividend_ex_date=True)
        assert eligible_shares == 200.0

        # Run dividend sync with rate $1.00 on 2024-06-01
        with patch("app.services.dividend_engine.fetch_yfinance_dividends", return_value=[(datetime.date(2024, 6, 1), 1.0)]):
            changes = await sync_dividends_for_asset(session, asset.asset_id)
            assert changes >= 1

        from app.db.models import ExpectedDividend
        exp_res = await session.execute(select(ExpectedDividend).where(ExpectedDividend.asset_id == asset.asset_id))
        exp = exp_res.scalar_one()

        assert exp.eligible_shares == 200.0
        assert exp.expected_amount == 200.0
        # Deterministic match must match tx_match ($200), not tx_other ($25)
        assert exp.matched_transaction_id == tx_match.transaction_id
        assert exp.status == "MATCHED"
