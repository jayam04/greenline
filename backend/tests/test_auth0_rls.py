"""
Dedicated Auth0 Authentication & Row-Level Security (RLS) Test Suite.

Verifies:
1. Token Verification & Rejection (HTTP 401):
   - Missing Authorization header -> 401
   - Non-Bearer scheme (e.g. Basic) -> 401
   - Malformed token string -> 401
   - Expired token -> 401
   - Invalid RS256 signature / foreign key -> 401
   - Wrong audience or issuer -> 401
   - Unsupported algorithm -> 401
2. User Synchronization & JIT Provisioning:
   - Valid token creates new User record with auth0_sub, email, name, picture.
   - Subsequent requests update existing user record if email/name changes.
   - /api/v1/auth/me returns authenticated user profile.
   - /api/v1/auth/sync updates user profile.
3. Row-Level Security (RLS) Isolation:
   - User A creates accounts, cashflows, and stock trades; User B queries accounts/cashflows/trades and receives 0 records (empty list) or 404 for specific IDs.
   - User B cannot update or delete User A's accounts, transactions, or cashflows (returns 404 or 403).
   - User B cannot create a transaction referencing User A's account (returns 400 or 404).
   - Backup export by User A exports only User A's data; User B exports only User B's data.
   - System default categories (user_id = 0) are accessible to all users.
"""

import time
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Account, Asset, Category, Transaction, CashflowTransaction
from tests.conftest import TEST_KEY_ID, ATTACKER_KEY_ID, ATTACKER_PRIVATE_PEM


# ==============================================================================
# 1. TOKEN VERIFICATION & REJECTION TESTS (HTTP 401)
# ==============================================================================

@pytest.mark.anyio
async def test_missing_authorization_header_rejected(auth0_client_unauthenticated: AsyncClient):
    """Missing Authorization header must return HTTP 401 Unauthorized with WWW-Authenticate."""
    res = await auth0_client_unauthenticated.get("/api/v1/accounts")
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")


@pytest.mark.anyio
async def test_non_bearer_scheme_rejected(auth0_client_unauthenticated: AsyncClient):
    """Non-Bearer auth schemes (e.g. Basic) must be rejected with HTTP 401."""
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")


@pytest.mark.anyio
async def test_malformed_token_rejected(auth0_client_unauthenticated: AsyncClient):
    """Malformed token string must be rejected with HTTP 401."""
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"}
    )
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")


@pytest.mark.anyio
async def test_expired_token_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Expired RS256 token must be rejected with HTTP 401."""
    expired_token = mint_auth0_token(
        sub="auth0|expired-user",
        exp=int(time.time()) - 3600
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")


@pytest.mark.anyio
async def test_untrusted_foreign_key_signature_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Token signed by untrusted foreign key / attacker key must be rejected with HTTP 401."""
    forged_token = mint_auth0_token(
        sub="auth0|attacker-user",
        key=ATTACKER_PRIVATE_PEM,
        kid=ATTACKER_KEY_ID
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {forged_token}"}
    )
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")


@pytest.mark.anyio
async def test_tampered_signature_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Token with tampered signature bytes must be rejected with HTTP 401."""
    tampered_token = mint_auth0_token(
        sub="auth0|tampered-user",
        tampered=True
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert res.status_code == 401


@pytest.mark.anyio
async def test_wrong_audience_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Token with mismatched audience claim must be rejected with HTTP 401."""
    wrong_aud_token = mint_auth0_token(
        sub="auth0|wrong-aud-user",
        aud="https://unauthorized-audience.example.com"
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {wrong_aud_token}"}
    )
    assert res.status_code == 401


