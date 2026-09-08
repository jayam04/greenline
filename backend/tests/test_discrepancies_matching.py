import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, Category, CashflowTransaction, CashflowPayment, CashflowItem, User

@pytest.mark.anyio
async def test_discrepancy_credit_date_and_candidate_matching():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="match_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Main Checking Bank", account_type="bank", currency="USD")
        demat_acc = Account(account_name="Main Demat", account_type="demat", currency="USD")
        session.add_all([bank_acc, demat_acc])

        cat = Category(name="Dividends", category_type="INCOME", default_label="INVESTMENT")
        session.add(cat)
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(demat_acc)
        await session.refresh(cat)

        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 1. Unlinked dividend with ex-dividend cut-off date: 2024-05-10
        div_tx = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=None,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 5, 10),
            quantity=50.0,
            price_per_unit=0.25,
            total_amount=12.50,
            taxes=0.0,
            source="yfinance_auto"
        )
        session.add(div_tx)

        # 2. Existing bank cashflow income transaction received on 2024-05-24 (within 90 days) for $12.50
        cf_match = CashflowTransaction(
            transaction_date=datetime.date(2024, 5, 24),
            title="Dividend Credit AAPL",
            total_amount=12.50,
            currency="USD",
            transaction_kind="INCOME",
            notes="Credited into bank"
        )
        session.add(cf_match)
        await session.flush()

        cf_payment = CashflowPayment(
            cashflow_id=cf_match.cashflow_id,
            account_id=bank_acc.account_id,
            amount=12.50
        )
        cf_item = CashflowItem(
            cashflow_id=cf_match.cashflow_id,
            category_id=cat.category_id,
            amount=12.50,
            label="INVESTMENT"
        )
        session.add_all([cf_payment, cf_item])

        # 3. An unrelated transaction older than 90 days (2024-01-01) for $12.50 (should NOT match)
        cf_old = CashflowTransaction(
            transaction_date=datetime.date(2024, 1, 1),
            title="Old Payment",
            total_amount=12.50,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf_old)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_old.cashflow_id, account_id=bank_acc.account_id, amount=12.50))
        session.add(CashflowItem(cashflow_id=cf_old.cashflow_id, category_id=cat.category_id, amount=12.50, label="INVESTMENT"))

        await session.commit()
        await session.refresh(div_tx)

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
            # Step 1: GET /api/v1/discrepancies/ and verify candidate match is detected
            res = await ac.get("/api/v1/discrepancies/")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == 1
            item = data["unlinked_items"][0]
            assert "candidate_matches" in item
            assert len(item["candidate_matches"]) == 1
            match = item["candidate_matches"][0]
            assert match["account_id"] == bank_acc.account_id
            assert match["account_name"] == "Main Checking Bank"
            assert match["date"] == "2024-05-24"
            assert match["amount"] == 12.50
            assert "Dividend Credit AAPL" in match["title"]

            # Step 2: Resolve discrepancy with explicit credit date (2024-05-24)
            res_resolve = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "transaction_id": div_tx.transaction_id,
                        "funding_account_id": bank_acc.account_id,
                        "transaction_date": "2024-05-24",
                        "taxes": 1.25,
                        "notes": "Confirmed credited date"
                    }
                ]
            })
            assert res_resolve.status_code == 200

            # Verify the dividend transaction now has updated credit date and funding account
            async with TestSession() as session:
                updated_tx = await session.get(Transaction, div_tx.transaction_id)
                assert updated_tx.funding_account_id == bank_acc.account_id
                assert updated_tx.transaction_date == datetime.date(2024, 5, 24)
                assert updated_tx.taxes == 1.25

            # Step 3: Verify auto-link-defaults endpoint is removed / disabled
            res_auto = await ac.post("/api/v1/discrepancies/auto-link-defaults")
            assert res_auto.status_code in [404, 405]

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_candidate_matching_currency_and_scoring():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="score_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        usd_bank = Account(account_name="USD Checking", account_type="bank", currency="USD")
        eur_bank = Account(account_name="EUR Savings", account_type="bank", currency="EUR")
        demat = Account(account_name="Demat Broker", account_type="demat", currency="USD")
        session.add_all([usd_bank, eur_bank, demat])

        cat = Category(name="Dividends", category_type="INCOME", default_label="INVESTMENT")
        session.add(cat)
        await session.commit()
        await session.refresh(usd_bank)
        await session.refresh(eur_bank)
        await session.refresh(demat)
        await session.refresh(cat)

        asset = Asset(symbol="NVDA", name="NVIDIA Corp", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Expected dividend of $100 USD on 2026-06-01
        from app.db.models import ExpectedDividend
        exp = ExpectedDividend(
            asset_id=asset.asset_id,
            account_id=demat.account_id,
            ex_date=datetime.date(2026, 6, 1),
            eligible_shares=100.0,
            dividend_rate=1.0,
            expected_amount=100.0,
            currency="USD",
            source="yfinance",
            status="UNMATCHED"
        )
        session.add(exp)
        await session.flush()

        # 1. Payment of 100 in EUR bank (Wrong currency: should NOT be a candidate match)
        cf_eur = CashflowTransaction(
            transaction_date=datetime.date(2026, 6, 5),
            title="EUR Dividend 100",
            total_amount=100.0,
            currency="EUR",
            transaction_kind="INCOME"
        )
        session.add(cf_eur)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_eur.cashflow_id, account_id=eur_bank.account_id, amount=100.0))
        session.add(CashflowItem(cashflow_id=cf_eur.cashflow_id, category_id=cat.category_id, amount=100.0, label="INVESTMENT"))

        # 2. Payment of 95 in USD bank on 2026-06-15 (Tax-withheld candidate)
        cf_usd_approx = CashflowTransaction(
            transaction_date=datetime.date(2026, 6, 15),
            title="USD Tax Withheld 95",
            total_amount=95.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf_usd_approx)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_usd_approx.cashflow_id, account_id=usd_bank.account_id, amount=95.0))
        session.add(CashflowItem(cashflow_id=cf_usd_approx.cashflow_id, category_id=cat.category_id, amount=95.0, label="INVESTMENT"))

        # 3. Exact payment of 100 in USD bank on 2026-06-10 (Exact amount candidate - higher score than 95)
        cf_usd_exact = CashflowTransaction(
            transaction_date=datetime.date(2026, 6, 10),
            title="USD Exact 100",
            total_amount=100.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf_usd_exact)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_usd_exact.cashflow_id, account_id=usd_bank.account_id, amount=100.0))
        session.add(CashflowItem(cashflow_id=cf_usd_exact.cashflow_id, category_id=cat.category_id, amount=100.0, label="INVESTMENT"))

        await session.commit()

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
            res = await ac.get("/api/v1/discrepancies/")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == 1
            item = data["unlinked_items"][0]
            matches = item.get("candidate_matches", [])

            # Must NOT include EUR bank payment
            account_ids = [m["account_id"] for m in matches]
            assert eur_bank.account_id not in account_ids

            # Must include USD candidate matches
            assert usd_bank.account_id in account_ids

            # Exact match (100.0) must be ranked ahead of partial match (95.0)
            assert len(matches) == 2
            assert matches[0]["amount"] == 100.0
            assert matches[0]["title"] == "USD Exact 100"
            assert matches[1]["amount"] == 95.0
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_candidate_matching_identical_scores_deterministic_ordering():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="tie_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank = Account(account_name="Tie Bank", account_type="bank", currency="USD")
        demat = Account(account_name="Tie Demat", account_type="demat", currency="USD")
        session.add_all([bank, demat])

        cat = Category(name="Dividends", category_type="INCOME", default_label="INVESTMENT")
        session.add(cat)
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)
        await session.refresh(cat)

        asset = Asset(symbol="MSFT", name="Microsoft", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        from app.db.models import ExpectedDividend
        exp = ExpectedDividend(
            asset_id=asset.asset_id,
            account_id=demat.account_id,
            ex_date=datetime.date(2026, 7, 1),
            eligible_shares=10.0,
            dividend_rate=5.0,
            expected_amount=50.0,
            currency="USD",
            status="UNMATCHED"
        )
        session.add(exp)
        await session.flush()

        # Two candidate cashflows on the EXACT same date (2026-07-05) for the EXACT same amount ($50.0)
        cf1 = CashflowTransaction(
            transaction_date=datetime.date(2026, 7, 5),
            title="Income Payment First",
            total_amount=50.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf1)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf1.cashflow_id, account_id=bank.account_id, amount=50.0))
        session.add(CashflowItem(cashflow_id=cf1.cashflow_id, category_id=cat.category_id, amount=50.0, label="INVESTMENT"))

        cf2 = CashflowTransaction(
            transaction_date=datetime.date(2026, 7, 5),
            title="Income Payment Second",
            total_amount=50.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf2)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf2.cashflow_id, account_id=bank.account_id, amount=50.0))
        session.add(CashflowItem(cashflow_id=cf2.cashflow_id, category_id=cat.category_id, amount=50.0, label="INVESTMENT"))

        # Third payment > 90 days after ex-date (2026-10-01)
        cf_too_late = CashflowTransaction(
            transaction_date=datetime.date(2026, 10, 1),
            title="Payment After 90 Days",
            total_amount=50.0,
            currency="USD",
            transaction_kind="INCOME"
        )
        session.add(cf_too_late)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=cf_too_late.cashflow_id, account_id=bank.account_id, amount=50.0))
        session.add(CashflowItem(cashflow_id=cf_too_late.cashflow_id, category_id=cat.category_id, amount=50.0, label="INVESTMENT"))

        await session.commit()

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
            res = await ac.get("/api/v1/discrepancies/")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == 1
            item = data["unlinked_items"][0]
            matches = item.get("candidate_matches", [])

            # The 91-day payment must NOT be included
            match_titles = [m["title"] for m in matches]
            assert "Payment After 90 Days" not in match_titles

            # There must be exactly 2 matches
            assert len(matches) == 2
            # Deterministic ordering by match_id ASC
            assert matches[0]["match_id"] == cf1.cashflow_id
            assert matches[0]["title"] == "Income Payment First"
            assert matches[1]["match_id"] == cf2.cashflow_id
            assert matches[1]["title"] == "Income Payment Second"
    finally:
        app.dependency_overrides.clear()


