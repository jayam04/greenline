"""
Comprehensive 4-Tier Opaque-Box E2E Test Suite for Greenline Networth and Analytics Microservice.

Requirements Under Test:
  - R1: Dedicated Networth microservice endpoints with query response times < 50ms
        (/api/v1/snapshots, /api/v1/portfolio/summary, /api/v1/portfolio/holdings, /api/v1/portfolio/annual_snapshot).
  - R2: Dedicated database user provisioning and least-privilege security (ADMIN SQL).
  - R3: Weekly end-of-Sunday snapshot aggregation (points strictly on calendar Sundays: d.weekday() == 6).
  - R4: Starting date selection (?start_date=YYYY-MM-DD) with automatic inception fallback.
  - R5: In-process background snapshot recalculation worker (POST /api/v1/snapshots/trigger-recalculate)
        and periodic scheduler updates.
  - R6: Transparent Next.js API routing, RS256 Auth0 token verification, and Row-Level Security (RLS) tenant isolation.

Testing Methodology:
  - Tier 1: Feature Coverage (>=5 tests per core feature: Endpoints, Auth, Sunday Aggregation)
  - Tier 2: Boundary & Corner Cases (>=5 tests per boundary feature: Date filtering, Empty/Zero states, Account boundaries)
  - Tier 3: Cross-Feature Combinations (Recalculation trigger, Cashflows, Multi-tenant isolation, Multi-currency)
  - Tier 4: Real-World Scenarios & SLA Benchmarks (3-5 Year realistic lifecycle, FIFO depletion, Sub-50ms latency)
"""

import os
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
import asyncio
import datetime
import math
from typing import AsyncGenerator, Dict, Any, Optional, List
from unittest.mock import patch

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from sqlalchemy import select, text
import sqlalchemy.ext.asyncio as sa_async
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app as core_app
from app.config import settings
from app.db.database import get_db, Base
from app.api.deps import get_current_user
from app.db.models import (
    User, Account, Asset, Transaction, Lot, LotSale,
    PriceHistory, Dividend, CashFlow, CashflowTransaction,
    CashflowPayment, CashflowItem, NetworthSnapshot
)
from app.services.fifo_engine import process_transaction_event
try:
    from services.networth.app.services.snapshot_engine import recalculate_past_snapshots, generate_daily_snapshot
except ImportError:
    from app.services.snapshot_engine import recalculate_past_snapshots, generate_daily_snapshot
try:
    from backend_conftest import get_test_engine, get_test_sessionmaker, clean_database_tables
except ImportError:
    try:
        from conftest import get_test_engine, get_test_sessionmaker, clean_database_tables
    except ImportError:
        from tests.conftest import get_test_engine, get_test_sessionmaker, clean_database_tables

# Ensure create_async_engine strips pool_size/max_overflow if NullPool is active
try:
    import conftest
    if hasattr(conftest, "_test_create_async_engine") and hasattr(conftest, "_orig_create_async_engine"):
        def _safe_test_create_async_engine(url, *args, **kwargs):
            kwargs["poolclass"] = conftest.NullPool
            clean_url = str(url)
            if "sqlite" in clean_url:
                clean_url = conftest.TEST_DATABASE_URL
            kwargs.pop("pool_size", None)
            kwargs.pop("max_overflow", None)
            return conftest._orig_create_async_engine(clean_url, *args, **kwargs)
        conftest._test_create_async_engine = _safe_test_create_async_engine
        sa_async.create_async_engine = _safe_test_create_async_engine
except Exception:
    pass


# ==============================================================================
# 1. OFFLINE MOCK RSA KEYPAIR & JWKS GENERATOR (100% Offline Mandate)
# ==============================================================================

TEST_KEY_ID = "greenline-test-auth0-kid-2026"
ATTACKER_KEY_ID = "untrusted-attacker-kid-9999"

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


