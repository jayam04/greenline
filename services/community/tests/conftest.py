"""
Test fixtures for Standalone Community Microservice.
Provides offline RS256 JWKS authentication mocking, dedicated Oracle GREENLINE_COMMUNITY
database sessions, and HTTP test clients.
"""

import os
import sys
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional
from unittest.mock import patch

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

COMMUNITY_ROOT = Path(__file__).resolve().parents[1]
if str(COMMUNITY_ROOT) in sys.path:
    sys.path.remove(str(COMMUNITY_ROOT))
sys.path.insert(0, str(COMMUNITY_ROOT))

# Evict foreign app modules from sys.modules
to_evict = [m for m in list(sys.modules.keys()) if m == "app" or m.startswith("app.")]
for m in to_evict:
    mod = sys.modules.get(m)
    if mod and hasattr(mod, "__file__") and mod.__file__ and str(COMMUNITY_ROOT) not in mod.__file__:
        del sys.modules[m]

# ==============================================================================
# 1. OFFLINE MOCK RSA KEYPAIR & JWKS GENERATOR (100% Offline Mandate)
# ==============================================================================

TEST_KEY_ID = "greenline-community-test-auth0-kid-2026"

_trusted_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PRIVATE_PEM = _trusted_rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

_trusted_pub_pem = _trusted_rsa_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")

_trusted_jwk = jwk.RSAKey(algorithm="RS256", key=_trusted_pub_pem).to_dict()
_trusted_jwk["kid"] = TEST_KEY_ID
TEST_JWKS = {"keys": [_trusted_jwk]}


@pytest.fixture
def mint_auth0_token():
    """Helper fixture to mint RS256 JWT tokens with custom claims, headers, and expiry."""
    def _mint(
        sub: str = "auth0|test_user",
        email: Optional[str] = None,
        name: Optional[str] = None,
        exp: Optional[int] = None,
        iat: Optional[int] = None,
        aud: Optional[str] = None,
        iss: Optional[str] = None,
        kid: Optional[str] = TEST_KEY_ID,
    ) -> str:
        now = int(time.time())
        default_iss = "https://jayam04.eu.auth0.com/"
        default_aud = "http://localhost:8000"

        payload: Dict[str, Any] = {
            "iss": iss or default_iss,
            "sub": sub,
            "aud": aud or default_aud,
            "iat": iat or now,
            "exp": exp or (now + 3600),
        }
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name

        headers = {"alg": "RS256", "typ": "JWT"}
        if kid:
            headers["kid"] = kid

        return jwt.encode(payload, TEST_PRIVATE_PEM, algorithm="RS256", headers=headers)

    return _mint


@pytest.fixture(autouse=True)
def mock_auth0_jwks():
    """Autouse fixture ensuring that calls to JWKS resolve in-memory to TEST_JWKS."""
    orig_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if ".well-known/jwks.json" in url_str:
            return httpx.Response(200, json=TEST_JWKS, request=httpx.Request("GET", url_str))
        return await orig_get(self, url, *args, **kwargs)

    patches = []
    try:
        from app.services import auth0_service
        patches.append(patch.object(auth0_service, "get_jwks", return_value=TEST_JWKS))
        patches.append(patch.object(auth0_service, "fetch_jwks", return_value=TEST_JWKS))
        if hasattr(auth0_service, "clear_jwks_cache"):
            auth0_service.clear_jwks_cache()
    except (ImportError, AttributeError):
        pass

    with patch.object(httpx.AsyncClient, "get", mock_get):
        for p in patches:
            p.start()
        try:
            yield
        finally:
            for p in reversed(patches):
                p.stop()


# ==============================================================================
# 2. DEDICATED ORACLE DATABASE FIXTURES (GREENLINE_COMMUNITY USER)
# ==============================================================================

COMMUNITY_USER = os.getenv("ORACLE_COMMUNITY_USER", "GREENLINE_COMMUNITY")
COMMUNITY_PASSWORD = os.getenv("COMMUNITY_DB_PASSWORD", "SecureCommunity2026#DbPass")
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")


def get_community_test_engine():
    """Create async engine using dedicated GREENLINE_COMMUNITY credentials."""
    db_url = os.getenv("DATABASE_URL_COMMUNITY")
    if db_url and ("?service_name=" in db_url or "@" not in db_url):
        return create_async_engine(db_url, echo=False, poolclass=NullPool)
    return create_async_engine(
        "oracle+oracledb://@",
        connect_args={
            "user": COMMUNITY_USER,
            "password": COMMUNITY_PASSWORD,
            "dsn": ORACLE_DSN,
        },
        echo=False,
        poolclass=NullPool,
    )


@pytest.fixture
async def community_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide clean database session using dedicated community connection."""
    engine = get_community_test_engine()
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    async with session_factory() as session:
        # Clean community tables prior to test
        try:
            await session.execute(text("DELETE FROM community_comments"))
            await session.execute(text("DELETE FROM community_posts"))
            await session.execute(text("DELETE FROM community_users"))
            await session.commit()
        except Exception:
            await session.rollback()

        yield session

        # Clean community tables after test
        try:
            await session.execute(text("DELETE FROM community_comments"))
            await session.execute(text("DELETE FROM community_posts"))
            await session.execute(text("DELETE FROM community_users"))
            await session.commit()
        except Exception:
            await session.rollback()

    await engine.dispose()


@pytest.fixture
async def community_client(community_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated HTTP client for Community microservice."""
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_community_client(community_db_session: AsyncSession, mint_auth0_token) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated HTTP client for Community microservice (User A)."""
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token = mint_auth0_token(sub="auth0|community_user_a", name="User A")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        yield client

    app.dependency_overrides.clear()
