import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import Base, User, ApiKey
from app.db.database import get_db
from app.main import app
from app.config import settings
from app.services.auth_service import get_password_hash
from app.api.deps import hash_api_key

# Helper to generate RSA key pair and JWKS
def create_rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pem_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    jwk_dict = jwk.RSAKey(algorithm="RS256", key=pem_public.decode("utf-8")).to_dict()
    jwk_dict["kid"] = "test-key-id"
    jwk_dict["use"] = "sig"
    return pem_private, jwk_dict

TEST_PRIVATE_KEY, TEST_JWK = create_rsa_keypair()
TEST_JWKS = {"keys": [TEST_JWK]}
AUTH0_DOMAIN = "test-auth0.us.auth0.com"
AUTH0_AUDIENCE = "https://api.greenline.local"
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

def generate_auth0_token(payload_overrides=None, kid="test-key-id"):
    payload = {
        "sub": "auth0|654321",
        "email": "investor@example.com",
        "aud": AUTH0_AUDIENCE,
        "iss": AUTH0_ISSUER,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow(),
    }
    if payload_overrides:
        payload.update(payload_overrides)
    return jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256", headers={"kid": kid})

@pytest.fixture(autouse=True)
def configure_auth0_settings():
    orig_domain = settings.AUTH0_DOMAIN
    orig_audience = settings.AUTH0_AUDIENCE
    orig_issuer = settings.AUTH0_ISSUER

    settings.AUTH0_DOMAIN = AUTH0_DOMAIN
    settings.AUTH0_AUDIENCE = AUTH0_AUDIENCE
    settings.AUTH0_ISSUER = AUTH0_ISSUER

    yield

    settings.AUTH0_DOMAIN = orig_domain
    settings.AUTH0_AUDIENCE = orig_audience
    settings.AUTH0_ISSUER = orig_issuer

@pytest.fixture
async def auth0_test_env():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed User
    test_user = User(user_id=1, username="admin", password_hash=get_password_hash("admin123"))
    test_api_key = ApiKey(
        key_id=1,
        user_id=1,
        name="Test Key",
        key_hash=hash_api_key("gl_test_api_key_123"),
        key_prefix="gl_test",
        is_active=True,
    )

    async with TestSession() as session:
        session.add_all([test_user, test_api_key])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, TestSession, test_user

    app.dependency_overrides.clear()
    await test_engine.dispose()

@pytest.mark.anyio
async def test_auth0_service_verify_token_valid():
    from app.services.auth0_service import verify_auth0_token, clear_jwks_cache

    clear_jwks_cache()
    token = generate_auth0_token()

    with patch("app.services.auth0_service.fetch_jwks", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = TEST_JWKS
        payload = await verify_auth0_token(token)

        assert payload is not None
        assert payload["sub"] == "auth0|654321"
        assert payload["email"] == "investor@example.com"
        assert payload["aud"] == AUTH0_AUDIENCE
        assert payload["iss"] == AUTH0_ISSUER

@pytest.mark.anyio
async def test_auth0_service_rejects_invalid_token():
    from app.services.auth0_service import verify_auth0_token, clear_jwks_cache

    clear_jwks_cache()

    with patch("app.services.auth0_service.fetch_jwks", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = TEST_JWKS

        # 1. Expired token
        expired_token = generate_auth0_token({
            "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        })
        assert await verify_auth0_token(expired_token) is None

        # 2. Wrong audience
        wrong_aud_token = generate_auth0_token({
            "aud": "https://wrong-audience.com"
        })
        assert await verify_auth0_token(wrong_aud_token) is None

        # 3. Wrong issuer
        wrong_iss_token = generate_auth0_token({
            "iss": "https://attacker.auth0.com/"
        })
        assert await verify_auth0_token(wrong_iss_token) is None

        # 4. Unknown key id
        unknown_kid_token = generate_auth0_token(kid="unknown-kid")
        assert await verify_auth0_token(unknown_kid_token) is None

@pytest.mark.anyio
async def test_endpoint_auth_with_auth0_token(auth0_test_env):
    client, session_factory, user = auth0_test_env
    token = generate_auth0_token()

    with patch("app.services.auth0_service.fetch_jwks", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = TEST_JWKS

        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["username"] == "admin"
        assert data["user_id"] == 1

@pytest.mark.anyio
async def test_endpoint_auth_coexistence_with_api_key_and_local_jwt(auth0_test_env):
    client, session_factory, user = auth0_test_env

    # 1. API Key Auth
    api_key_res = await client.get("/api/v1/auth/me", headers={"X-API-Key": "gl_test_api_key_123"})
    assert api_key_res.status_code == 200
    assert api_key_res.json()["user_id"] == 1

    # 2. Local JWT Login & Auth
    login_res = await client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200
    local_jwt = login_res.json()["access_token"]

    local_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {local_jwt}"})
    assert local_res.status_code == 200
    assert local_res.json()["user_id"] == 1

@pytest.mark.anyio
async def test_auth0_auto_creates_user_if_table_empty():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = generate_auth0_token()
        with patch("app.services.auth0_service.fetch_jwks", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = TEST_JWKS
            res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["username"] == settings.DEFAULT_ADMIN_USER

    app.dependency_overrides.clear()
    await test_engine.dispose()