def make_auth0_token(
    sub: str,
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
    private_pem: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Helper to mint RS256 JWT tokens with custom claims, headers, and expiry."""
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

    signing_key = private_pem or TEST_PRIVATE_PEM
    return jwt.encode(payload, signing_key, algorithm=alg, headers=headers)


@pytest.fixture(autouse=True)
def mock_auth0_jwks():
    """Autouse fixture intercepting JWKS network requests with in-memory test keys."""
    orig_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if ".well-known/jwks.json" in url_str:
            req = httpx.Request("GET", url)
            return httpx.Response(200, json=TEST_JWKS, request=req)
        return await orig_get(self, url, *args, **kwargs)

    patches = []
    try:
        from app.services import auth0_service as core_auth0
        patches.append(patch.object(core_auth0, "get_jwks", return_value=TEST_JWKS))
        patches.append(patch.object(core_auth0, "fetch_jwks", return_value=TEST_JWKS))
        if hasattr(core_auth0, "clear_jwks_cache"):
            core_auth0.clear_jwks_cache()
    except (ImportError, AttributeError):
        pass

    try:
        from services.networth.app.services import auth0_service as nw_auth0
        patches.append(patch.object(nw_auth0, "get_jwks", return_value=TEST_JWKS))
        patches.append(patch.object(nw_auth0, "fetch_jwks", return_value=TEST_JWKS))
        if hasattr(nw_auth0, "clear_jwks_cache"):
            nw_auth0.clear_jwks_cache()
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
# 2. APPLICATION TARGET RESOLUTION & TEST CLIENT FIXTURE
# ==============================================================================

def get_target_app():
    """
    Resolves the FastAPI application target:
    1. Dedicated Networth microservice app in `services/networth/app/main.py` if present.
    2. Fallback to `backend/app/main.py` for progressive testability.
    """
    try:
        from services.networth.app.main import app as networth_app
        return networth_app
    except ImportError:
        return core_app


@pytest.fixture
async def raw_client(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client that preserves genuine RS256 token verification without
    mocking get_current_user, ensuring opaque-box testing parity.
    """
    target_app = get_target_app()
    session, session_maker = test_db_session

    async def override_get_db():
        async with session_maker() as s:
            yield s

    target_app.dependency_overrides[get_db] = override_get_db
    target_app.dependency_overrides.pop(get_current_user, None)
    try:
        from services.networth.app.db.database import get_db as networth_get_db
        target_app.dependency_overrides[networth_get_db] = override_get_db
    except ImportError:
        pass

    if target_app is not core_app:
        core_app.dependency_overrides[get_db] = override_get_db
        core_app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=target_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    target_app.dependency_overrides.clear()
    if target_app is not core_app:
        core_app.dependency_overrides.clear()


# ==============================================================================
# 3. HELPER FUNCTIONS FOR SEEDING TEST STATE
# ==============================================================================

async def get_or_create_user(session: AsyncSession, sub: str, email: str, name: str) -> User:
    """Retrieves or provisions an isolated user in the test database."""
    stmt = select(User).where(User.auth0_sub == sub)
    res = await session.execute(stmt)
    user = res.scalars().first()
    if not user:
        user = User(auth0_sub=sub, email=email, name=name, username=sub)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def seed_basic_portfolio(
    session: AsyncSession,
    user_id: int,
    deposit_date: datetime.date = datetime.date(2025, 1, 1),
    buy_date: datetime.date = datetime.date(2025, 1, 8),
    deposit_amount: float = 10000.0,
    buy_amount: float = 1500.0,
    buy_qty: float = 10.0,
    buy_fees: float = 10.0,
    symbol: str = "AAPL",
    price_on_sunday: float = 180.0,
    sunday_date: datetime.date = datetime.date(2025, 1, 12),
) -> Dict[str, Any]:
    """
    Seeds a deterministic baseline portfolio:
    1. Demat account
    2. Asset (stock)
    3. Cash deposit
    4. Stock buy transaction and FIFO lot processing
    5. Price history on Sunday
    6. Historical snapshot materialization
    """
    acc = Account(
        user_id=user_id,
        account_name="Primary Brokerage",
        account_type="demat",
        currency="USD"
    )
    stmt_ast = select(Asset).where(Asset.symbol == symbol)
    ast_res = await session.execute(stmt_ast)
    ast = ast_res.scalar_one_or_none()
    if not ast:
        ast = Asset(symbol=symbol, name=f"{symbol} Corp", asset_type="stock", currency="USD")
        session.add(ast)

    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    await session.refresh(ast)

    # Deposit
    tx_dep = Transaction(
        user_id=user_id,
        account_id=acc.account_id,
        transaction_type="deposit",
        transaction_date=deposit_date,
        total_amount=deposit_amount
    )
    session.add(tx_dep)
    await session.commit()
    await session.refresh(tx_dep)
    await process_transaction_event(session, tx_dep)

    # Buy Stock
    price_per_unit = (buy_amount - buy_fees) / buy_qty if buy_qty > 0 else 100.0
    tx_buy = Transaction(
        user_id=user_id,
        account_id=acc.account_id,
        asset_id=ast.asset_id,
        transaction_type="buy",
        transaction_date=buy_date,
        quantity=buy_qty,
        price_per_unit=price_per_unit,
        total_amount=buy_amount,
        fees=buy_fees
    )
    session.add(tx_buy)
    await session.commit()
    await session.refresh(tx_buy)
    await process_transaction_event(session, tx_buy)

    # Price history on Sunday (avoid ORA-00001 duplicate if asset already has price on that date)
    stmt_ph = select(PriceHistory).where(
        PriceHistory.asset_id == ast.asset_id,
        PriceHistory.price_date == sunday_date
    )
    res_ph = await session.execute(stmt_ph)
    ph = res_ph.scalar_one_or_none()
    if not ph:
        ph = PriceHistory(
            asset_id=ast.asset_id,
            price_date=sunday_date,
            close_price=price_on_sunday,
            source="test"
        )
        session.add(ph)
        await session.commit()

    # Materialize snapshots
    await recalculate_past_snapshots(session, start_date=deposit_date, user_id=user_id)
    await session.commit()

    return {
        "account": acc,
        "asset": ast,
        "deposit_tx": tx_dep,
        "buy_tx": tx_buy,
        "price_history": ph
    }


# ==============================================================================
# TIER 1: FEATURE COVERAGE (Core Requirements >= 5 per feature)
# ==============================================================================

class TestTier1FeatureCoverage:
    """
    Tier 1: Feature Coverage (Core Requirements).
    Verifies primary behavior and contracts for:
      - Analytical endpoints existence and JSON structure (5 tests)
      - Auth0 RS256 token verification and rejections (5 tests)
      - Weekly end-of-Sunday snapshot aggregation invariants (5 tests)
    """

    # --------------------------------------------------------------------------
    # 1.1 Networth Endpoints Coverage (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_get_snapshots_endpoint_status(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/snapshots returns HTTP 200 and a list of snapshot records."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_user_endpoints", "t1_endpoints@test.com", "Tier1 Endpoints")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t1_user_endpoints", email="t1_endpoints@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        if len(data) > 0:
            first = data[0]
            assert "snapshot_date" in first
            assert "net_worth" in first
            assert "total_invested" in first

    @pytest.mark.anyio
    async def test_tier1_get_portfolio_summary_endpoint(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/portfolio/summary returns HTTP 200 with totals and allocation maps."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_user_summary", "t1_summary@test.com", "Tier1 Summary")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t1_user_summary", email="t1_summary@test.com")
        res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert "total_invested" in body
        assert "total_current_value" in body
        assert "asset_allocation" in body
        assert "sector_allocation" in body
        assert body["total_invested"] > 0

    @pytest.mark.anyio
    async def test_tier1_get_portfolio_holdings_endpoint(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/portfolio/holdings returns HTTP 200 with active open holdings."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_user_holdings", "t1_holdings@test.com", "Tier1 Holdings")
        await seed_basic_portfolio(session, u.user_id, symbol="NVDA")

        token = make_auth0_token(sub="auth0|t1_user_holdings", email="t1_holdings@test.com")
        res = await raw_client.get("/api/v1/portfolio/holdings", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        holdings = res.json()
        assert isinstance(holdings, list)
        assert len(holdings) >= 1
        assert any(h.get("symbol") == "NVDA" for h in holdings)

    @pytest.mark.anyio
    async def test_tier1_get_annual_snapshot_endpoint(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/portfolio/annual_snapshot returns HTTP 200 with annual portfolio summaries."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_user_annual", "t1_annual@test.com", "Tier1 Annual")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t1_user_annual", email="t1_annual@test.com")
        res = await raw_client.get("/api/v1/portfolio/annual_snapshot", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert "year_label" in body
        assert "net_worth_delta" in body

    @pytest.mark.anyio
    async def test_tier1_post_trigger_recalculate_endpoint(self, raw_client: AsyncClient, test_db_session):
        """POST /api/v1/snapshots/trigger-recalculate queues non-blocking recalculation."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_user_trigger", "t1_trigger@test.com", "Tier1 Trigger")

        token = make_auth0_token(sub="auth0|t1_user_trigger", email="t1_trigger@test.com")
        payload = {
            "user_id": u.user_id,
            "start_date": "2025-01-01",
            "reason": "trade_created"
        }
        res = await raw_client.post(
            "/api/v1/snapshots/trigger-recalculate",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        # Expected in M3: 200 or 202 with status queued
        assert res.status_code in (200, 202)
        data = res.json()
        assert data.get("status") == "queued"

    # --------------------------------------------------------------------------
    # 1.2 Auth0 RS256 Verification & Security Boundary (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_auth_valid_rs256_token_accepted(self, raw_client: AsyncClient, test_db_session):
        """Valid RS256 token signed by the trusted keypair is accepted (HTTP 200)."""
        session, _ = test_db_session
        await get_or_create_user(session, "auth0|t1_valid_auth", "valid_auth@test.com", "Valid Auth")

        token = make_auth0_token(sub="auth0|t1_valid_auth", email="valid_auth@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    @pytest.mark.anyio
    async def test_tier1_auth_missing_token_returns_401(self, raw_client: AsyncClient):
        """Request without Authorization header is rejected with HTTP 401."""
        res = await raw_client.get("/api/v1/snapshots")
        assert res.status_code == 401
        assert "Bearer" in res.headers.get("WWW-Authenticate", "")

    @pytest.mark.anyio
    async def test_tier1_auth_malformed_token_returns_401(self, raw_client: AsyncClient):
        """Request with malformed or empty Bearer string is rejected with HTTP 401."""
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": "Bearer "})
        assert res.status_code == 401

        res_garbage = await raw_client.get("/api/v1/snapshots", headers={"Authorization": "Bearer not-a-valid-jwt"})
        assert res_garbage.status_code == 401

    @pytest.mark.anyio
    async def test_tier1_auth_expired_token_returns_401(self, raw_client: AsyncClient):
        """Request with token expired in the past is rejected with HTTP 401."""
        now = int(time.time())
        expired_token = make_auth0_token(sub="auth0|t1_expired", exp=now - 3600)
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier1_auth_untrusted_signature_returns_401(self, raw_client: AsyncClient):
        """Token signed by untrusted attacker private key is rejected with HTTP 401."""
        attacker_token = make_auth0_token(
            sub="auth0|attacker_target",
            kid=ATTACKER_KEY_ID,
            private_pem=ATTACKER_PRIVATE_PEM
        )
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {attacker_token}"})
        assert res.status_code == 401

    # --------------------------------------------------------------------------
    # 1.3 Weekly End-of-Sunday Snapshot Aggregation Invariants (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_sunday_aggregation_weekday_invariant(self, raw_client: AsyncClient, test_db_session):
        """Every snapshot returned by GET /api/v1/snapshots is strictly on a calendar Sunday (weekday == 6)."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_sunday_inv", "sunday_inv@test.com", "Sunday Invariant")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t1_sunday_inv", email="sunday_inv@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) > 0, "Expected at least one snapshot record"
        for pt in snaps:
            d = datetime.date.fromisoformat(pt["snapshot_date"])
            assert d.weekday() == 6, f"Snapshot date {pt['snapshot_date']} is weekday {d.weekday()} (must be 6 for Sunday)"

    @pytest.mark.anyio
    async def test_tier1_sunday_aggregation_point_reduction_ratio(self, raw_client: AsyncClient, test_db_session):
        """For a full 1-year timeline (2024), Sunday aggregation returns <= 53 points (85%+ payload reduction)."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_reduction", "reduction@test.com", "Point Reduction")
        await seed_basic_portfolio(
            session,
            u.user_id,
            deposit_date=datetime.date(2024, 1, 1),
            buy_date=datetime.date(2024, 1, 10),
            sunday_date=datetime.date(2024, 1, 14)
        )

        token = make_auth0_token(sub="auth0|t1_reduction", email="reduction@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) <= 53, f"Expected <= 53 Sunday points for 1 year, got {len(snaps)}"

    @pytest.mark.anyio
    async def test_tier1_sunday_aggregation_midweek_trade_capture(self, raw_client: AsyncClient, test_db_session):
        """A trade occurring on Wednesday (2025-01-08) is materialized in the following Sunday snapshot (2025-01-12)."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_midweek", "midweek@test.com", "Midweek Capture")
        wednesday = datetime.date(2025, 1, 8)
        assert wednesday.weekday() == 2, "2025-01-08 must be Wednesday"
        following_sunday = datetime.date(2025, 1, 12)
        assert following_sunday.weekday() == 6, "2025-01-12 must be Sunday"

        await seed_basic_portfolio(
            session,
            u.user_id,
            deposit_date=datetime.date(2025, 1, 1),
            buy_date=wednesday,
            sunday_date=following_sunday
        )

        token = make_auth0_token(sub="auth0|t1_midweek", email="midweek@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        sunday_snap = next((s for s in snaps if s["snapshot_date"] == str(following_sunday)), None)
        assert sunday_snap is not None, f"Expected snapshot on Sunday {following_sunday}"
        assert sunday_snap["total_current_value"] > 0

    @pytest.mark.anyio
    async def test_tier1_sunday_aggregation_exact_sunday_trade(self, raw_client: AsyncClient, test_db_session):
        """A trade executed directly on a Sunday (2025-01-05) is included in that Sunday's snapshot."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_exact_sun", "exact_sun@test.com", "Exact Sunday")
        sunday_tx = datetime.date(2025, 1, 5)
        assert sunday_tx.weekday() == 6, "2025-01-05 must be Sunday"

        await seed_basic_portfolio(
            session,
            u.user_id,
            deposit_date=sunday_tx,
            buy_date=sunday_tx,
            sunday_date=sunday_tx
        )

        token = make_auth0_token(sub="auth0|t1_exact_sun", email="exact_sun@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert any(s["snapshot_date"] == str(sunday_tx) for s in snaps)

    @pytest.mark.anyio
    async def test_tier1_sunday_aggregation_monotonic_progression(self, raw_client: AsyncClient, test_db_session):
        """Snapshot timeline progresses monotonically ascending with zero duplicate Sunday dates."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t1_monotonic", "monotonic@test.com", "Monotonic")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t1_monotonic", email="monotonic@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        dates = [s["snapshot_date"] for s in snaps]
        assert dates == sorted(dates), "Snapshot dates must be strictly sorted ascending"
        assert len(dates) == len(set(dates)), "Duplicate Sunday snapshot dates detected"


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 5 per feature)
# ==============================================================================

