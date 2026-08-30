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
