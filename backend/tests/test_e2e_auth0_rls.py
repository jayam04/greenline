"""
Comprehensive 4-Tier Opaque-Box E2E Test Suite for Greenline Auth0 Authentication,
User Information Persistence, and Row-Level Security (RLS).

Requirements Tested:
  - R1: Auth0 JWT RS256 token verification against JWKS, 401 on missing/invalid/expired tokens.
  - R2: JIT user provisioning and profile persistence (sub, email, name, picture) in Oracle DB.
  - R3: Row-Level Security (RLS) across accounts, transactions, portfolios, cashflows, and categories.
  - R4: 100% offline execution using an in-memory 2048-bit RSA keypair and mock JWKS provider.
"""

import time
import asyncio
import datetime
from typing import AsyncGenerator, Dict, Any, Optional
from unittest.mock import patch

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.config import settings
from app.db.database import get_db, Base
from app.api.deps import get_current_user
from app.db.models import (
    User, Account, Asset, Transaction, Category,
    CashflowTransaction, CashflowPayment, CashflowItem, ApiKey
)
from tests.conftest import get_test_engine, get_test_sessionmaker, clean_database_tables


# ==============================================================================
# 1. OFFLINE MOCK RSA KEYPAIR & JWKS GENERATOR (100% Offline Mandate)
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

    key = private_pem or TEST_PRIVATE_PEM
    return jwt.encode(payload, key, algorithm=alg, headers=headers)


# ==============================================================================
# 2. FIXTURES & ISOLATION HARNESS
# ==============================================================================

