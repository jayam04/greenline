import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from unittest.mock import AsyncMock, patch
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, PriceHistory, User
from app.services.snapshot_engine import generate_daily_snapshot

@pytest.mark.anyio
@patch("app.api.routers.transactions.sync_dividends_for_asset", new_callable=AsyncMock)
async def test_price_history_cleanup_on_transaction_deletion(mock_sync_div):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="cleanup_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Bank Account", account_type="bank", currency="USD")
        demat_acc = Account(account_name="Demat Account", account_type="demat", currency="USD")
        session.add_all([bank_acc, demat_acc])
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(demat_acc)

        asset = Asset(symbol="UNLISTED_XX", name="XX Private Ltd", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

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
            # 1. Add valid buy transaction at $50 on 2026-08-01
            res1 = await ac.post("/api/v1/transactions/", json={
                "account_id": demat_acc.account_id,
                "funding_account_id": bank_acc.account_id,
                "asset_id": asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-08-01",
                "quantity": 10.0,
                "price_per_unit": 50.0,
                "total_amount": 500.0,
                "fees": 0.0,
                "taxes": 0.0,
                "notes": "Valid buy at 50"
            })
            assert res1.status_code == 201
            tx1_id = res1.json()["transaction_id"]

            # 2. Add erroneous buy transaction at $500 on 2026-08-15
            res2 = await ac.post("/api/v1/transactions/", json={
                "account_id": demat_acc.account_id,
                "funding_account_id": bank_acc.account_id,
                "asset_id": asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-08-15",
                "quantity": 5.0,
                "price_per_unit": 500.0,
                "total_amount": 2500.0,
                "fees": 0.0,
                "taxes": 0.0,
                "notes": "Mistake buy at 500"
            })
            assert res2.status_code == 201
            tx2_id = res2.json()["transaction_id"]

            # Verify PriceHistory contains both dates
            async with TestSession() as session:
                phs = (await session.execute(select(PriceHistory).where(PriceHistory.asset_id == asset.asset_id))).scalars().all()
                dates = {p.price_date: p.close_price for p in phs}
                assert datetime.date(2026, 8, 1) in dates
                assert datetime.date(2026, 8, 15) in dates
                assert dates[datetime.date(2026, 8, 15)] == 500.0

            # 3. Delete the erroneous transaction tx2
            del_res = await ac.delete(f"/api/v1/transactions/{tx2_id}")
            assert del_res.status_code == 204

            # Verify orphan PriceHistory on 2026-08-15 with source="transaction" was cleaned up
            async with TestSession() as session:
                phs_after = (await session.execute(select(PriceHistory).where(PriceHistory.asset_id == asset.asset_id))).scalars().all()
                dates_after = {p.price_date: p.close_price for p in phs_after}
                assert datetime.date(2026, 8, 1) in dates_after
                assert datetime.date(2026, 8, 15) not in dates_after

                # Generate daily snapshot for 2026-08-20 and verify asset valuation is 10 * 50 = $500 (not $500 per unit)
                snap = await generate_daily_snapshot(session, datetime.date(2026, 8, 20))
                # 10 shares remaining at $50 = $500
                assert snap.total_current_value == pytest.approx(500.0, 0.01)

    finally:
        app.dependency_overrides.clear()
