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
            assert data_after["unlinked_items"][0]["transaction_id"] == div1.transaction_id

            # 3. POST /api/v1/discrepancies/auto-link-defaults (auto-link div1)
            res_autolink = await ac.post("/api/v1/discrepancies/auto-link-defaults")
            assert res_autolink.status_code == 200
            assert res_autolink.json()["linked_count"] == 1

            # Verify all discrepancies resolved
            res_final = await ac.get("/api/v1/discrepancies/")
            assert res_final.json()["total_count"] == 0

    finally:
        app.dependency_overrides.clear()