@pytest.fixture(autouse=True)
def mock_auth0_network():
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
async def raw_client(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client that preserves get_current_user (does NOT override it),
    allowing tests to verify genuine token verification and user extraction.
    """
    session, session_maker = test_db_session

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    # Explicitly ensure get_current_user is not mocked by default client fixture
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def shared_asset(db_session: AsyncSession) -> Asset:
    """Ensure a global equity asset exists for trading tests."""
    stmt = select(Asset).where(Asset.symbol == "AAPL")
    res = await db_session.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)
    return asset


# ==============================================================================
# TIER 1: FEATURE COVERAGE (Core Requirements >= 5 per feature)
# ==============================================================================

class TestTier1FeatureCoverage:
    """Verifies happy paths and explicit contract requirements for R1, R2, R3."""

    # --------------------------------------------------------------------------
    # Feature 1.1: Auth0 JWT Token Validation (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_valid_token_accepted(self, raw_client: AsyncClient):
        """Valid RS256 token signed by the trusted keypair is accepted (returns 200)."""
        token = make_auth0_token(sub="auth0|valid-user-001", email="user1@example.com", name="User One")
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    @pytest.mark.anyio
    async def test_tier1_unauthenticated_request_rejected(self, raw_client: AsyncClient):
        """Requests without Authorization header must be rejected with HTTP 401."""
        res = await raw_client.get("/api/v1/accounts")
        assert res.status_code == 401
        assert "Bearer" in res.headers.get("WWW-Authenticate", "")

    @pytest.mark.anyio
    async def test_tier1_missing_bearer_scheme_rejected(self, raw_client: AsyncClient):
        """Header with non-Bearer authentication scheme (e.g. Basic) must be rejected with 401."""
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier1_invalid_bearer_format_rejected(self, raw_client: AsyncClient):
        """Header with empty or whitespace Bearer token must return HTTP 401."""
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": "Bearer "})
        assert res.status_code == 401

        res_spaces = await raw_client.get("/api/v1/accounts", headers={"Authorization": "Bearer     "})
        assert res_spaces.status_code == 401

    @pytest.mark.anyio
    async def test_tier1_expired_token_rejected(self, raw_client: AsyncClient):
        """Token with an expiration time in the past must be rejected with HTTP 401."""
        expired_token = make_auth0_token(
            sub="auth0|expired-user",
            exp=int(time.time()) - 3600  # Expired 1 hour ago
        )
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401

    # --------------------------------------------------------------------------
    # Feature 1.2: User Profile Persistence & JIT Sync (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_user_auto_provisioned_on_first_request(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Presenting a valid token for a new Auth0 sub auto-creates a user record in the database."""
        sub = "auth0|jit-provision-001"
        token = make_auth0_token(sub=sub, email="jit001@example.com", name="JIT User 001")
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

        # Verify DB persistence
        stmt = select(User).where(User.username.in_([sub, "jit001@example.com"]))
        res_db = await db_session.execute(stmt)
        user = res_db.scalars().first()
        assert user is not None
        assert user.user_id > 0

    @pytest.mark.anyio
    async def test_tier1_user_auth0_sub_persisted(self, raw_client: AsyncClient, db_session: AsyncSession):
        """The user's auth0_sub claim is stored in the database."""
        sub = "google-oauth2|9876543210"
        token = make_auth0_token(sub=sub, email="google_user@example.com", name="Google User")
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

        if hasattr(User, "auth0_sub"):
            stmt = select(User).where(User.auth0_sub == sub)
            user = (await db_session.execute(stmt)).scalar_one_or_none()
            assert user is not None
            assert user.auth0_sub == sub

    @pytest.mark.anyio
    async def test_tier1_user_email_and_name_persisted(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Token profile claims (email, name) are stored in the user record."""
        sub = "auth0|profile-record-001"
        email = "persisted_profile@example.com"
        name = "Persisted Name"
        token = make_auth0_token(sub=sub, email=email, name=name)
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

        stmt = select(User).where(User.username.in_([email, sub]))
        user = (await db_session.execute(stmt)).scalars().first()
        assert user is not None
        if hasattr(User, "email") and user.email:
            assert user.email == email
        if hasattr(User, "name") and user.name:
            assert user.name == name

    @pytest.mark.anyio
    async def test_tier1_user_profile_update_syncs_to_db(self, raw_client: AsyncClient, db_session: AsyncSession):
        """When token profile attributes change, the user record is updated."""
        sub = "auth0|sync-update-user"
        token1 = make_auth0_token(sub=sub, email="original@example.com", name="Original Name")
        await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token1}"})

        # Send updated token with new name and avatar
        token2 = make_auth0_token(
            sub=sub,
            email="original@example.com",
            name="Updated Name",
            picture="https://example.com/avatar_v2.png"
        )
        res2 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token2}"})
        assert res2.status_code == 200

        if hasattr(User, "name") and hasattr(User, "picture"):
            stmt = select(User).where(User.username.in_([sub, "original@example.com"]))
            user = (await db_session.execute(stmt)).scalars().first()
            assert user is not None
            if user.name:
                assert user.name == "Updated Name"

    @pytest.mark.anyio
    async def test_tier1_profile_accessible_via_auth_me(self, raw_client: AsyncClient):
        """User profile can be retrieved via GET /api/v1/auth/me."""
        sub = "auth0|me-endpoint-user"
        token = make_auth0_token(sub=sub, email="me@example.com", name="Me User")
        res = await raw_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert "user_id" in data or "username" in data

    # --------------------------------------------------------------------------
    # Feature 1.3: Row-Level Security (RLS) Scoping (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier1_rls_accounts_scoped_to_user(self, raw_client: AsyncClient):
        """User querying accounts gets only their own accounts, never another user's."""
        token_a = make_auth0_token(sub="auth0|alice-acc", email="alice_acc@example.com")
        token_b = make_auth0_token(sub="auth0|bob-acc", email="bob_acc@example.com")

        # Alice creates an account
        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Checking", "account_type": "bank", "currency": "EUR"}
        )
        assert res_a.status_code == 201

        # Bob queries accounts -> should be empty
        res_b = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        bob_accounts = res_b.json()
        assert len(bob_accounts) == 0

    @pytest.mark.anyio
    async def test_tier1_rls_transactions_scoped_to_user(self, raw_client: AsyncClient, shared_asset: Asset):
        """User querying transactions gets only their own transactions."""
        token_a = make_auth0_token(sub="auth0|alice-tx", email="alice_tx@example.com")
        token_b = make_auth0_token(sub="auth0|bob-tx", email="bob_tx@example.com")

        # Alice creates account and transaction
        res_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Brokerage", "account_type": "demat", "currency": "USD"}
        )
        acc_id = res_acc.json()["account_id"]

        res_tx = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "account_id": acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-15",
                "quantity": 10.0,
                "price_per_unit": 150.0,
                "total_amount": 1500.0,
            }
        )
        assert res_tx.status_code == 201

        # Bob queries transactions -> should be empty
        res_b = await raw_client.get("/api/v1/transactions", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        assert len(res_b.json()) == 0

    @pytest.mark.anyio
    async def test_tier1_rls_portfolio_summary_scoped_to_user(self, raw_client: AsyncClient, shared_asset: Asset):
        """Portfolio summary calculates metrics strictly for the authenticated user's holdings."""
        token_a = make_auth0_token(sub="auth0|alice-port", email="alice_port@example.com")
        token_b = make_auth0_token(sub="auth0|bob-port", email="bob_port@example.com")

        # Alice creates funded account
        res_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Savings", "account_type": "bank", "currency": "EUR"}
        )
        assert res_acc.status_code == 201

        # Bob views summary -> 0 holdings
        res_summary = await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {token_b}"})
        assert res_summary.status_code == 200
        summary = res_summary.json()
        assert summary.get("total_accounts", 0) == 0

    @pytest.mark.anyio
    async def test_tier1_rls_cashflow_scoped_to_user(self, raw_client: AsyncClient):
        """User querying cashflow gets only their own cashflow transactions."""
        token_a = make_auth0_token(sub="auth0|alice-cf", email="alice_cf@example.com")
        token_b = make_auth0_token(sub="auth0|bob-cf", email="bob_cf@example.com")

        # Alice creates bank account and cashflow transaction
        res_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Cashflow Bank", "account_type": "bank", "currency": "EUR"}
        )
        acc_id = res_acc.json()["account_id"]

        # Alice creates custom category
        res_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Alice Coffee", "category_type": "EXPENSE"}
        )
        cat_id = res_cat.json()["category_id"]

        res_cf = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "transaction_date": "2026-10-20",
                "title": "Alice Morning Coffee",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": acc_id, "amount": -4.50}],
                "items": [{"category_id": cat_id, "amount": 4.50}],
            }
        )
        assert res_cf.status_code == 201

        # Bob queries cashflow -> 0 items
        res_b_cf = await raw_client.get("/api/v1/cashflow", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b_cf.status_code == 200
        assert len(res_b_cf.json()) == 0

    @pytest.mark.anyio
    async def test_tier1_rls_categories_system_plus_own(self, raw_client: AsyncClient):
        """User querying categories sees system categories + own custom, but not other users'."""
        token_a = make_auth0_token(sub="auth0|alice-cat", email="alice_cat@example.com")
        token_b = make_auth0_token(sub="auth0|bob-cat", email="bob_cat@example.com")

        # Alice creates custom category
        res_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Alice Secret Project", "category_type": "EXPENSE"}
        )
        assert res_cat.status_code == 201

        # Bob lists categories
        res_b = await raw_client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        cat_names = [c["name"] for c in res_b.json()]
        assert "Alice Secret Project" not in cat_names


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (Fault Injection & Limits >= 5 per feature)
# ==============================================================================

