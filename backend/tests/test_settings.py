import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base, User
from app.db.database import get_db
from app.main import app
from app.services.auth_service import get_password_hash

@pytest.fixture
async def settings_test_env():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    test_user = User(user_id=1, username="admin", password_hash=get_password_hash("password123"))

    async with TestSession() as session:
        session.add(test_user)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login to obtain auth token
        login_res = await client.post("/api/v1/auth/login", data={"username": "admin", "password": "password123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        yield client, auth_headers

    app.dependency_overrides.clear()
    await test_engine.dispose()

@pytest.mark.anyio
async def test_settings_app_font_defaults_and_updates(settings_test_env):
    client, headers = settings_test_env

    # 1. Initial GET should return default "general-sans"
    res = await client.get("/api/v1/settings", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "app_font" in data, "app_font should be returned in settings schema"
    assert data["app_font"] == "general-sans"

    # 2. Update to "inter"
    put_res = await client.put("/api/v1/settings", headers=headers, json={
        "link_brokerage_with_bank": False,
        "master_currency": "USD",
        "fiscal_year_start": "01-01",
        "app_font": "inter"
    })
    assert put_res.status_code == 200, put_res.text
    put_data = put_res.json()
    assert put_data["app_font"] == "inter"

    # 3. GET should now return "inter"
    get_res = await client.get("/api/v1/settings", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["app_font"] == "inter"

    # 4. Fallback for invalid font should be "general-sans"
    fallback_res = await client.put("/api/v1/settings", headers=headers, json={
        "link_brokerage_with_bank": False,
        "master_currency": "USD",
        "fiscal_year_start": "01-01",
        "app_font": "invalid-font"
    })
    assert fallback_res.status_code == 200
    assert fallback_res.json()["app_font"] == "general-sans"
