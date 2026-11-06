import os
import time
import asyncio
import pytest
from typing import AsyncGenerator, Tuple, Optional, Dict, Any
from unittest.mock import patch

import httpx
from httpx import AsyncClient, ASGITransport
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk

import sqlalchemy.ext.asyncio as sa_async
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.pool import NullPool
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from sqlalchemy import event, inspect

from app.main import app
from app.config import settings
from app.api.deps import get_db, get_current_user
from app.db.database import Base, get_tables_in_dependency_order
from app.db.models import User

# Enable test mode for Auth0
settings.AUTH0_TEST_MODE = True

# ==============================================================================
# MOCK RSA KEYPAIRS & JWKS FOR 100% OFFLINE AUTH0 TESTING
# ==============================================================================

TEST_KEY_ID = "greenline-test-auth0-kid-2026"
ATTACKER_KEY_ID = "untrusted-attacker-kid-9999"

# Generate trusted test RSA keypair (2048-bit)
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

# Generate untrusted attacker keypair (to simulate forgery / rogue key attacks)
_attacker_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ATTACKER_PRIVATE_PEM = _attacker_rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

_attacker_pub_pem = _attacker_rsa_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")

_attacker_jwk = jwk.RSAKey(algorithm="RS256", key=_attacker_pub_pem).to_dict()
_attacker_jwk["kid"] = ATTACKER_KEY_ID
ATTACKER_JWKS = {"keys": [_attacker_jwk]}


@pytest.fixture(autouse=True)
def mock_auth0_jwks():
    """
    Autouse fixture ensuring that ANY call to Auth0 JWKS endpoints resolves
    in-memory to TEST_JWKS with zero network traffic to external domains.
    """
    orig_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if ".well-known/jwks.json" in url_str:
            return httpx.Response(200, json=TEST_JWKS)
        return await orig_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        try:
            from app.services import auth0_service
            with patch.object(auth0_service, "get_jwks", return_value=TEST_JWKS), \
                 patch.object(auth0_service, "fetch_jwks", return_value=TEST_JWKS):
                if hasattr(auth0_service, "clear_jwks_cache"):
                    auth0_service.clear_jwks_cache()
                yield
        except (ImportError, AttributeError):
            yield


@pytest.fixture
def mint_auth0_token():
    """Helper fixture to mint RS256 JWT tokens with custom claims, headers, and expiry."""
    def _mint(
        sub: str = "auth0|test_user",
        email: Optional[str] = None,
        name: Optional[str] = None,
        picture: Optional[str] = None,
        exp: Optional[int] = None,
        iat: Optional[int] = None,
        nbf: Optional[int] = None,
        aud: Optional[str] = None,
        iss: Optional[str] = None,
        kid: Optional[str] = TEST_KEY_ID,
        alg: str = "RS256",
        key: Optional[str] = None,
        tampered: bool = False,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        now = int(time.time())
        domain = getattr(settings, "AUTH0_DOMAIN", "jayam04.eu.auth0.com") or "jayam04.eu.auth0.com"
        default_iss = getattr(settings, "AUTH0_ISSUER", f"https://{domain}/") or f"https://{domain}/"
        if not default_iss.endswith("/"):
            default_iss = f"{default_iss}/"

        payload: Dict[str, Any] = {
            "sub": sub,
            "aud": aud or getattr(settings, "AUTH0_AUDIENCE", "http://localhost:8000") or "http://localhost:8000",
            "iss": iss or default_iss,
            "exp": exp if exp is not None else (now + 3600),
            "iat": iat if iat is not None else now,
        }

        if email is not None:
            payload["email"] = email
        if name is not None:
            payload["name"] = name
        if picture is not None:
            payload["picture"] = picture
        if nbf is not None:
            payload["nbf"] = nbf
        if extra_claims:
            payload.update(extra_claims)

        headers = {}
        if kid is not None:
            headers["kid"] = kid

        signing_key = key or (TEST_PRIVATE_PEM if alg == "RS256" else "test-secret-key-1234567890123456")
        token_str = jwt.encode(payload, signing_key, algorithm=alg, headers=headers)

        if tampered:
            # Corrupt the signature by modifying the last characters
            parts = token_str.split(".")
            if len(parts) == 3:
                sig = parts[2]
                flipped_char = "X" if sig[-1:] != "X" else "Y"
                corrupted_sig = sig[:-1] + flipped_char
                token_str = f"{parts[0]}.{parts[1]}.{corrupted_sig}"

        return token_str

    return _mint


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1"
)

# Patch create_async_engine so all test-created engines use NullPool on the Oracle test database
_orig_create_async_engine = sa_async.create_async_engine

def _test_create_async_engine(url, *args, **kwargs):
    kwargs["poolclass"] = NullPool
    clean_url = str(url)
    if "sqlite" in clean_url:
        clean_url = TEST_DATABASE_URL
    return _orig_create_async_engine(clean_url, *args, **kwargs)

sa_async.create_async_engine = _test_create_async_engine

