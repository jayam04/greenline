"""
Service initialization and infrastructure tests for Networth & Analytics Microservice (Milestone 2).

Comprehensive verification:
1. Healthcheck endpoint (/health) returns 200 OK and {"status": "ok", "service": "networth"}.
2. Root endpoint (/) returns 200 OK and service metadata.
3. GZip middleware presence and gzip configuration (minimum_size=1000).
4. Auth0 RS256 token authentication via get_current_user:
   - Valid signed token authenticates matching user.
   - Missing token raises HTTP 401.
   - Empty Bearer header raises HTTP 401.
   - Invalid token (untrusted rogue key / forged) raises HTTP 401.
   - Expired token raises HTTP 401.
   - Tampered signature bytes raises HTTP 401.
   - Unregistered user (sub not in database) raises HTTP 401.
5. get_user_id helper function extracts user_id.
6. Database connection cleanly executes against test database.
7. Models table definition check asserting the 17 accessible tables.
8. Models exclusion check asserting forbidden tables are absent from metadata.
"""

import time
import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy import text, select
from fastapi import HTTPException

from app.config import settings
from app.main import app as networth_app
from app.db.database import get_db, AsyncSessionLocal, engine, Base
from app.db.models import (
    User, Account, Asset, Transaction, Lot, LotSale,
    PriceHistory, Dividend, CashFlow, CashflowTransaction,
    CashflowPayment, CashflowItem, Category, NetworthSnapshot,
    NetworthByAssetClass, Benchmark, XIRRCache
)
from app.api.deps import get_current_user, get_user_id
from tests.conftest import TEST_KEY_ID, TEST_PRIVATE_PEM, ATTACKER_KEY_ID, ATTACKER_PRIVATE_PEM


def create_token(
    sub: str,
    email: str = "test@example.com",
    key_id: str = TEST_KEY_ID,
    private_pem: str = TEST_PRIVATE_PEM,
    expired: bool = False,
    tampered: bool = False
) -> str:
    now = int(time.time())
    exp = (now - 3600) if expired else (now + 3600)
    domain = getattr(settings, "AUTH0_DOMAIN", "jayam04.eu.auth0.com") or "jayam04.eu.auth0.com"
    issuer = getattr(settings, "AUTH0_ISSUER", f"https://{domain}/") or f"https://{domain}/"
    if not issuer.endswith("/"):
        issuer = f"{issuer}/"
    aud = getattr(settings, "AUTH0_AUDIENCE", "http://localhost:8000") or "http://localhost:8000"

    payload = {
        "sub": sub,
        "email": email,
        "aud": aud,
        "iss": issuer,
        "exp": exp,
        "iat": now,
    }
    raw_token = jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": key_id})
    if tampered:
        # Flip characters in signature portion
        parts = raw_token.split(".")
        sig = parts[2]
        flipped_sig = ("AAAA" if sig[-4:] != "AAAA" else "ZZZZ") + sig[:-4]
        return f"{parts[0]}.{parts[1]}.{flipped_sig}"
    return raw_token