@pytest.mark.anyio
async def test_wrong_issuer_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Token with mismatched issuer claim must be rejected with HTTP 401."""
    wrong_iss_token = mint_auth0_token(
        sub="auth0|wrong-iss-user",
        iss="https://evil-issuer.auth0.com/"
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {wrong_iss_token}"}
    )
    assert res.status_code == 401


@pytest.mark.anyio
async def test_unsupported_algorithm_rejected(auth0_client_unauthenticated: AsyncClient, mint_auth0_token):
    """Token with non-RS256 algorithm (e.g. HS256) must be rejected with HTTP 401."""
    hs256_token = mint_auth0_token(
        sub="auth0|hs256-user",
        alg="HS256"
    )
    res = await auth0_client_unauthenticated.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {hs256_token}"}
    )
    assert res.status_code == 401


# ==============================================================================
# 2. USER SYNCHRONIZATION & JIT PROVISIONING TESTS
# ==============================================================================

@pytest.mark.anyio
async def test_jit_user_creation_on_first_request(
    auth0_client_unauthenticated: AsyncClient,
    mint_auth0_token,
    db_session: AsyncSession
):
    """Valid token creates new User record with auth0_sub, email, name, picture."""
    sub = "auth0|jit_new_user_99"
    email = "jit_new_user_99@example.com"
    name = "JIT New User 99"
    picture = "https://example.com/avatar99.png"

    token = mint_auth0_token(sub=sub, email=email, name=name, picture=picture)

    res = await auth0_client_unauthenticated.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["auth0_sub"] == sub
    assert data["email"] == email
    assert data["name"] == name
    assert data["picture"] == picture
    user_id = data["user_id"]
    assert user_id > 0

    # Query DB to confirm real persistence
    stmt = select(User).where(User.auth0_sub == sub)
    db_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert db_user is not None
    assert db_user.user_id == user_id
    assert db_user.email == email
    assert db_user.name == name
    assert db_user.picture == picture


@pytest.mark.anyio
async def test_auth_me_returns_authenticated_profile(auth0_client_user_a: AsyncClient):
    """GET /api/v1/auth/me returns profile of authenticated user."""
    res = await auth0_client_user_a.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["auth0_sub"] == "auth0|user_a"
    assert data["email"] == "user_a@example.com"
    assert data["name"] == "User A"
    assert data["user_id"] > 0


@pytest.mark.anyio
async def test_auth_sync_updates_user_profile(
    auth0_client_user_a: AsyncClient,
    db_session: AsyncSession
):
    """POST /api/v1/auth/sync updates name, email, and picture for current user."""
    # First ensure user A exists
    me_res = await auth0_client_user_a.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    user_id = me_res.json()["user_id"]

    # Call sync endpoint with new profile details
    sync_payload = {
        "name": "User A Updated Name",
        "email": "user_a_updated@example.com",
        "picture": "https://example.com/new_pic.png"
    }
    sync_res = await auth0_client_user_a.post("/api/v1/auth/sync", json=sync_payload)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["name"] == "User A Updated Name"
    assert sync_data["email"] == "user_a_updated@example.com"
    assert sync_data["picture"] == "https://example.com/new_pic.png"

    # Verify DB reflects changes
    stmt = select(User).where(User.user_id == user_id)
    db_user = (await db_session.execute(stmt)).scalar_one()
    assert db_user.name == "User A Updated Name"
    assert db_user.email == "user_a_updated@example.com"
    assert db_user.picture == "https://example.com/new_pic.png"


# ==============================================================================
# 3. ROW-LEVEL SECURITY (RLS) ISOLATION TESTS
# ==============================================================================

@pytest.mark.anyio
async def test_accounts_isolation_between_users(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """User A creates account; User B cannot see, read, update, or delete it."""
    # User A creates an account
    acc_payload = {
        "account_name": "User A Savings",
        "account_type": "bank",
        "currency": "USD"
    }
    create_res = await auth0_client_user_a.post("/api/v1/accounts", json=acc_payload)
    assert create_res.status_code == 201
    acc_a = create_res.json()
    acc_id_a = acc_a["account_id"]

    # User A sees account in list
    list_a = await auth0_client_user_a.get("/api/v1/accounts")
    assert list_a.status_code == 200
    ids_a = [acc["account_id"] for acc in list_a.json()]
    assert acc_id_a in ids_a

    # User B lists accounts: User A's account must NOT be present
    list_b = await auth0_client_user_b.get("/api/v1/accounts")
    assert list_b.status_code == 200
    ids_b = [acc["account_id"] for acc in list_b.json()]
    assert acc_id_a not in ids_b

    # User B attempts to read User A's account -> 404
    get_res = await auth0_client_user_b.get(f"/api/v1/accounts/{acc_id_a}")
    assert get_res.status_code == 404

    # User B attempts to update User A's account -> 404
    update_res = await auth0_client_user_b.put(
        f"/api/v1/accounts/{acc_id_a}",
        json={"account_name": "Hacked Name"}
    )
    assert update_res.status_code == 404

    # User B attempts to delete User A's account -> 404
    delete_res = await auth0_client_user_b.delete(f"/api/v1/accounts/{acc_id_a}")
    assert delete_res.status_code == 404

    # Confirm account was NOT deleted and unchanged
    check_a = await auth0_client_user_a.get(f"/api/v1/accounts/{acc_id_a}")
    assert check_a.status_code == 200
    assert check_a.json()["account_name"] == "User A Savings"


@pytest.mark.anyio
async def test_cashflow_isolation_between_users(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """User A creates cashflow; User B receives 0 records or 404 on access."""
    # User A creates bank account first
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Cash Account", "account_type": "bank", "currency": "USD"}
    )
    assert acc_res.status_code == 201
    acc_id = acc_res.json()["account_id"]

    # User A creates custom category
    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "User A Consulting Cat", "category_type": "INCOME"}
    )
    assert cat_res.status_code == 201
    cat_id = cat_res.json()["category_id"]

    # User A creates cashflow transaction
    cf_payload = {
        "title": "User A Consulting Income",
        "total_amount": 1200.0,
        "currency": "USD",
        "transaction_kind": "INCOME",
        "transaction_date": "2026-11-01",
        "payments": [{"account_id": acc_id, "amount": 1200.0}],
        "items": [{"category_id": cat_id, "amount": 1200.0}]
    }
    create_res = await auth0_client_user_a.post("/api/v1/cashflow", json=cf_payload)
    assert create_res.status_code == 201
    cf_data = create_res.json()
    cf_id = cf_data["cashflow_id"]

    # User A sees it
    res_a = await auth0_client_user_a.get("/api/v1/cashflow")
    assert res_a.status_code == 200
    assert any(c["cashflow_id"] == cf_id for c in res_a.json())

    # User B lists cashflows: receives empty list (0 records)
    res_b = await auth0_client_user_b.get("/api/v1/cashflow")
    assert res_b.status_code == 200
    assert not any(c["cashflow_id"] == cf_id for c in res_b.json())

    # User B attempts to read User A's cashflow -> 404
    get_b = await auth0_client_user_b.get(f"/api/v1/cashflow/{cf_id}")
    assert get_b.status_code == 404

    # User B attempts to delete User A's cashflow -> 404
    del_b = await auth0_client_user_b.delete(f"/api/v1/cashflow/{cf_id}")
    assert del_b.status_code == 404


@pytest.mark.anyio
async def test_cross_user_transaction_referencing_rejected(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient,
    db_session: AsyncSession
):
    """User B cannot create a transaction referencing User A's account."""
    # Ensure asset exists
    stmt = select(Asset).where(Asset.symbol == "MSFT")
    asset = (await db_session.execute(stmt)).scalar_one_or_none()
    if not asset:
        asset = Asset(symbol="MSFT", name="Microsoft Corporation", asset_type="stock", currency="USD")
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

    # User A creates Demat account
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Demat", "account_type": "demat", "currency": "USD"}
    )
    assert acc_res.status_code == 201
    acc_id_a = acc_res.json()["account_id"]

    # User B tries to record trade referencing User A's account -> 400 or 404
    tx_payload = {
        "account_id": acc_id_a,
        "asset_id": asset.asset_id,
        "transaction_type": "buy",
        "quantity": 10.0,
        "price_per_unit": 300.0,
        "total_amount": 3000.0,
        "transaction_date": "2026-11-01",
    }
    tx_res = await auth0_client_user_b.post("/api/v1/transactions", json=tx_payload)
    assert tx_res.status_code in (400, 404)


