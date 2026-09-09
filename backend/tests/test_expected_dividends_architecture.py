import datetime
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, ExpectedDividend, User, CashflowTransaction, CashflowPayment, CashflowItem, Category
from app.services.dividend_engine import sync_dividends_for_asset

@pytest.mark.anyio
@patch("app.services.dividend_engine.fetch_yfinance_dividends", new_callable=AsyncMock)
async def test_3tier_expected_dividends_lifecycle(mock_fetch_div):
    # Mock yfinance dividend announcement: 1.00 USD per share on ex_date 2024-06-15
    mock_fetch_div.return_value = [
        (datetime.date(2024, 6, 15), 1.00)
    ]

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="div_architect", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Chase Checking", account_type="bank", currency="USD")
        demat_acc = Account(account_name="Zerodha Demat", account_type="demat", currency="USD")
        session.add_all([bank_acc, demat_acc])

        cat = Category(name="Dividends", category_type="INCOME", default_label="INVESTMENT")
        session.add(cat)
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(demat_acc)
        await session.refresh(cat)

        # Asset (A)
        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 1. Buy 100 shares of AAPL on 2024-01-10 in Demat
        buy_tx = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=bank_acc.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 1, 10),
            quantity=100.0,
            price_per_unit=150.0,
            total_amount=15000.0,
            source="manual"
        )
        session.add(buy_tx)

        # 2. Add an existing bank cashflow credit on 2024-06-25 for $90.00 ($100 gross - $10 tax)
        cf_match = CashflowTransaction(
            transaction_date=datetime.date(2024, 6, 25),
            title="Dividend Cash Deposit AAPL",
            total_amount=90.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf_match)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_match.cashflow_id, account_id=bank_acc.account_id, amount=90.0))
        session.add(CashflowItem(cashflow_id=cf_match.cashflow_id, category_id=cat.category_id, amount=90.0, label="INVESTMENT"))

        await session.commit()

        # Step 1: Sync dividends for AAPL -> Populates Table B (ExpectedDividend) only
        changes = await sync_dividends_for_asset(session, asset.asset_id)
        assert changes >= 1

        # Verify Table B has expected dividend record
        exp_res = await session.execute(select(ExpectedDividend).where(ExpectedDividend.asset_id == asset.asset_id))
        exp_records = exp_res.scalars().all()
        assert len(exp_records) == 1
        exp_div = exp_records[0]
        assert exp_div.ex_date == datetime.date(2024, 6, 15)
        assert exp_div.eligible_shares == 100.0
        assert exp_div.dividend_rate == 1.00
        assert exp_div.expected_amount == 100.0
        assert exp_div.status == "UNMATCHED"
        assert exp_div.matched_transaction_id is None

        # Verify Table C (transactions) has NOT had any dividend transaction inserted automatically!
        tx_res = await session.execute(select(Transaction).where(Transaction.transaction_type == "dividend"))
        assert len(tx_res.scalars().all()) == 0

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Step 2: GET /api/v1/discrepancies/ returns unmatched expected dividend with candidate match
            res = await ac.get("/api/v1/discrepancies/")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == 1
            item = data["unlinked_items"][0]
            assert item["expected_dividend_id"] == exp_div.expected_dividend_id
            assert item["asset_symbol"] == "AAPL"
            assert item["quantity"] == 100.0
            assert item["total_amount"] == 100.0
            assert item["status"] == "UNMATCHED"
            assert len(item["candidate_matches"]) == 1
            assert item["candidate_matches"][0]["account_id"] == bank_acc.account_id

            # Step 3: Resolve discrepancy -> creates real transaction in Table C and links B <-> C
            res_resolve = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp_div.expected_dividend_id,
                        "funding_account_id": bank_acc.account_id,
                        "transaction_date": "2024-06-25",
                        "total_amount": 100.0,
                        "taxes": 10.0,
                        "notes": "Verified AAPL Dividend"
                    }
                ]
            })
            assert res_resolve.status_code == 200

            # Verify Table C now has real dividend transaction with expected_dividend_id
            async with TestSession() as session:
                div_txs = (await session.execute(select(Transaction).where(Transaction.transaction_type == "dividend"))).scalars().all()
                assert len(div_txs) == 1
                div_tx = div_txs[0]
                assert div_tx.funding_account_id == bank_acc.account_id
                assert div_tx.transaction_date == datetime.date(2024, 6, 25)
                assert div_tx.total_amount == 100.0
                assert div_tx.taxes == 10.0
                assert div_tx.expected_dividend_id == exp_div.expected_dividend_id

                # Verify Table B is now MATCHED with matched_transaction_id
                exp_after = await session.get(ExpectedDividend, exp_div.expected_dividend_id)
                assert exp_after.status == "MATCHED"
                assert exp_after.matched_transaction_id == div_tx.transaction_id

            # Discrepancies count is now 0
            res_zero = await ac.get("/api/v1/discrepancies/")
            assert res_zero.json()["total_count"] == 0

            # Step 4: User sells 50 shares on 2024-04-01 (before ex-date 2024-06-15)
            # Re-sync should adjust B to 50 shares ($50), but C remains $100 -> status AMOUNT_MISMATCH
            async with TestSession() as session:
                sell_tx = Transaction(
                    account_id=demat_acc.account_id,
                    funding_account_id=bank_acc.account_id,
                    asset_id=asset.asset_id,
                    transaction_type="sell",
                    transaction_date=datetime.date(2024, 4, 1),
                    quantity=50.0,
                    price_per_unit=170.0,
                    total_amount=8500.0,
                    source="manual"
                )
                session.add(sell_tx)
                await session.commit()

                # Re-sync dividends
                await sync_dividends_for_asset(session, asset.asset_id)

                # Verify Table B updated to 50 shares / $50 expected, but status is AMOUNT_MISMATCH
                exp_mismatch = await session.get(ExpectedDividend, exp_div.expected_dividend_id)
                assert exp_mismatch.eligible_shares == 50.0
                assert exp_mismatch.expected_amount == 50.0
                assert exp_mismatch.status == "AMOUNT_MISMATCH"

                # Verify Table C was NEVER deleted or mutated (remains $100)
                tx_c = await session.get(Transaction, div_tx.transaction_id)
                assert tx_c.total_amount == 100.0

            # Step 5: Discrepancies endpoint returns the AMOUNT_MISMATCH item
            res_mismatch = await ac.get("/api/v1/discrepancies/")
            assert res_mismatch.json()["total_count"] == 1
            mismatch_item = res_mismatch.json()["unlinked_items"][0]
            assert mismatch_item["status"] == "AMOUNT_MISMATCH"
            assert mismatch_item["expected_amount"] == 50.0
            assert mismatch_item["linked_transaction_amount"] == 100.0

            # Step 6: Test Unlinking the dividend
            res_unlink = await ac.post("/api/v1/discrepancies/unlink", json={
                "expected_dividend_ids": [exp_div.expected_dividend_id]
            })
            assert res_unlink.status_code == 200
            async with TestSession() as session:
                exp_unlinked = await session.get(ExpectedDividend, exp_div.expected_dividend_id)
                assert exp_unlinked.matched_transaction_id is None
                assert exp_unlinked.status == "UNMATCHED"
                # Table C transaction is preserved
                tx_preserved = await session.get(Transaction, div_tx.transaction_id)
                assert tx_preserved is not None
                assert tx_preserved.expected_dividend_id is None

            # Step 7: Test Dismissing an expected dividend
            res_dismiss = await ac.post("/api/v1/discrepancies/dismiss", json={
                "expected_dividend_ids": [exp_div.expected_dividend_id]
            })
            assert res_dismiss.status_code == 200
            async with TestSession() as session:
                exp_dismissed = await session.get(ExpectedDividend, exp_div.expected_dividend_id)
                assert exp_dismissed.status == "DISMISSED"

            # Verify dismissed item no longer appears in discrepancies summary
            res_after_dismiss = await ac.get("/api/v1/discrepancies/")
            assert res_after_dismiss.json()["total_count"] == 0

    finally:
        app.dependency_overrides.clear()