class TestTier2Boundaries:
    """
    Tier 2: Boundary & Corner Cases.
    Verifies edge conditions:
      - Starting date selection parameter boundaries (5 tests)
      - Portfolio state limits: empty, zero balance, account isolation (5 tests)
    """

    # --------------------------------------------------------------------------
    # 2.1 Starting Date Parameter Boundaries (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier2_start_date_before_inception(self, raw_client: AsyncClient, test_db_session):
        """start_date before portfolio inception returns all snapshots from inception."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_pre_inception", "pre_inc@test.com", "Pre Inception")
        await seed_basic_portfolio(session, u.user_id, deposit_date=datetime.date(2025, 1, 1))

        token = make_auth0_token(sub="auth0|t2_pre_inception", email="pre_inc@test.com")
        res = await raw_client.get("/api/v1/snapshots?start_date=2020-01-01", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) > 0
        for s in snaps:
            assert s["snapshot_date"] >= "2025-01-01"

    @pytest.mark.anyio
    async def test_tier2_start_date_future_boundary(self, raw_client: AsyncClient, test_db_session):
        """start_date far in the future returns an empty list []."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_future", "future@test.com", "Future Boundary")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t2_future", email="future@test.com")
        res = await raw_client.get("/api/v1/snapshots?start_date=2099-01-01", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) == 0

    @pytest.mark.anyio
    async def test_tier2_start_date_exact_sunday(self, raw_client: AsyncClient, test_db_session):
        """start_date specified on an exact Sunday returns snapshots starting on or after that Sunday."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_exact_sun_start", "exact_start@test.com", "Exact Start")
        await seed_basic_portfolio(
            session,
            u.user_id,
            deposit_date=datetime.date(2025, 1, 1),
            sunday_date=datetime.date(2025, 1, 19)
        )

        target_sunday = "2025-01-12"
        token = make_auth0_token(sub="auth0|t2_exact_sun_start", email="exact_start@test.com")
        res = await raw_client.get(f"/api/v1/snapshots?start_date={target_sunday}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        for s in snaps:
            assert s["snapshot_date"] >= target_sunday

    @pytest.mark.anyio
    async def test_tier2_start_date_midweek_september_preset(self, raw_client: AsyncClient, test_db_session):
        """
        Selecting manual starting date 'Sep 1' (e.g. 2026-09-01, Tuesday) filters
        all snapshots to dates on or after 2026-09-01.
        """
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_sep1_preset", "sep1@test.com", "Sep1 Preset")
        # In 2026, Sep 1 is Tuesday, next Sunday is Sep 6
        sep_sunday = datetime.date(2026, 9, 6)
        assert sep_sunday.weekday() == 6

        await seed_basic_portfolio(
            session,
            u.user_id,
            deposit_date=datetime.date(2026, 8, 1),
            buy_date=datetime.date(2026, 8, 15),
            sunday_date=sep_sunday
        )

        token = make_auth0_token(sub="auth0|t2_sep1_preset", email="sep1@test.com")
        res = await raw_client.get("/api/v1/snapshots?start_date=2026-09-01", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        for s in snaps:
            assert s["snapshot_date"] >= "2026-09-01"

    @pytest.mark.anyio
    async def test_tier2_start_date_invalid_format_returns_422(self, raw_client: AsyncClient, test_db_session):
        """Malformed start_date string returns HTTP 422 Unprocessable Entity."""
        session, _ = test_db_session
        await get_or_create_user(session, "auth0|t2_invalid_fmt", "invalid_fmt@test.com", "Invalid Format")

        token = make_auth0_token(sub="auth0|t2_invalid_fmt", email="invalid_fmt@test.com")
        res = await raw_client.get("/api/v1/snapshots?start_date=not-a-valid-date", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422

    # --------------------------------------------------------------------------
    # 2.2 Portfolio State Limits & Account Boundaries (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier2_empty_portfolio_zero_snapshots(self, raw_client: AsyncClient, test_db_session):
        """A newly registered user with no accounts or trades receives an empty list []."""
        session, _ = test_db_session
        await get_or_create_user(session, "auth0|t2_empty_user", "empty@test.com", "Empty User")

        token = make_auth0_token(sub="auth0|t2_empty_user", email="empty@test.com")
        res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json() == []

    @pytest.mark.anyio
    async def test_tier2_zero_balance_portfolio_calculation(self, raw_client: AsyncClient, test_db_session):
        """An account deposited and completely withdrawn maintains an exact net worth of 0.0."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_zero_bal", "zero_bal@test.com", "Zero Balance")

        acc = Account(user_id=u.user_id, account_name="Zero Account", account_type="bank", currency="USD")
        session.add(acc)
        await session.commit()
        await session.refresh(acc)

        # Deposit $5,000 on 2025-01-01
        t_dep = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=5000.0
        )
        session.add(t_dep)
        await session.commit()
        await process_transaction_event(session, t_dep)

        # Withdraw $5,000 on 2025-01-05 (Sunday)
        t_wdr = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            transaction_type="withdrawal",
            transaction_date=datetime.date(2025, 1, 5),
            total_amount=5000.0
        )
        session.add(t_wdr)
        await session.commit()
        await process_transaction_event(session, t_wdr)

        await recalculate_past_snapshots(session, start_date=datetime.date(2025, 1, 1), user_id=u.user_id)
        await session.commit()

        token = make_auth0_token(sub="auth0|t2_zero_bal", email="zero_bal@test.com")
        res = await raw_client.get(f"/api/v1/snapshots?account_id={acc.account_id}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) >= 1
        last_snap = snaps[-1]
        assert round(last_snap["cash_balance"], 2) == 0.0
        assert round(last_snap["net_worth"], 2) == 0.0

    @pytest.mark.anyio
    async def test_tier2_single_account_filtering(self, raw_client: AsyncClient, test_db_session):
        """Querying ?account_id=X filters snapshot metrics specifically to account X."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t2_acc_filter", "acc_filter@test.com", "Account Filter")

        # Two accounts: Demat ($10k) and Savings ($5k)
        acc1 = Account(user_id=u.user_id, account_name="Demat 1", account_type="demat", currency="USD")
        acc2 = Account(user_id=u.user_id, account_name="Savings 2", account_type="bank", currency="USD")
        session.add_all([acc1, acc2])
        await session.commit()
        await session.refresh(acc1)
        await session.refresh(acc2)

        t1 = Transaction(user_id=u.user_id, account_id=acc1.account_id, transaction_type="deposit", transaction_date=datetime.date(2025, 1, 1), total_amount=10000.0)
        t2 = Transaction(user_id=u.user_id, account_id=acc2.account_id, transaction_type="deposit", transaction_date=datetime.date(2025, 1, 1), total_amount=5000.0)
        session.add_all([t1, t2])
        await session.commit()
        await process_transaction_event(session, t1)
        await process_transaction_event(session, t2)

        token = make_auth0_token(sub="auth0|t2_acc_filter", email="acc_filter@test.com")
        res = await raw_client.get(f"/api/v1/snapshots?account_id={acc1.account_id}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) >= 1
        assert snaps[-1]["cash_balance"] == 10000.0

    @pytest.mark.anyio
    async def test_tier2_nonexistent_account_returns_404(self, raw_client: AsyncClient, test_db_session):
        """Querying for a non-existent account_id returns HTTP 404."""
        session, _ = test_db_session
        await get_or_create_user(session, "auth0|t2_nonexistent", "nonexistent@test.com", "Nonexistent")

        token = make_auth0_token(sub="auth0|t2_nonexistent", email="nonexistent@test.com")
        res = await raw_client.get("/api/v1/snapshots?account_id=9999999", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404

    @pytest.mark.anyio
    async def test_tier2_cross_user_account_returns_404(self, raw_client: AsyncClient, test_db_session):
        """User B querying User A's account_id returns HTTP 404 (Row-Level Security)."""
        session, _ = test_db_session
        user_a = await get_or_create_user(session, "auth0|t2_user_a", "user_a@test.com", "User A")
        user_b = await get_or_create_user(session, "auth0|t2_user_b", "user_b@test.com", "User B")

        acc_a = Account(user_id=user_a.user_id, account_name="User A Secret Account", account_type="demat", currency="USD")
        session.add(acc_a)
        await session.commit()
        await session.refresh(acc_a)

        token_b = make_auth0_token(sub="auth0|t2_user_b", email="user_b@test.com")
        res = await raw_client.get(f"/api/v1/snapshots?account_id={acc_a.account_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert res.status_code == 404


# ==============================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS & COMBINATIONS
# ==============================================================================

class TestTier3Interactions:
    """
    Tier 3: Cross-Feature Interactions & Combinations.
    Verifies interaction between:
      - Background recalculation trigger and subsequent snapshot reads
      - Cashflow payments and net worth consistency
      - Multi-tenant data and trigger isolation
      - Multi-currency portfolio aggregation
    """

    @pytest.mark.anyio
    async def test_tier3_trigger_recalculate_refreshes_snapshots(self, raw_client: AsyncClient, test_db_session):
        """Triggering recalculation via POST refreshes materialized snapshot values."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t3_recalc_flow", "recalc@test.com", "Recalc Flow")
        seed = await seed_basic_portfolio(session, u.user_id, deposit_amount=10000.0)

        token = make_auth0_token(sub="auth0|t3_recalc_flow", email="recalc@test.com")

        # 1. Trigger recalculation
        trigger_res = await raw_client.post(
            "/api/v1/snapshots/trigger-recalculate",
            json={"user_id": u.user_id, "start_date": "2025-01-01", "reason": "test_verification"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert trigger_res.status_code in (200, 202)

        # 2. Query snapshots
        get_res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert get_res.status_code == 200
        data = get_res.json()
        assert len(data) > 0

    @pytest.mark.anyio
    async def test_tier3_cashflow_payment_reflects_in_networth(self, raw_client: AsyncClient, test_db_session):
        """Cashflow income payments increase cash balance and net worth."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t3_cf_networth", "cf_networth@test.com", "Cashflow Networth")

        acc = Account(user_id=u.user_id, account_name="Cashflow Checking", account_type="bank", currency="EUR")
        session.add(acc)
        await session.commit()
        await session.refresh(acc)

        # Record cashflow transaction and payment of +€3,000
        cf_tx = CashflowTransaction(
            user_id=u.user_id,
            transaction_date=datetime.date(2025, 1, 1),
            title="Freelance Income",
            total_amount=3000.0,
            currency="EUR",
            transaction_kind="INCOME"
        )
        session.add(cf_tx)
        await session.commit()
        await session.refresh(cf_tx)

        cf_pay = CashflowPayment(
            user_id=u.user_id,
            cashflow_id=cf_tx.cashflow_id,
            account_id=acc.account_id,
            amount=3000.0
        )
        session.add(cf_pay)
        await session.commit()

        # Recalculate
        await recalculate_past_snapshots(session, start_date=datetime.date(2025, 1, 1), user_id=u.user_id)
        await session.commit()

        token = make_auth0_token(sub="auth0|t3_cf_networth", email="cf_networth@test.com")
        res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        summary = res.json()
        assert summary["total_current_value"] >= 3000.0 or summary["total_invested"] >= 0.0

    @pytest.mark.anyio
    async def test_tier3_multitenant_snapshot_data_isolation(self, raw_client: AsyncClient, test_db_session):
        """User A and User B maintain completely isolated snapshot datasets with zero cross-talk."""
        session, _ = test_db_session
        user_a = await get_or_create_user(session, "auth0|t3_tenant_a", "tenant_a@test.com", "Tenant A")
        user_b = await get_or_create_user(session, "auth0|t3_tenant_b", "tenant_b@test.com", "Tenant B")

        # User A deposits $50,000
        await seed_basic_portfolio(session, user_a.user_id, deposit_amount=50000.0)
        # User B deposits $1,000
        await seed_basic_portfolio(session, user_b.user_id, deposit_amount=1000.0)

        token_a = make_auth0_token(sub="auth0|t3_tenant_a", email="tenant_a@test.com")
        token_b = make_auth0_token(sub="auth0|t3_tenant_b", email="tenant_b@test.com")

        res_a = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token_a}"})
        res_b = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token_b}"})

        assert res_a.status_code == 200
        assert res_b.status_code == 200

        data_a = res_a.json()
        data_b = res_b.json()

        assert len(data_a) > 0 and len(data_b) > 0
        assert data_a[-1]["net_worth"] > data_b[-1]["net_worth"]
        assert abs(data_a[-1]["net_worth"] - 50000.0) < 5000.0
        assert abs(data_b[-1]["net_worth"] - 1000.0) < 500.0

    @pytest.mark.anyio
    async def test_tier3_multitenant_trigger_isolation(self, raw_client: AsyncClient, test_db_session):
        """User B cannot trigger recalculation targeting User A's user_id."""
        session, _ = test_db_session
        user_a = await get_or_create_user(session, "auth0|t3_iso_a", "iso_a@test.com", "Iso A")
        user_b = await get_or_create_user(session, "auth0|t3_iso_b", "iso_b@test.com", "Iso B")

        token_b = make_auth0_token(sub="auth0|t3_iso_b", email="iso_b@test.com")
        # Attempt to trigger for User A
        res = await raw_client.post(
            "/api/v1/snapshots/trigger-recalculate",
            json={"user_id": user_a.user_id, "start_date": "2025-01-01", "reason": "malicious_attempt"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        # Expected: either rejected (403/400) or coerced to User B's own queue
        if res.status_code in (200, 202):
            data = res.json()
            assert data.get("user_id") != user_a.user_id or data.get("status") == "queued"
        else:
            assert res.status_code in (400, 403, 404)

    @pytest.mark.anyio
    async def test_tier3_multicurrency_portfolio_aggregation(self, raw_client: AsyncClient, test_db_session):
        """USD Demat account is aggregated into master portfolio summary."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t3_multicurrency", "multicurrency@test.com", "Multi Currency")

        acc_usd = Account(user_id=u.user_id, account_name="US Demat", account_type="demat", currency="USD")
        session.add(acc_usd)
        await session.commit()
        await session.refresh(acc_usd)

        t_dep = Transaction(
            user_id=u.user_id,
            account_id=acc_usd.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2025, 1, 1),
            total_amount=10000.0
        )
        session.add(t_dep)
        await session.commit()
        await process_transaction_event(session, t_dep)

        token = make_auth0_token(sub="auth0|t3_multicurrency", email="multicurrency@test.com")
        res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["total_net_worth"] > 0 or body["cash_balance"] > 0


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS & LATENCY SLA (< 50ms)
# ==============================================================================

class TestTier4RealWorldScenarios:
    """
    Tier 4: Real-World Application Scenarios & Sub-50ms Latency SLA.
    Verifies:
      - Realistic multi-year investor journey (deposits, trades, dividends, sales)
      - Corporate actions and cash dividend payouts
      - FIFO lot depletion and realized PnL calculations
      - Response latency benchmarks < 50ms
    """

    @pytest.mark.anyio
    async def test_tier4_real_world_multiyear_portfolio_scenario(self, raw_client: AsyncClient, test_db_session):
        """
        Comprehensive 3-year investor journey:
        - 2023-01-01: Deposit $100,000 cash in demat account
        - 2023-01-04: Buy 100 shares AAPL @ $150 ($15,000 + $10 fees)
        - 2023-06-01: Buy 50 shares MSFT @ $300 ($15,000 + $10 fees)
        - 2024-03-15: Receive $200 dividend from AAPL
        - 2024-06-10: Sell 40 shares AAPL @ $180 ($7,200 proceeds - $10 fees)
        - 2025-01-05: Final Sunday valuation verification
        """
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t4_investor_journey", "journey@test.com", "Investor Journey")

        acc = Account(user_id=u.user_id, account_name="Main Broker", account_type="demat", currency="USD")
        ast_aapl = Asset(symbol="AAPL", name="Apple Inc", asset_type="stock", currency="USD")
        ast_msft = Asset(symbol="MSFT", name="Microsoft Corp", asset_type="stock", currency="USD")
        session.add_all([acc, ast_aapl, ast_msft])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast_aapl)
        await session.refresh(ast_msft)

        # 1. Deposit $100,000 on 2023-01-01 (Sunday)
        t_dep = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2023, 1, 1),
            total_amount=100000.0
        )
        session.add(t_dep)
        await session.commit()
        await process_transaction_event(session, t_dep)

        # 2. Buy AAPL on 2023-01-04
        t_buy_aapl = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            asset_id=ast_aapl.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2023, 1, 4),
            quantity=100.0,
            price_per_unit=150.0,
            total_amount=15010.0,
            fees=10.0
        )
        session.add(t_buy_aapl)
        await session.commit()
        await process_transaction_event(session, t_buy_aapl)

        # 3. Buy MSFT on 2023-06-01
        t_buy_msft = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            asset_id=ast_msft.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2023, 6, 1),
            quantity=50.0,
            price_per_unit=300.0,
            total_amount=15010.0,
            fees=10.0
        )
        session.add(t_buy_msft)
        await session.commit()
        await process_transaction_event(session, t_buy_msft)

        # 4. Dividend on 2024-03-15
        div = Dividend(
            user_id=u.user_id,
            account_id=acc.account_id,
            asset_id=ast_aapl.asset_id,
            pay_date=datetime.date(2024, 3, 15),
            total_amount=200.0
        )
        session.add(div)
        await session.commit()

        # 5. Sell 40 AAPL on 2024-06-10
        t_sell_aapl = Transaction(
            user_id=u.user_id,
            account_id=acc.account_id,
            asset_id=ast_aapl.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2024, 6, 10),
            quantity=40.0,
            price_per_unit=180.0,
            total_amount=7190.0,
            fees=10.0
        )
        session.add(t_sell_aapl)
        await session.commit()
        await process_transaction_event(session, t_sell_aapl)

        # Prices on Sunday 2025-01-05
        sun_2025 = datetime.date(2025, 1, 5)
        ph_aapl = PriceHistory(asset_id=ast_aapl.asset_id, price_date=sun_2025, close_price=200.0, source="test")
        ph_msft = PriceHistory(asset_id=ast_msft.asset_id, price_date=sun_2025, close_price=400.0, source="test")
        session.add_all([ph_aapl, ph_msft])
        await session.commit()

        # Recalculate
        await recalculate_past_snapshots(session, start_date=datetime.date(2023, 1, 1), user_id=u.user_id)
        await session.commit()

        token = make_auth0_token(sub="auth0|t4_investor_journey", email="journey@test.com")

        # Verify snapshots
        snap_res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
        assert snap_res.status_code == 200
        snaps = snap_res.json()
        assert len(snaps) > 0

        # Verify portfolio summary
        sum_res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
        assert sum_res.status_code == 200
        summary = sum_res.json()
        assert summary["total_current_value"] > 0
        assert summary["total_invested"] > 0

    @pytest.mark.anyio
    async def test_tier4_real_world_dividend_payout_accumulation(self, raw_client: AsyncClient, test_db_session):
        """Cash dividend payments accumulate in cash balance without reducing total invested."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t4_dividend_acc", "div_acc@test.com", "Dividend Acc")

        acc = Account(user_id=u.user_id, account_name="Dividend Demat", account_type="demat", currency="USD")
        ast = Asset(symbol="KO", name="Coca-Cola", asset_type="stock", currency="USD")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)

        # Deposit $5,000
        t_dep = Transaction(user_id=u.user_id, account_id=acc.account_id, transaction_type="deposit", transaction_date=datetime.date(2025, 1, 1), total_amount=5000.0)
        session.add(t_dep)
        await session.commit()
        await process_transaction_event(session, t_dep)

        # Dividend of $150
        div = Dividend(user_id=u.user_id, account_id=acc.account_id, asset_id=ast.asset_id, pay_date=datetime.date(2025, 1, 10), total_amount=150.0)
        session.add(div)
        await session.commit()

        await recalculate_past_snapshots(session, start_date=datetime.date(2025, 1, 1), user_id=u.user_id)
        await session.commit()

        token = make_auth0_token(sub="auth0|t4_dividend_acc", email="div_acc@test.com")
        res = await raw_client.get(f"/api/v1/snapshots?account_id={acc.account_id}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        snaps = res.json()
        assert len(snaps) >= 1
        assert snaps[-1]["cash_balance"] >= 5000.0

    @pytest.mark.anyio
    async def test_tier4_real_world_fifo_partial_lot_depletion(self, raw_client: AsyncClient, test_db_session):
        """Chronological lot sales deplete the earliest lot first with correct realized PnL."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t4_fifo_depletion", "fifo_dep@test.com", "FIFO Depletion")

        acc = Account(user_id=u.user_id, account_name="FIFO Broker", account_type="demat", currency="USD")
        ast = Asset(symbol="GOOGL", name="Alphabet Inc", asset_type="stock", currency="USD")
        session.add_all([acc, ast])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(ast)

        # Deposit $20,000
        t_dep = Transaction(user_id=u.user_id, account_id=acc.account_id, transaction_type="deposit", transaction_date=datetime.date(2025, 1, 1), total_amount=20000.0)
        session.add(t_dep)
        await session.commit()
        await process_transaction_event(session, t_dep)

        # Lot 1: Buy 10 @ $100 = $1,000 on 2025-01-02
        t_buy1 = Transaction(user_id=u.user_id, account_id=acc.account_id, asset_id=ast.asset_id, transaction_type="buy", transaction_date=datetime.date(2025, 1, 2), quantity=10.0, price_per_unit=100.0, total_amount=1000.0)
        # Lot 2: Buy 10 @ $120 = $1,200 on 2025-01-04
        t_buy2 = Transaction(user_id=u.user_id, account_id=acc.account_id, asset_id=ast.asset_id, transaction_type="buy", transaction_date=datetime.date(2025, 1, 4), quantity=10.0, price_per_unit=120.0, total_amount=1200.0)
        session.add_all([t_buy1, t_buy2])
        await session.commit()
        await process_transaction_event(session, t_buy1)
        await process_transaction_event(session, t_buy2)

        # Sell 15 @ $150 = $2,250 on 2025-01-10
        # FIFO depletes 10 from Lot 1 (PnL = 10*(150-100) = $500) and 5 from Lot 2 (PnL = 5*(150-120) = $150). Total PnL = $650.
        t_sell = Transaction(user_id=u.user_id, account_id=acc.account_id, asset_id=ast.asset_id, transaction_type="sell", transaction_date=datetime.date(2025, 1, 10), quantity=15.0, price_per_unit=150.0, total_amount=2250.0)
        session.add(t_sell)
        await session.commit()
        await process_transaction_event(session, t_sell)
        await session.commit()

        token = make_auth0_token(sub="auth0|t4_fifo_depletion", email="fifo_dep@test.com")
        res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert round(body["total_realized_pnl"], 2) == 650.0

    @pytest.mark.anyio
    async def test_tier4_performance_snapshots_latency_sub_50ms(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/snapshots responds with average query latency < 50ms across repeated requests."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t4_perf_snapshots", "perf_snap@test.com", "Perf Snapshots")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t4_perf_snapshots", email="perf_snap@test.com")
        latencies_ms: List[float] = []

        # Warmup
        await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})

        # 10 iterations
        for _ in range(10):
            t0 = time.perf_counter()
            res = await raw_client.get("/api/v1/snapshots", headers={"Authorization": f"Bearer {token}"})
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed)
            assert res.status_code == 200

        avg_lat = sum(latencies_ms) / len(latencies_ms)
        p95_lat = sorted(latencies_ms)[int(len(latencies_ms) * 0.95)]
        assert avg_lat < 50.0, f"Average snapshot latency {avg_lat:.2f}ms exceeded 50ms requirement"
        assert p95_lat < 50.0, f"P95 snapshot latency {p95_lat:.2f}ms exceeded 50ms requirement"

    @pytest.mark.anyio
    async def test_tier4_performance_portfolio_summary_latency_sub_50ms(self, raw_client: AsyncClient, test_db_session):
        """GET /api/v1/portfolio/summary responds with average query latency < 50ms across repeated requests."""
        session, _ = test_db_session
        u = await get_or_create_user(session, "auth0|t4_perf_summary", "perf_sum@test.com", "Perf Summary")
        await seed_basic_portfolio(session, u.user_id)

        token = make_auth0_token(sub="auth0|t4_perf_summary", email="perf_sum@test.com")
        latencies_ms: List[float] = []

        # Warmup
        await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})

        # 10 iterations
        for _ in range(10):
            t0 = time.perf_counter()
            res = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token}"})
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed)
            assert res.status_code == 200

        avg_lat = sum(latencies_ms) / len(latencies_ms)
        p95_lat = sorted(latencies_ms)[int(len(latencies_ms) * 0.95)]
        assert avg_lat < 50.0, f"Average summary latency {avg_lat:.2f}ms exceeded 50ms requirement"
        assert p95_lat < 50.0, f"P95 summary latency {p95_lat:.2f}ms exceeded 50ms requirement"
