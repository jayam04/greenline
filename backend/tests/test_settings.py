import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base, User
from app.db.database import get_db
from app.main import app
from app.services.auth_service import get_password_hash

@pytest.fixture
async def settings_test_env():
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
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

    # 4. Update to "spline-sans" (Google Fonts Spline/Spine Sans)
    spline_res = await client.put("/api/v1/settings", headers=headers, json={
        "link_brokerage_with_bank": False,
        "master_currency": "USD",
        "fiscal_year_start": "01-01",
        "app_font": "spline-sans"
    })
    assert spline_res.status_code == 200, spline_res.text
    assert spline_res.json()["app_font"] == "spline-sans"

    get_spline_res = await client.get("/api/v1/settings", headers=headers)
    assert get_spline_res.status_code == 200
    assert get_spline_res.json()["app_font"] == "spline-sans"

    # 5. Update to "spine-sans" alias
    spine_res = await client.put("/api/v1/settings", headers=headers, json={
        "link_brokerage_with_bank": False,
        "master_currency": "USD",
        "fiscal_year_start": "01-01",
        "app_font": "spine-sans"
    })
    assert spine_res.status_code == 200, spine_res.text
    assert spine_res.json()["app_font"] == "spine-sans"

    # 6. Fallback for invalid font should be "general-sans"
    fallback_res = await client.put("/api/v1/settings", headers=headers, json={
        "link_brokerage_with_bank": False,
        "master_currency": "USD",
        "fiscal_year_start": "01-01",
        "app_font": "invalid-font"
    })
    assert fallback_res.status_code == 200
    assert fallback_res.json()["app_font"] == "general-sans"


@pytest.mark.anyio
async def test_settings_community_pseudonym_lifecycle(settings_test_env):
    client, headers = settings_test_env

    # 1. Initial GET returns default None
    get_res = await client.get("/api/v1/settings", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert "community_pseudonym" in data
    assert data["community_pseudonym"] is None

    # 2. Update pseudonym to "Giant Elephant"
    put_res = await client.put("/api/v1/settings", headers=headers, json={
        "community_pseudonym": "Giant Elephant"
    })
    assert put_res.status_code == 200
    assert put_res.json()["community_pseudonym"] == "Giant Elephant"

    # 3. GET confirms persistence in database
    get_res2 = await client.get("/api/v1/settings", headers=headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["community_pseudonym"] == "Giant Elephant"

    # 4. Updating another field (e.g. app_font) omitting community_pseudonym preserves it
    put_font_res = await client.put("/api/v1/settings", headers=headers, json={
        "app_font": "rx100"
    })
    assert put_font_res.status_code == 200
    assert put_font_res.json()["app_font"] == "rx100"
    assert put_font_res.json()["community_pseudonym"] == "Giant Elephant"

    get_res3 = await client.get("/api/v1/settings", headers=headers)
    assert get_res3.json()["community_pseudonym"] == "Giant Elephant"

    # 5. Whitespace is stripped
    put_trim_res = await client.put("/api/v1/settings", headers=headers, json={
        "community_pseudonym": "   Crazy Dog   "
    })
    assert put_trim_res.status_code == 200
    assert put_trim_res.json()["community_pseudonym"] == "Crazy Dog"

    # 6. Explicitly clearing with empty string resets to None
    put_clear_res = await client.put("/api/v1/settings", headers=headers, json={
        "community_pseudonym": ""
    })
    assert put_clear_res.status_code == 200
    assert put_clear_res.json()["community_pseudonym"] is None

    get_res4 = await client.get("/api/v1/settings", headers=headers)
    assert get_res4.json()["community_pseudonym"] is None

    # 7. Explicitly setting and clearing with None
    await client.put("/api/v1/settings", headers=headers, json={"community_pseudonym": "Golden Falcon"})
    put_none_res = await client.put("/api/v1/settings", headers=headers, json={"community_pseudonym": None})
    assert put_none_res.status_code == 200
    assert put_none_res.json()["community_pseudonym"] is None

    get_res5 = await client.get("/api/v1/settings", headers=headers)
    assert get_res5.json()["community_pseudonym"] is None


@pytest.fixture
async def multi_user_settings_env():
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    u1 = User(user_id=1, username="admin1", password_hash=get_password_hash("password123"))
    u2 = User(user_id=2, username="admin2", password_hash=get_password_hash("password123"))

    async with TestSession() as session:
        session.add(u1)
        session.add(u2)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res1 = await client.post("/api/v1/auth/login", data={"username": "admin1", "password": "password123"})
        res2 = await client.post("/api/v1/auth/login", data={"username": "admin2", "password": "password123"})
        h1 = {"Authorization": f"Bearer {res1.json()['access_token']}"}
        h2 = {"Authorization": f"Bearer {res2.json()['access_token']}"}
        yield client, h1, h2

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.anyio
async def test_settings_community_pseudonym_multi_user_isolation(multi_user_settings_env):
    client, h1, h2 = multi_user_settings_env

    # User 1 sets "Giant Elephant"
    await client.put("/api/v1/settings", headers=h1, json={"community_pseudonym": "Giant Elephant"})
    # User 2 sets "Crazy Dog"
    await client.put("/api/v1/settings", headers=h2, json={"community_pseudonym": "Crazy Dog"})

    # Check User 1
    r1 = await client.get("/api/v1/settings", headers=h1)
    assert r1.json()["community_pseudonym"] == "Giant Elephant"

    # Check User 2
    r2 = await client.get("/api/v1/settings", headers=h2)
    assert r2.json()["community_pseudonym"] == "Crazy Dog"