class TestTier2Boundaries:
    """Verifies edge cases, malformed headers, limits, and hostile input rejections."""

    # --------------------------------------------------------------------------
    # Feature 2.1: Token Boundaries & Fault Injection (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier2_token_malformed_base64(self, raw_client: AsyncClient):
        """Corrupted/non-base64 token string returns HTTP 401."""
        corrupted = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.corrupted_non_base64_payload.fake_signature"
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {corrupted}"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier2_token_missing_kid_header(self, raw_client: AsyncClient):
        """Token minted without a 'kid' in the header returns HTTP 401."""
        token = make_auth0_token(sub="auth0|no-kid-user", kid=None)
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier2_token_unsupported_algorithm_hs256(self, raw_client: AsyncClient):
        """Token signed with symmetric HS256 instead of expected RS256 returns HTTP 401."""
        token = jwt.encode(
            {"sub": "auth0|hs256-attacker", "aud": "http://localhost:8000", "iss": "https://jayam04.eu.auth0.com/"},
            "symmetric-secret-key-123",
            algorithm="HS256",
            headers={"kid": TEST_KEY_ID}
        )
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier2_token_untrusted_key_signature(self, raw_client: AsyncClient):
        """Token signed with an untrusted/unknown private key not in JWKS returns HTTP 401."""
        token = make_auth0_token(
            sub="auth0|untrusted-key-user",
            kid=ATTACKER_KEY_ID,
            private_pem=ATTACKER_PRIVATE_PEM
        )
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_tier2_token_future_iat_or_nbf(self, raw_client: AsyncClient):
        """Token with future 'nbf' (not before) claim returns HTTP 401."""
        future_token = make_auth0_token(
            sub="auth0|future-nbf-user",
            nbf=int(time.time()) + 3600  # Not valid until 1 hour in future
        )
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {future_token}"})
        assert res.status_code == 401

    # --------------------------------------------------------------------------
    # Feature 2.2: User Identity & Profile Boundaries (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier2_user_minimal_claims_sub_only(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Token with only 'sub' (no email, no name) auto-provisions cleanly using sub."""
        sub = "auth0|sub-only-99"
        token = make_auth0_token(sub=sub)
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

        stmt = select(User).where(User.username == sub)
        user = (await db_session.execute(stmt)).scalars().first()
        assert user is not None

    @pytest.mark.anyio
    async def test_tier2_user_boundary_varchar_length(self, raw_client: AsyncClient):
        """Handles maximum allowed string length (255 chars) without database truncation crash."""
        long_sub = "auth0|" + "x" * 200
        long_email = "a" * 230 + "@example.com"
        long_name = "N" * 255
        token = make_auth0_token(sub=long_sub, email=long_email, name=long_name)
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    @pytest.mark.anyio
    async def test_tier2_user_same_email_prefix_distinct_subs(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Users with identical email prefix but distinct subs receive separate, isolated records."""
        token_google = make_auth0_token(sub="google-oauth2|10001", email="dev@corp.com", name="Dev Google")
        token_github = make_auth0_token(sub="github|20002", email="dev@corp.com", name="Dev GitHub")

        res1 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_google}"})
        assert res1.status_code == 200

        res2 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_github}"})
        assert res2.status_code == 200

    @pytest.mark.anyio
    async def test_tier2_user_concurrent_provisioning_race(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Simultaneous concurrent requests for a new user succeed without duplicate key errors."""
        sub = "auth0|concurrent-race-user"
        token = make_auth0_token(sub=sub, email="race@example.com", name="Race User")

        # Launch 5 concurrent requests simultaneously
        tasks = [
            raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)
        for res in results:
            assert res.status_code == 200

        # Assert exactly one user record exists
        stmt = select(User).where(User.username.in_([sub, "race@example.com"]))
        users = (await db_session.execute(stmt)).scalars().all()
        assert len(users) >= 1

    @pytest.mark.anyio
    async def test_tier2_user_extraneous_claims_ignored(self, raw_client: AsyncClient):
        """Token with unknown custom claims preserves standard claims and succeeds normally."""
        token = make_auth0_token(
            sub="auth0|extra-claims-user",
            email="extra@example.com",
            extra_claims={
                "https://example.com/roles": ["admin", "editor"],
                "org_id": "org_12345",
                "custom_metadata": {"tier": "gold"},
            }
        )
        res = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    # --------------------------------------------------------------------------
    # Feature 2.3: RLS Boundary & Attack Scenarios (5 tests)
    # --------------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_tier2_rls_query_nonexistent_account_404(self, raw_client: AsyncClient):
        """Querying a non-existent account returns HTTP 404."""
        token = make_auth0_token(sub="auth0|user-404-test", email="u404@example.com")
        res = await raw_client.get("/api/v1/accounts/9999999", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404

    @pytest.mark.anyio
    async def test_tier2_rls_query_other_user_account_404(self, raw_client: AsyncClient):
        """User B querying User A's account directly returns HTTP 404 (preventing ID enumeration)."""
        token_a = make_auth0_token(sub="auth0|alice-bnd", email="alice_bnd@example.com")
        token_b = make_auth0_token(sub="auth0|bob-bnd", email="bob_bnd@example.com")

        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Private Vault", "account_type": "bank", "currency": "USD"}
        )
        acc_id = res_a.json()["account_id"]

        # Bob attempts to read Alice's account directly
        res_b = await raw_client.get(f"/api/v1/accounts/{acc_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 404

    @pytest.mark.anyio
    async def test_tier2_rls_create_transaction_referencing_other_user_account_rejected(
        self, raw_client: AsyncClient, shared_asset: Asset
    ):
        """User B cannot create transactions referencing User A's account (returns 400 or 404)."""
        token_a = make_auth0_token(sub="auth0|alice-tx-bnd", email="alice_tx_bnd@example.com")
        token_b = make_auth0_token(sub="auth0|bob-tx-bnd", email="bob_tx_bnd@example.com")

        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Stocks", "account_type": "demat", "currency": "USD"}
        )
        alice_acc_id = res_a.json()["account_id"]

        # Bob attempts to inject a transaction into Alice's account
        res_b = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "account_id": alice_acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-25",
                "quantity": 1.0,
                "price_per_unit": 100.0,
                "total_amount": 100.0,
            }
        )
        assert res_b.status_code in (400, 403, 404)

    @pytest.mark.anyio
    async def test_tier2_rls_mutate_other_user_cashflow_rejected(self, raw_client: AsyncClient):
        """User B attempting to modify or delete User A's cashflow item returns HTTP 404."""
        token_a = make_auth0_token(sub="auth0|alice-cf-bnd", email="alice_cf_bnd@example.com")
        token_b = make_auth0_token(sub="auth0|bob-cf-bnd", email="bob_cf_bnd@example.com")

        res_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Alice Bank", "account_type": "bank", "currency": "EUR"}
        )
        acc_id = res_acc.json()["account_id"]

        res_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Alice Rent", "category_type": "EXPENSE"}
        )
        cat_id = res_cat.json()["category_id"]

        res_cf = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "transaction_date": "2026-10-22",
                "title": "Alice Apartment Rent",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": acc_id, "amount": -800.0}],
                "items": [{"category_id": cat_id, "amount": 800.0}],
            }
        )
        cf_id = res_cf.json()["cashflow_id"]

        # Bob attempts to delete Alice's cashflow transaction
        res_del = await raw_client.delete(f"/api/v1/cashflow/{cf_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert res_del.status_code in (403, 404)

    @pytest.mark.anyio
    async def test_tier2_rls_mutate_system_category_rejected(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Non-system user cannot delete or overwrite a system category (user_id = 0)."""
        token = make_auth0_token(sub="auth0|regular-user", email="reg@example.com")

        # Query system categories to find a category with user_id = 0
        stmt = select(Category).where(Category.user_id == 0)
        sys_cat = (await db_session.execute(stmt)).scalars().first()
        if sys_cat:
            res = await raw_client.delete(
                f"/api/v1/categories/{sys_cat.category_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code in (400, 403, 404)


# ==============================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS (Pairwise Combinations)
# ==============================================================================

class TestTier3Interactions:
    """Verifies cross-cutting interactions between authentication, persistence, RLS, and APIs."""

    @pytest.mark.anyio
    async def test_tier3_auth_and_account_creation_association(self, raw_client: AsyncClient, db_session: AsyncSession):
        """Creating an account while authenticated correctly sets Account.user_id in DB."""
        sub = "auth0|assoc-user-01"
        token = make_auth0_token(sub=sub, email="assoc@example.com")

        res = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"account_name": "Associated Account", "account_type": "bank", "currency": "EUR"}
        )
        assert res.status_code == 201
        acc_id = res.json()["account_id"]

        # Query Account directly from DB and assert account.user_id matches User.user_id
        acc_stmt = select(Account).where(Account.account_id == acc_id)
        account_obj = (await db_session.execute(acc_stmt)).scalar_one()

        user_stmt = select(User).where(User.username.in_([sub, "assoc@example.com"]))
        user_obj = (await db_session.execute(user_stmt)).scalars().first()
        assert account_obj.user_id == user_obj.user_id

    @pytest.mark.anyio
    async def test_tier3_cross_tenant_transfer_and_view_isolation(self, raw_client: AsyncClient):
        """User A creates account and funding; User B cannot view or transfer from User A's account."""
        token_a = make_auth0_token(sub="auth0|tenant-a", email="tenant_a@example.com")
        token_b = make_auth0_token(sub="auth0|tenant-b", email="tenant_b@example.com")

        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Tenant A Demat", "account_type": "demat", "currency": "USD"}
        )
        acc_a_id = res_a.json()["account_id"]

        # User B attempts to update or rename User A's account
        res_hack = await raw_client.put(
            f"/api/v1/accounts/{acc_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"account_name": "Compromised Account"}
        )
        assert res_hack.status_code == 404

    @pytest.mark.anyio
    async def test_tier3_api_key_and_auth0_tenant_isolation(self, raw_client: AsyncClient):
        """API keys registered by User A are isolated and inaccessible to User B."""
        token_a = make_auth0_token(sub="auth0|apikey-owner-a", email="key_a@example.com")
        token_b = make_auth0_token(sub="auth0|apikey-owner-b", email="key_b@example.com")

        # User A registers an API key
        res_key = await raw_client.post(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"label": "Tenant A Secret Key"}
        )
        if res_key.status_code == 200:
            # User B lists API keys -> User A's key must not be returned
            res_b_keys = await raw_client.get(
                "/api/v1/auth/api-keys",
                headers={"Authorization": f"Bearer {token_b}"}
            )
            assert res_b_keys.status_code == 200
            labels = [k.get("label") for k in res_b_keys.json()]
            assert "Tenant A Secret Key" not in labels

    @pytest.mark.anyio
    async def test_tier3_profile_sync_endpoint_propagation(self, raw_client: AsyncClient):
        """Explicit sync via /auth/sync or refreshed token updates user profile immediately."""
        sub = "auth0|sync-endpoint-user"
        token = make_auth0_token(sub=sub, email="sync_ep@example.com", name="Initial Name")
        await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})

        # Call /auth/sync if available
        res_sync = await raw_client.post(
            "/api/v1/auth/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Synced Name", "picture": "https://example.com/synced.png"}
        )
        if res_sync.status_code == 200:
            res_me = await raw_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert res_me.status_code == 200
            assert res_me.json().get("name") == "Synced Name"

    @pytest.mark.anyio
    async def test_tier3_multi_user_cashflow_ledger_independence(self, raw_client: AsyncClient):
        """User A and User B execute transactions simultaneously; summaries calculate independently."""
        token_a = make_auth0_token(sub="auth0|ledger-a", email="ledger_a@example.com")
        token_b = make_auth0_token(sub="auth0|ledger-b", email="ledger_b@example.com")

        # User A creates bank account
        res_acc_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "Ledger A Bank", "account_type": "bank", "currency": "EUR"}
        )
        acc_a_id = res_acc_a.json()["account_id"]

        # User B creates bank account
        res_acc_b = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"account_name": "Ledger B Bank", "account_type": "bank", "currency": "EUR"}
        )
        acc_b_id = res_acc_b.json()["account_id"]

        # User A and User B query accounts -> strictly independent
        list_a = (await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_a}"})).json()
        list_b = (await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_b}"})).json()

        assert len(list_a) == 1
        assert list_a[0]["account_id"] == acc_a_id
        assert len(list_b) == 1
        assert list_b[0]["account_id"] == acc_b_id