@pytest.mark.anyio
async def test_stock_transactions_isolation_between_users(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient,
    db_session: AsyncSession
):
    """User A creates a trade on User A's account; User B cannot see, modify, or delete it."""
    # Ensure asset exists
    stmt = select(Asset).where(Asset.symbol == "NVDA")
    asset = (await db_session.execute(stmt)).scalar_one_or_none()
    if not asset:
        asset = Asset(symbol="NVDA", name="NVIDIA Corporation", asset_type="stock", currency="USD")
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

    # User A creates account
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Trading", "account_type": "demat", "currency": "USD"}
    )
    assert acc_res.status_code == 201
    acc_id_a = acc_res.json()["account_id"]

    # User A records trade
    tx_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id_a,
            "asset_id": asset.asset_id,
            "transaction_type": "buy",
            "quantity": 5.0,
            "price_per_unit": 120.0,
            "total_amount": 600.0,
            "transaction_date": "2026-11-01"
        }
    )
    assert tx_res.status_code == 201
    tx_id_a = tx_res.json()["transaction_id"]

    # User B lists transactions: User A's transaction is NOT visible
    list_b = await auth0_client_user_b.get("/api/v1/transactions")
    assert list_b.status_code == 200
    tx_ids_b = [t["transaction_id"] for t in list_b.json()]
    assert tx_id_a not in tx_ids_b

    # User B cannot update User A's transaction -> 404
    put_b = await auth0_client_user_b.put(
        f"/api/v1/transactions/{tx_id_a}",
        json={"quantity": 10.0}
    )
    assert put_b.status_code == 404

    # User B cannot delete User A's transaction -> 404
    del_b = await auth0_client_user_b.delete(f"/api/v1/transactions/{tx_id_a}")
    assert del_b.status_code == 404