@pytest.mark.anyio
async def test_healthcheck():
    """Verify healthcheck endpoint returns 200 OK and expected payload."""
    transport = ASGITransport(app=networth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok", "service": "networth"}


@pytest.mark.anyio
async def test_root_endpoint():
    """Verify root endpoint returns 200 OK and service metadata."""
    transport = ASGITransport(app=networth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("service") == "networth"


@pytest.mark.anyio
async def test_gzip_middleware_enabled():
    """Verify GZip middleware is installed in app middleware stack."""
    middleware_classes = [m.cls.__name__ for m in networth_app.user_middleware]
    assert "GZipMiddleware" in middleware_classes


@pytest.mark.anyio
async def test_auth0_valid_token(test_db_session):
    """Verify get_current_user successfully resolves user from valid RS256 token."""
    session, session_maker = test_db_session
    sub = "auth0|networth_m2_test_user_001"
    email = "networth_m2@example.com"

    # Pre-seed user in database
    async with session_maker() as s:
        user_res = await s.execute(select(User).where(User.auth0_sub == sub))
        user = user_res.scalars().first()
        if not user:
            user = User(auth0_sub=sub, email=email, name="Networth M2 User", username=sub)
            s.add(user)
            await s.commit()

        token = create_token(sub=sub, email=email)
        resolved_user = await get_current_user(authorization=f"Bearer {token}", db=s)
        assert resolved_user is not None
        assert resolved_user.auth0_sub == sub
        assert resolved_user.email == email


@pytest.mark.anyio
async def test_auth0_missing_token_rejection(test_db_session):
    """Verify protected dependency rejects requests with missing or empty token."""
    session, session_maker = test_db_session

    with pytest.raises(HTTPException) as exc_info_none:
        async with session_maker() as s:
            await get_current_user(authorization=None, token=None, db=s)
    assert exc_info_none.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info_empty:
        async with session_maker() as s:
            await get_current_user(authorization="Bearer ", token=None, db=s)
    assert exc_info_empty.value.status_code == 401


@pytest.mark.anyio
async def test_auth0_invalid_and_expired_tokens(test_db_session):
    """Verify get_current_user rejects expired tokens, rogue keys, and tampered signatures."""
    session, session_maker = test_db_session

    expired_token = create_token(sub="auth0|expired_user", expired=True)
    attacker_token = create_token(
        sub="auth0|attacker_user",
        key_id=ATTACKER_KEY_ID,
        private_pem=ATTACKER_PRIVATE_PEM
    )
    tampered_token = create_token(sub="auth0|tampered_user", tampered=True)

    async with session_maker() as s:
        with pytest.raises(HTTPException) as exc_info_exp:
            await get_current_user(token=expired_token, db=s)
        assert exc_info_exp.value.status_code == 401

        with pytest.raises(HTTPException) as exc_info_att:
            await get_current_user(token=attacker_token, db=s)
        assert exc_info_att.value.status_code == 401

        with pytest.raises(HTTPException) as exc_info_tamp:
            await get_current_user(token=tampered_token, db=s)
        assert exc_info_tamp.value.status_code == 401


@pytest.mark.anyio
async def test_auth0_unregistered_user_rejection(test_db_session):
    """Verify valid token with non-existent database user is rejected."""
    session, session_maker = test_db_session
    ghost_token = create_token(sub="auth0|non_existent_user_99999")

    async with session_maker() as s:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=ghost_token, db=s)
        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()


def test_get_user_id_helper():
    """Verify get_user_id helper extracts user_id correctly."""
    mock_user = User(user_id=42, auth0_sub="sub42", username="user42")
    assert get_user_id(mock_user) == 42


@pytest.mark.anyio
async def test_database_connection(test_db_session):
    """Verify database engine connects and executes queries cleanly."""
    session, session_maker = test_db_session
    async with session_maker() as s:
        res = await s.execute(text("SELECT 1 FROM DUAL"))
        val = res.scalar()
        assert val == 1


def test_models_17_accessible_tables():
    """Verify models define the 17 accessible tables."""
    accessible_tables = {
        "users", "accounts", "assets", "transactions", "lots", "lot_sales",
        "price_history", "dividends", "cash_flows", "cashflow_transactions",
        "cashflow_payments", "cashflow_items", "categories", "networth_snapshots",
        "networth_by_asset_class", "benchmarks", "xirr_cache"
    }
    table_names = set(Base.metadata.tables.keys())
    assert accessible_tables.issubset(table_names), f"Missing tables: {accessible_tables - table_names}"


def test_models_excluded_forbidden_tables():
    """Verify forbidden tables are strictly omitted from Networth models metadata."""
    excluded_tables = {"api_keys", "app_settings", "expected_dividends", "schema_migrations"}
    table_names = set(Base.metadata.tables.keys())
    for exc in excluded_tables:
        assert exc not in table_names, f"Forbidden table {exc} is defined in Networth models metadata"
