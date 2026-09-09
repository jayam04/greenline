import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, User

@pytest.mark.anyio
async def test_discrepancies_endpoints():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="discrepancy_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="HDFC Bank Checking", account_type="bank", currency="USD")
        session.add(bank_acc)
        await session.commit()
        await session.refresh(bank_acc)

        demat_acc = Account(
            account_name="Zerodha Demat",
            account_type="demat",
            currency="USD",
            default_dividend_account_id=bank_acc.account_id
        )
        session.add(demat_acc)

        demat_acc2 = Account(
            account_name="Groww Demat",
            account_type="demat",
            currency="USD",
            default_dividend_account_id=None
        )
        session.add(demat_acc2)
        await session.commit()
        await session.refresh(demat_acc)
        await session.refresh(demat_acc2)

        asset = Asset(symbol="NVDA", name="NVIDIA Corp", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Unlinked dividend 1 (belongs to demat_acc with default bank)
        div1 = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=None,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 6, 15),
            quantity=100.0,
            price_per_unit=0.10,
            total_amount=10.0,
            taxes=0.0,
            source="yfinance_auto"
        )
        # Unlinked dividend 2 (belongs to demat_acc2 with NO default bank)
        div2 = Transaction(
            account_id=demat_acc2.account_id,
            funding_account_id=None,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 9, 15),
            quantity=50.0,
            price_per_unit=0.10,
            total_amount=5.0,
            taxes=0.0,
            source="yfinance_auto"
        )
        session.add_all([div1, div2])
        await session.commit()
        await session.refresh(div1)
        await session.refresh(div2)

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
            # 1. GET /api/v1/discrepancies/
            res = await ac.get("/api/v1/discrepancies/")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == 2
            assert data["total_unlinked_amount"] == 15.0
            assert data["auto_linkable_count"] == 1
            assert len(data["unlinked_items"]) == 2

            item1 = next(it for it in data["unlinked_items"] if it["transaction_id"] == div1.transaction_id)
            assert item1["suggested_funding_account_id"] == bank_acc.account_id
            assert item1["suggested_funding_account_name"] == "HDFC Bank Checking"

            # 2. POST /api/v1/discrepancies/resolve (resolve div2 with tax adjustment)
            res_resolve = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "transaction_id": div2.transaction_id,
                        "funding_account_id": bank_acc.account_id,
                        "taxes": 0.50,
                        "notes": "Linked with 10% TDS"
                    }
                ],
                "set_default_for_demat": {
                    "demat_account_id": demat_acc2.account_id,
                    "default_dividend_account_id": bank_acc.account_id
                }
            })
            assert res_resolve.status_code == 200

            # Verify remaining discrepancies is now 1
            res_after = await ac.get("/api/v1/discrepancies/")
            data_after = res_after.json()
            assert data_after["total_count"] == 1
            # 3. POST /api/v1/discrepancies/resolve (resolve div1 explicitly with credit date)
            res_resolve2 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "transaction_id": div1.transaction_id,
                        "funding_account_id": bank_acc.account_id,
                        "transaction_date": "2024-06-18"
                    }
                ]
            })
            assert res_resolve2.status_code == 200

            # Verify all discrepancies resolved
            res_final = await ac.get("/api/v1/discrepancies/")
            assert res_final.json()["total_count"] == 0

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_discrepancy_resolution_validation_and_invalid_state_transitions():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="valid_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Bank 1", account_type="bank", currency="USD")
        demat_acc = Account(account_name="Demat 1", account_type="demat", currency="USD")
        demat_acc2 = Account(account_name="Demat 2", account_type="demat", currency="USD")
        session.add_all([bank_acc, demat_acc, demat_acc2])
        await session.commit()
        for a in [bank_acc, demat_acc, demat_acc2]:
            await session.refresh(a)

        asset = Asset(symbol="MSFT", name="Microsoft", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        from app.db.models import ExpectedDividend
        exp = ExpectedDividend(
            asset_id=asset.asset_id,
            account_id=demat_acc.account_id,
            ex_date=datetime.date(2026, 6, 1),
            eligible_shares=10.0,
            dividend_rate=1.0,
            expected_amount=10.0,
            currency="USD",
            status="UNMATCHED"
        )
        session.add(exp)
        await session.commit()
        await session.refresh(exp)

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
            # 1. Non-existent funding account -> 400
            res = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp.expected_dividend_id,
                        "funding_account_id": 99999
                    }
                ]
            })
            assert res.status_code == 400
            assert "funding account" in res.json()["detail"].lower()

            # 2. Non-bank funding account (e.g. demat account) -> 400
            res2 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp.expected_dividend_id,
                        "funding_account_id": demat_acc2.account_id
                    }
                ]
            })
            assert res2.status_code == 400
            assert "bank account" in res2.json()["detail"].lower()

            # 3. Negative total amount -> 400
            res3 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp.expected_dividend_id,
                        "funding_account_id": bank_acc.account_id,
                        "total_amount": -10.0
                    }
                ]
            })
            assert res3.status_code == 400

            # 4. Negative taxes -> 400
            res4 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp.expected_dividend_id,
                        "funding_account_id": bank_acc.account_id,
                        "taxes": -5.0
                    }
                ]
            })
            assert res4.status_code == 400

            # 5. Taxes exceeding total amount -> 400
            res5 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": exp.expected_dividend_id,
                        "funding_account_id": bank_acc.account_id,
                        "total_amount": 10.0,
                        "taxes": 15.0
                    }
                ]
            })
            assert res5.status_code == 400

            # 6. Non-existent expected dividend ID -> 404
            res6 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "expected_dividend_id": 88888,
                        "funding_account_id": bank_acc.account_id
                    }
                ]
            })
            assert res6.status_code == 404

            # 7. Neither expected_dividend_id nor transaction_id -> 400
            res7 = await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "funding_account_id": bank_acc.account_id
                    }
                ]
            })
            assert res7.status_code == 400
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_account_default_dividend_deleted_and_invalid_handling():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="del_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Primary Bank", account_type="bank", currency="USD")
        demat_acc = Account(account_name="Primary Demat", account_type="demat", currency="USD")
        session.add_all([bank_acc, demat_acc])
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(demat_acc)

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
            # 1. Update demat to have bank as default dividend account
            res_up = await ac.put(f"/api/v1/accounts/{demat_acc.account_id}", json={
                "default_dividend_account_id": bank_acc.account_id
            })
            assert res_up.status_code == 200
            assert res_up.json()["default_dividend_account_id"] == bank_acc.account_id
            assert res_up.json()["default_dividend_account_name"] == "Primary Bank"

            # 2. Cannot set account to be its own default dividend account
            res_self = await ac.put(f"/api/v1/accounts/{demat_acc.account_id}", json={
                "default_dividend_account_id": demat_acc.account_id
            })
            assert res_self.status_code == 400

            # 3. Cannot set non-bank account as default dividend account
            demat2_res = await ac.post("/api/v1/accounts/", json={
                "account_name": "Second Demat",
                "account_type": "demat",
                "currency": "USD"
            })
            d2_id = demat2_res.json()["account_id"]
            res_nonbank = await ac.put(f"/api/v1/accounts/{demat_acc.account_id}", json={
                "default_dividend_account_id": d2_id
            })
            assert res_nonbank.status_code == 400

            # 4. Delete the bank account
            res_del = await ac.delete(f"/api/v1/accounts/{bank_acc.account_id}")
            assert res_del.status_code == 204

            # 5. Verify demat account gracefully shows null default dividend account without crash
            res_get = await ac.get(f"/api/v1/accounts/{demat_acc.account_id}")
            assert res_get.status_code == 200
            assert res_get.json()["default_dividend_account_name"] is None

            # 6. Verify list_accounts also handles gracefully
            res_list = await ac.get("/api/v1/accounts/")
            assert res_list.status_code == 200
            d_item = next(a for a in res_list.json() if a["account_id"] == demat_acc.account_id)
            assert d_item["default_dividend_account_name"] is None
    finally:
        app.dependency_overrides.clear()