@pytest.mark.anyio
async def test_backup_export_data_isolation(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """Backup export by User A exports only User A's data; User B exports only User B's data."""
    # User A creates account
    res_a = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Secret Bank", "account_type": "bank", "currency": "USD"}
    )
    assert res_a.status_code == 201
    acc_id_a = res_a.json()["account_id"]

    # User B creates account
    res_b = await auth0_client_user_b.post(
        "/api/v1/accounts",
        json={"account_name": "User B Separate Demat", "account_type": "demat", "currency": "EUR"}
    )
    assert res_b.status_code == 201
    acc_id_b = res_b.json()["account_id"]

    # User A exports backup
    export_a = await auth0_client_user_a.get("/api/v1/backup/export")
    assert export_a.status_code == 200
    data_a = export_a.json()
    accounts_in_a = [a["account_id"] for a in data_a.get("accounts", [])]
    assert acc_id_a in accounts_in_a
    assert acc_id_b not in accounts_in_a

    # User B exports backup
    export_b = await auth0_client_user_b.get("/api/v1/backup/export")
    assert export_b.status_code == 200
    data_b = export_b.json()
    accounts_in_b = [b["account_id"] for b in data_b.get("accounts", [])]
    assert acc_id_b in accounts_in_b
    assert acc_id_a not in accounts_in_b


@pytest.mark.anyio
async def test_system_default_categories_accessible_to_all_users(
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient,
    db_session: AsyncSession
):
    """System default categories (user_id = 0) are accessible to all users, while custom categories are isolated."""
    # Ensure a system category exists with user_id = 0
    stmt = select(Category).where(Category.user_id == 0)
    sys_cat = (await db_session.execute(stmt)).scalars().first()
    if not sys_cat:
        sys_cat = Category(user_id=0, name="System General", category_type="EXPENSE")
        db_session.add(sys_cat)
        await db_session.commit()
        await db_session.refresh(sys_cat)

    sys_cat_id = sys_cat.category_id

    # User A lists categories -> includes system category
    cats_a_res = await auth0_client_user_a.get("/api/v1/categories")
    assert cats_a_res.status_code == 200
    cats_a_ids = [c["category_id"] for c in cats_a_res.json()]
    assert sys_cat_id in cats_a_ids

    # User B lists categories -> includes system category
    cats_b_res = await auth0_client_user_b.get("/api/v1/categories")
    assert cats_b_res.status_code == 200
    cats_b_ids = [c["category_id"] for c in cats_b_res.json()]
    assert sys_cat_id in cats_b_ids

    # User A creates a custom category
    custom_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "User A Private Category", "category_type": "EXPENSE"}
    )
    assert custom_res.status_code == 201
    custom_cat_id = custom_res.json()["category_id"]

    # User A sees custom category
    res_a_new = await auth0_client_user_a.get("/api/v1/categories")
    assert any(c["category_id"] == custom_cat_id for c in res_a_new.json())

    # User B does NOT see User A's custom category
    res_b_new = await auth0_client_user_b.get("/api/v1/categories")
    assert not any(c["category_id"] == custom_cat_id for c in res_b_new.json())