def get_test_engine() -> AsyncEngine:
    return _orig_create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

def get_test_sessionmaker(engine: AsyncEngine = None) -> async_sessionmaker:
    if engine is None:
        engine = get_test_engine()
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@event.listens_for(Session, "before_flush")
def handle_test_user_zero(session, flush_context, instances):
    for obj in list(session.new):
        if isinstance(obj, User) and getattr(obj, "user_id", 0) == 0:
            row = session.connection().execute(text("SELECT COUNT(*) FROM users WHERE user_id = 0")).scalar()
            if row > 0:
                session.connection().execute(
                    text("UPDATE users SET username = :u, password_hash = :p WHERE user_id = 0"),
                    {"u": obj.username, "p": obj.password_hash}
                )
                session.expunge(obj)
                state = inspect(obj)
                state.key = session.identity_key(User, (0,))
                session.identity_map.add(state)

def pytest_sessionstart(session):
    """Synchronously create schema once for the test session and ensure user 0 exists."""
    async def _init():
        engine = get_test_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            res = await conn.execute(text("SELECT COUNT(*) FROM users WHERE user_id = 0"))
            if res.scalar() == 0:
                await conn.execute(
                    text("INSERT INTO users (user_id, username, password_hash) VALUES (0, 'system', 'hash')")
                )
        await engine.dispose()
    asyncio.run(_init())

async def clean_database_tables(session: AsyncSession):
    """Delete rows from all tables in reverse dependency order, preserving user 0."""
    try:
        from app.db.models import Transaction, ExpectedDividend, Account
        from sqlalchemy import update
        await session.execute(update(Transaction).values(expected_dividend_id=None))
        await session.execute(update(ExpectedDividend).values(matched_transaction_id=None))
        await session.execute(update(Account).values(default_dividend_account_id=None))
    except Exception:
        pass

    tables = list(reversed(get_tables_in_dependency_order()))
    for table in tables:
        if table.name == "schema_migrations":
            continue
        elif table.name == "users":
            await session.execute(table.delete().where(table.c.user_id != 0))
        else:
            await session.execute(table.delete())
    # Ensure User 0 always exists and reset its credentials to system defaults
    res = await session.execute(select(User).where(User.user_id == 0))
    u0 = res.scalars().first()
    if not u0:
        await session.execute(text("INSERT INTO users (user_id, username, password_hash) VALUES (0, 'system', 'hash')"))
    else:
        u0.username = "system"
        u0.password_hash = "hash"
    await session.commit()

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Clean database tables before and after every test run outside the test event loop."""
    async def _clean():
        engine = get_test_engine()
        SessionMaker = get_test_sessionmaker(engine)
        async with SessionMaker() as session:
            await clean_database_tables(session)
        await engine.dispose()
    try:
        asyncio.run(_clean())
    except Exception as e:
        print(f"[conftest before clean error] {e}")
    yield
    try:
        asyncio.run(_clean())
    except Exception as e:
        print(f"[conftest after clean error] {e}")

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh database session."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)
    async with SessionMaker() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def test_db_session() -> AsyncGenerator[Tuple[AsyncSession, async_sessionmaker], None]:
    """Yields (session, sessionmaker) tuple."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)
    async with SessionMaker() as session:
        yield session, SessionMaker
    await engine.dispose()

@pytest.fixture
async def client(test_db_session) -> AsyncGenerator[Tuple[AsyncClient, AsyncSession, async_sessionmaker], None]:
    """Client fixture yielding (client, session, session_maker) with dependency overrides."""
    session, session_maker = test_db_session
    mock_user = User(user_id=0, username="system")

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session, session_maker

    app.dependency_overrides.clear()

@pytest.fixture
async def app_client(client) -> AsyncGenerator[AsyncClient, None]:
    """Convenience fixture yielding AsyncClient."""
    ac, _, _ = client
    yield ac


# ==============================================================================
# MULTI-USER AUTH0 TEST FIXTURES
# ==============================================================================

@pytest.fixture
async def auth0_client_unauthenticated(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client without Authorization header, verifying authentic unauthenticated behavior."""
    session, session_maker = test_db_session

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth0_client_user_a(test_db_session, mint_auth0_token) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client authenticated as User A (sub='auth0|user_a', email='user_a@example.com', name='User A')."""
    session, session_maker = test_db_session
    token_a = mint_auth0_token(
        sub="auth0|user_a",
        email="user_a@example.com",
        name="User A"
    )

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_a}"}
    ) as ac:
        ac.token = token_a
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth0_client_user_b(test_db_session, mint_auth0_token) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client authenticated as User B (sub='auth0|user_b', email='user_b@example.com', name='User B')."""
    session, session_maker = test_db_session
    token_b = mint_auth0_token(
        sub="auth0|user_b",
        email="user_b@example.com",
        name="User B"
    )

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_b}"}
    ) as ac:
        ac.token = token_b
        yield ac

    app.dependency_overrides.clear()