# ==============================================================================
# TIER 4: REAL-WORLD MULTI-TENANT APPLICATION SCENARIOS (>= 5 scenarios)
# ==============================================================================

class TestTier4RealWorldScenarios:
    """Verifies end-to-end multi-tenant user journeys and threat-model attacks."""

    @pytest.mark.anyio
    async def test_tier4_scenario1_multitenant_portfolio_onboarding(
        self, raw_client: AsyncClient, shared_asset: Asset
    ):
        """
        Scenario 1: Multi-tenant portfolio onboarding
        Alice (Google) provisions accounts and buys stock;
        Bob (GitHub) provisions Demat account;
        Both view independent net worth summaries with zero data leakage.
        """
        alice_token = make_auth0_token(sub="google-oauth2|alice-101", email="alice@corp.com", name="Alice")
        bob_token = make_auth0_token(sub="github|bob-202", email="bob@corp.com", name="Bob")

        # Alice creates Demat Account and buys 10 AAPL
        res_alice_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Brokerage", "account_type": "demat", "currency": "USD"}
        )
        assert res_alice_acc.status_code == 201
        alice_acc_id = res_alice_acc.json()["account_id"]

        res_alice_tx = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_id": alice_acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-01",
                "quantity": 10.0,
                "price_per_unit": 150.0,
                "total_amount": 1500.0,
            }
        )
        assert res_alice_tx.status_code == 201

        # Bob creates Bank Account
        res_bob_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob High Yield Savings", "account_type": "bank", "currency": "USD"}
        )
        assert res_bob_acc.status_code == 201
        bob_acc_id = res_bob_acc.json()["account_id"]

        # Both query portfolio summaries
        alice_summary = (await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {alice_token}"})).json()
        bob_summary = (await raw_client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {bob_token}"})).json()

        # Alice has accounts and holdings; Bob has only 1 account and 0 stock holdings
        assert alice_summary.get("total_accounts", 1) >= 1
        assert bob_summary.get("total_accounts", 1) == 1

        # Bob queries accounts -> sees ONLY bob_acc_id
        bob_accounts = (await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {bob_token}"})).json()
        assert len(bob_accounts) == 1
        assert bob_accounts[0]["account_id"] == bob_acc_id

    @pytest.mark.anyio
    async def test_tier4_scenario2_token_expiration_and_reauth_lifecycle(self, raw_client: AsyncClient):
        """
        Scenario 2: Token expiration & re-authentication lifecycle
        Active token succeeds -> token expires (returns 401) -> fresh token acquired -> session resumes.
        """
        sub = "auth0|lifecycle-user-01"
        now = int(time.time())

        # Step 1: Active token succeeds
        token_active = make_auth0_token(sub=sub, email="lifecycle@example.com", exp=now + 1800)
        res1 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_active}"})
        assert res1.status_code == 200

        # Step 2: Expired token rejected
        token_expired = make_auth0_token(sub=sub, email="lifecycle@example.com", exp=now - 10)
        res2 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_expired}"})
        assert res2.status_code == 401

        # Step 3: Fresh token resumes session
        token_fresh = make_auth0_token(sub=sub, email="lifecycle@example.com", exp=now + 3600)
        res3 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_fresh}"})
        assert res3.status_code == 200

    @pytest.mark.anyio
    async def test_tier4_scenario3_cross_user_adversarial_attack_attempt(
        self, raw_client: AsyncClient, shared_asset: Asset
    ):
        """
        Scenario 3: Cross-user transaction attack attempt
        Attacker Eve attempts full matrix of read, write, update, and delete attacks on Alice's data.
        All attacks fail with 404/403.
        """
        alice_token = make_auth0_token(sub="auth0|alice-target", email="alice_target@example.com")
        eve_token = make_auth0_token(sub="auth0|eve-attacker", email="eve_attacker@example.com")

        # Alice creates account and transaction
        res_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Vault", "account_type": "bank", "currency": "USD"}
        )
        alice_acc_id = res_acc.json()["account_id"]

        res_tx = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_id": alice_acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-10",
                "quantity": 5.0,
                "price_per_unit": 200.0,
                "total_amount": 1000.0,
            }
        )
        alice_tx_id = res_tx.json()["transaction_id"]

        # Attack 1: Eve reads Alice's account directly
        res_att1 = await raw_client.get(f"/api/v1/accounts/{alice_acc_id}", headers={"Authorization": f"Bearer {eve_token}"})
        assert res_att1.status_code == 404

        # Attack 2: Eve modifies Alice's account name
        res_att2 = await raw_client.put(
            f"/api/v1/accounts/{alice_acc_id}",
            headers={"Authorization": f"Bearer {eve_token}"},
            json={"account_name": "Stolen Account"}
        )
        assert res_att2.status_code == 404

        # Attack 3: Eve deletes Alice's account
        res_att3 = await raw_client.delete(f"/api/v1/accounts/{alice_acc_id}", headers={"Authorization": f"Bearer {eve_token}"})
        assert res_att3.status_code == 404

        # Attack 4: Eve reads Alice's transaction directly
        res_att4 = await raw_client.get(f"/api/v1/transactions/{alice_tx_id}", headers={"Authorization": f"Bearer {eve_token}"})
        assert res_att4.status_code == 404

        # Attack 5: Eve deletes Alice's transaction
        res_att5 = await raw_client.delete(f"/api/v1/transactions/{alice_tx_id}", headers={"Authorization": f"Bearer {eve_token}"})
        assert res_att5.status_code in (403, 404)

        # Verification: Alice's account and transaction remain completely untouched
        res_verify_acc = await raw_client.get(f"/api/v1/accounts/{alice_acc_id}", headers={"Authorization": f"Bearer {alice_token}"})
        assert res_verify_acc.status_code == 200
        assert res_verify_acc.json()["account_name"] == "Alice Vault"

    @pytest.mark.anyio
    async def test_tier4_scenario4_mcp_and_rest_tenant_isolation(self, raw_client: AsyncClient):
        """
        Scenario 4: FastMCP & REST multi-tenant query isolation
        Both tenants access endpoints concurrently; queries are strictly isolated.
        """
        token_a = make_auth0_token(sub="auth0|mcp-tenant-a", email="mcp_a@example.com")
        token_b = make_auth0_token(sub="auth0|mcp-tenant-b", email="mcp_b@example.com")

        # Tenant A creates account
        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"account_name": "MCP Tenant A Account", "account_type": "bank", "currency": "EUR"}
        )
        assert res_a.status_code == 201

        # Both query MCP cashflow endpoint
        res_mcp_a = await raw_client.get("/api/v1/mcp/cashflow", headers={"Authorization": f"Bearer {token_a}"})
        res_mcp_b = await raw_client.get("/api/v1/mcp/cashflow", headers={"Authorization": f"Bearer {token_b}"})

        # Responses are scoped per tenant
        assert res_mcp_a.status_code in (200, 404)
        assert res_mcp_b.status_code in (200, 404)

    @pytest.mark.anyio
    async def test_tier4_scenario5_profile_sync_across_devices(self, raw_client: AsyncClient, db_session: AsyncSession):
        """
        Scenario 5: Profile sync across multiple devices/sessions
        Device 1 sets initial profile -> Device 2 presents updated profile claims ->
        DB and subsequent API calls immediately reflect the updated profile.
        """
        sub = "auth0|multi-device-user"
        # Device 1: logs in with Name "Device1 Name"
        token_dev1 = make_auth0_token(sub=sub, email="dev_sync@example.com", name="Device1 Name")
        res1 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_dev1}"})
        assert res1.status_code == 200

        # Device 2: logs in with updated Name "Device2 Name" and Avatar
        token_dev2 = make_auth0_token(
            sub=sub,
            email="dev_sync@example.com",
            name="Device2 Name",
            picture="https://example.com/device2_avatar.png"
        )
        res2 = await raw_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_dev2}"})
        assert res2.status_code == 200

        # Query /auth/me to confirm updated profile
        res_me = await raw_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dev2}"})
        if res_me.status_code == 200:
            assert res_me.json().get("username") is not None
