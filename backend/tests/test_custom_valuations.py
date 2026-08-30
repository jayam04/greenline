import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, PriceHistory, User

@pytest.mark.anyio
async def test_custom_asset_valuations_crud():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="val_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        asset = Asset(symbol="STARTUP_EQ", name="Startup Equity", asset_type="stock", currency="USD")
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
            # 1. Add manual custom valuation point
            res_add = await ac.post("/api/v1/prices/", json={
                "asset_id": asset.asset_id,
                "price_date": "2026-08-10",
                "close_price": 120.0,
                "source": "manual"
            })
            assert res_add.status_code == 201
            price_id = res_add.json()["price_id"]
            assert res_add.json()["close_price"] == 120.0

            # 2. List custom valuations via GET /api/v1/prices/custom
            res_list = await ac.get("/api/v1/prices/custom")
            assert res_list.status_code == 200
            data = res_list.json()
            assert len(data) == 1
            assert data[0]["price_id"] == price_id
            assert data[0]["asset_symbol"] == "STARTUP_EQ"
            assert data[0]["close_price"] == 120.0
            assert data[0]["price_date"] == "2026-08-10"

            # 3. Delete manual custom valuation via DELETE /api/v1/prices/{price_id}
            res_del = await ac.delete(f"/api/v1/prices/{price_id}")
            assert res_del.status_code == 204

            # Verify list is now empty
            res_list2 = await ac.get("/api/v1/prices/custom")
            assert res_list2.status_code == 200
            assert len(res_list2.json()) == 0

    finally:
        app.dependency_overrides.clear()
