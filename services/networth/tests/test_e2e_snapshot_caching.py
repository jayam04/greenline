"""
E2E Test Suite: R1 - Snapshot Caching and Invalidation across /api/v1/snapshots,
/api/v1/portfolio/summary, and /api/v1/portfolio/annual_snapshot.

4-Tier Matrix:
- Tier 1: Feature Coverage (Cache miss, cache hit, multi-user tenant isolation,
          query param differentiation, TTL positive/expiry, graceful fallback)
- Tier 2: Boundary & Corner Cases (Empty portfolio, boundary/future dates,
          invalid account 404 not cached, cross-user forbidden, concurrent requests, unauthenticated 401)
- Tier 3: Cross-Feature Combinations (Cache invalidation on stock buy/sell, delete,
          cashflow CRUD, account CRUD, price update, manual recalculate)
- Tier 4: Real-World Scenarios (Full wealth management lifecycle & multi-user concurrent trading lifecycle)
"""

import json
import asyncio
import datetime
import pytest
from httpx import AsyncClient
from unittest.mock import patch

from app.services import cache_service


@pytest.fixture
def fake_redis(mock_redis_cache):
    """Provides the in-memory fake redis client configured in conftest."""
    return mock_redis_cache


async def get_user_id(client: AsyncClient) -> int:
    """Helper to fetch database user_id for the authenticated client."""
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 200
    return res.json()["user_id"]


async def get_or_create_asset(
    client: AsyncClient,
    symbol: str = "AAPL",
    name: str = "Apple Inc.",
    currency: str = "EUR"
) -> int:
    """Helper to ensure an asset exists via the API, returning its asset_id."""
    res = await client.post(
        "/api/v1/assets",
        json={
            "symbol": symbol,
            "name": name,
            "asset_type": "stock",
            "currency": currency
        }
    )
    if res.status_code == 201:
        return res.json()["asset_id"]

    # Fallback to lookup if already created
    list_res = await client.get("/api/v1/assets")
    if list_res.status_code == 200:
        for a in list_res.json():
            if a["symbol"] == symbol.upper().strip():
                return a["asset_id"]
    raise RuntimeError(f"Could not get or create asset {symbol}: {res.text}")


# ==============================================================================
# TIER 1: FEATURE COVERAGE (6 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_tier1_snapshot_cache_miss_populates_redis(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.1: Cache Miss Populates Redis.
    Verifies that initial requests to snapshot endpoints query the database,
    return 200 OK, and populate the appropriate Redis keys.
    """
    user_a_id = await get_user_id(auth0_client_user_a)

    # Assert Redis keys are absent before queries
    snap_key = cache_service.get_snapshot_key(user_a_id)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    annual_key = cache_service.get_annual_snapshot_key(user_a_id)

    assert await fake_redis.get(snap_key) is None
    assert await fake_redis.get(summary_key) is None
    assert await fake_redis.get(annual_key) is None

    # 1. GET /api/v1/snapshots
    res_snap = await auth0_client_user_a.get("/api/v1/snapshots")
    assert res_snap.status_code == 200
    cached_snap = await fake_redis.get(snap_key)
    assert cached_snap is not None
    assert isinstance(json.loads(cached_snap), list)

    # 2. GET /api/v1/portfolio/summary
    res_sum = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_sum.status_code == 200
    cached_sum = await fake_redis.get(summary_key)
    assert cached_sum is not None
    sum_data = json.loads(cached_sum)
    assert "net_worth" in sum_data or "total_current_value" in sum_data

    # 3. GET /api/v1/portfolio/annual_snapshot
    res_ann = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert res_ann.status_code == 200
    cached_ann = await fake_redis.get(annual_key)
    assert cached_ann is not None
    ann_data = json.loads(cached_ann)
    assert "total_income" in ann_data or "net_worth_delta" in ann_data


@pytest.mark.anyio
async def test_tier1_portfolio_summary_cache_hit_returns_cached_data(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.2: Cache Hit Returns Cached String.
    Proves that subsequent requests serve data directly from Redis by mutating
    the cached payload in Redis and verifying the second HTTP GET returns the mutated value.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)

    # Initial request populates cache
    res1 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res1.status_code == 200
    cached_raw = await fake_redis.get(summary_key)
    assert cached_raw is not None

    # Tamper with the cached JSON string in Redis
    cached_data = json.loads(cached_raw)
    sentinel_val = 987654.32
    cached_data["total_current_value"] = sentinel_val
    await fake_redis.set(summary_key, json.dumps(cached_data))

    # Second request must return the exact tampered cached data, proving DB was bypassed
    res2 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res2.status_code == 200
    assert res2.json()["total_current_value"] == sentinel_val


@pytest.mark.anyio
async def test_tier1_annual_snapshot_cache_hit_returns_cached_data(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.3: Annual Snapshot Cache Hit.
    Verifies that /api/v1/portfolio/annual_snapshot serves cached data from Redis.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    annual_key = cache_service.get_annual_snapshot_key(user_a_id, fiscal_year_start="01-01", master_currency="EUR")

    res1 = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert res1.status_code == 200

    cached_raw = await fake_redis.get(annual_key)
    assert cached_raw is not None

    # Tamper cached annual snapshot
    cached_data = json.loads(cached_raw)
    sentinel_income = 55555.55
    cached_data["total_income"] = sentinel_income
    await fake_redis.set(annual_key, json.dumps(cached_data))

    res2 = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert res2.status_code == 200
    assert res2.json()["total_income"] == sentinel_income


@pytest.mark.anyio
async def test_tier1_multi_user_tenant_cache_isolation(
    fake_redis,
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """
    Tier 1.4: Multi-User Tenant Cache Isolation.
    Asserts User A and User B cache keys are strictly partitioned by user_id.
    Invalidating User A's cache must leave User B's cache entries intact.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    user_b_id = await get_user_id(auth0_client_user_b)
    assert user_a_id != user_b_id

    # Populate both caches
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    await auth0_client_user_b.get("/api/v1/portfolio/summary")

    key_a = cache_service.get_portfolio_summary_key(user_a_id)
    key_b = cache_service.get_portfolio_summary_key(user_b_id)

    assert await fake_redis.get(key_a) is not None
    assert await fake_redis.get(key_b) is not None

    # Invalidate User A
    await cache_service.invalidate_user_snapshot_cache(user_a_id)

    # Verify User A's key is deleted while User B's key is completely untouched
    assert await fake_redis.get(key_a) is None
    assert await fake_redis.get(key_b) is not None


@pytest.mark.anyio
async def test_tier1_query_parameter_differentiation(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.5: Query Parameter Differentiation.
    Verifies that distinct query parameters (account_id, start_date, fiscal_year_start, currency)
    produce distinct Redis cache keys without key collisions.
    """
    # Create two distinct accounts
    acc1_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 1 Acc 1", "account_type": "demat", "currency": "EUR"}
    )
    acc1_id = acc1_res.json()["account_id"]

    acc2_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 1 Acc 2", "account_type": "demat", "currency": "EUR"}
    )
    acc2_id = acc2_res.json()["account_id"]

    # 1. Snapshots with different account_ids and overall
    await auth0_client_user_a.get("/api/v1/snapshots")
    await auth0_client_user_a.get(f"/api/v1/snapshots?account_id={acc1_id}")
    await auth0_client_user_a.get(f"/api/v1/snapshots?account_id={acc2_id}")

    user_a_id = await get_user_id(auth0_client_user_a)
    key_all = cache_service.get_snapshot_key(user_a_id)
    key_acc1 = cache_service.get_snapshot_key(user_a_id, account_id=acc1_id)
    key_acc2 = cache_service.get_snapshot_key(user_a_id, account_id=acc2_id)

    assert key_all != key_acc1 != key_acc2
    assert await fake_redis.get(key_all) is not None
    assert await fake_redis.get(key_acc1) is not None
    assert await fake_redis.get(key_acc2) is not None

    # 2. Annual snapshots with different parameters
    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot?fiscal_year_start=01-01&master_currency=EUR")
    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot?fiscal_year_start=04-01&master_currency=USD")

    key_fy_eur = cache_service.get_annual_snapshot_key(user_a_id, "01-01", "EUR")
    key_fy_usd = cache_service.get_annual_snapshot_key(user_a_id, "04-01", "USD")

    assert key_fy_eur != key_fy_usd
    assert await fake_redis.get(key_fy_eur) is not None
    assert await fake_redis.get(key_fy_usd) is not None


@pytest.mark.anyio
async def test_tier1_redis_ttl_expiry_and_graceful_fallback(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.6: Redis TTL Expiry and Graceful Fallback.
    Asserts cached keys have positive TTL (<= 300s). Simulates Redis failure
    and verifies the endpoint gracefully falls back to database recomputation without throwing 500.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)

    res = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res.status_code == 200

    ttl = await fake_redis.ttl(summary_key)
    assert 0 < ttl <= 300

    # Simulate Redis connection failure inside fake_redis.get (which cache_service catches and falls back to None)
    with patch.object(fake_redis, "get", side_effect=Exception("Redis Cluster Connection Refused")):
        res_fallback = await auth0_client_user_a.get("/api/v1/portfolio/summary")
        assert res_fallback.status_code == 200
        assert "net_worth" in res_fallback.json() or "total_current_value" in res_fallback.json()


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (6 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_tier2_empty_portfolio_caching(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.1: Empty Portfolio Caching.
    Verifies that a user with 0 accounts, 0 transactions, and 0 cashflows
    receives 200 OK with empty/zero payloads that are cached and deserialized cleanly.
    """
    user_a_id = await get_user_id(auth0_client_user_a)

    res_sum = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum.get("total_current_value", 0.0) == 0.0
    assert data_sum.get("top_holdings", []) == []

    # Verify cached
    sum_key = cache_service.get_portfolio_summary_key(user_a_id)
    assert await fake_redis.get(sum_key) is not None

    # Repeat GET succeeds via cache
    res_sum2 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_sum2.status_code == 200
    assert res_sum.json() == res_sum2.json()


@pytest.mark.anyio
async def test_tier2_date_boundaries_and_future_dates(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.2: Date Boundaries and Future Dates.
    Queries /api/v1/snapshots with a future date (2099-01-01), verifying empty
    list response, 200 OK status, and correct caching of empty results.
    """
    user_a_id = await get_user_id(auth0_client_user_a)

    future_date = "2099-01-01"
    res = await auth0_client_user_a.get(f"/api/v1/snapshots?start_date={future_date}")
    assert res.status_code == 200
    assert res.json() == []

    key = cache_service.get_snapshot_key(user_a_id, start_date=future_date)
    cached = await fake_redis.get(key)
    assert cached is not None
    assert json.loads(cached) == []


@pytest.mark.anyio
async def test_tier2_invalid_account_id_not_cached_as_hit(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.3: Non-existent Account 404 is Not Cached.
    Queries /api/v1/snapshots with invalid account_id 999999.
    Verifies 404 Not Found and ensures no invalid cache key was created in Redis.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    invalid_acc_id = 999999

    res = await auth0_client_user_a.get(f"/api/v1/snapshots?account_id={invalid_acc_id}")
    assert res.status_code == 404

    key = cache_service.get_snapshot_key(user_a_id, account_id=invalid_acc_id)
    assert await fake_redis.get(key) is None


@pytest.mark.anyio
async def test_tier2_cross_user_account_access_forbidden_and_not_cached(
    fake_redis,
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """
    Tier 2.4: Cross-User Account Access Denied and Not Cached.
    User B creates an account. User A attempts to query snapshots for User B's account.
    Asserts 404 Not Found and verifies no cross-tenant cache entry is created.
    """
    acc_b_res = await auth0_client_user_b.post(
        "/api/v1/accounts",
        json={"account_name": "User B Secret Demat", "account_type": "demat", "currency": "EUR"}
    )
    assert acc_b_res.status_code == 201
    acc_b_id = acc_b_res.json()["account_id"]

    # User A tries to access User B's account snapshots
    res_a = await auth0_client_user_a.get(f"/api/v1/snapshots?account_id={acc_b_id}")
    assert res_a.status_code == 404

    user_a_id = await get_user_id(auth0_client_user_a)
    key_a_cross = cache_service.get_snapshot_key(user_a_id, account_id=acc_b_id)
    assert await fake_redis.get(key_a_cross) is None


@pytest.mark.anyio
async def test_tier2_concurrent_requests_consistency(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.5: Concurrent Requests Consistency.
    Dispatches 5 concurrent GET requests to /api/v1/portfolio/summary via asyncio.gather.
    Asserts all 5 return 200 OK with identical JSON bodies and no corrupted cache states.
    """
    responses = await asyncio.gather(
        auth0_client_user_a.get("/api/v1/portfolio/summary"),
        auth0_client_user_a.get("/api/v1/portfolio/summary"),
        auth0_client_user_a.get("/api/v1/portfolio/summary"),
        auth0_client_user_a.get("/api/v1/portfolio/summary"),
        auth0_client_user_a.get("/api/v1/portfolio/summary")
    )

    for r in responses:
        assert r.status_code == 200

    base_body = responses[0].json()
    for r in responses[1:]:
        assert r.json() == base_body


@pytest.mark.anyio
async def test_tier2_unauthenticated_request_handling(
    fake_redis,
    auth0_client_unauthenticated: AsyncClient
):
    """
    Tier 2.6: Unauthenticated Request Handling.
    Requests without Bearer token must return 401 Unauthorized and write zero Redis keys.
    """
    keys_before = await fake_redis.keys("*")

    res_snap = await auth0_client_unauthenticated.get("/api/v1/snapshots")
    assert res_snap.status_code == 401

    res_sum = await auth0_client_unauthenticated.get("/api/v1/portfolio/summary")
    assert res_sum.status_code == 401

    res_ann = await auth0_client_unauthenticated.get("/api/v1/portfolio/annual_snapshot")
    assert res_ann.status_code == 401

    keys_after = await fake_redis.keys("*")
    assert keys_before == keys_after


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (Cache Invalidation on CRUD) (6 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_tier3_stock_buy_sell_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.1: Stock Buy and Sell Invalidate Snapshot Caches.
    1. Query /portfolio/summary -> populates Redis.
    2. POST /transactions (buy) -> asserts Redis summary/snapshot keys deleted.
    3. Subsequent GET /portfolio/summary recomputes with updated holdings and re-caches.
    4. POST /transactions (sell) -> asserts cache deleted again.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="T3_BUY", name="Tier 3 Buy Asset", currency="EUR")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 3 Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    # Step 1: Establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    assert await fake_redis.get(summary_key) is not None

    # Step 2: Buy 10 shares
    buy_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 10.0,
            "price_per_unit": 100.0,
            "total_amount": 1000.0,
            "transaction_date": "2026-11-01"
        }
    )
    assert buy_res.status_code == 201

    # Step 3: Assert cache was invalidated
    assert await fake_redis.get(summary_key) is None

    # Re-cache via GET
    res_after_buy = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_after_buy.status_code == 200
    assert await fake_redis.get(summary_key) is not None

    # Step 4: Sell 5 shares
    sell_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "asset_id": asset_id,
            "transaction_type": "sell",
            "quantity": 5.0,
            "price_per_unit": 120.0,
            "total_amount": 600.0,
            "transaction_date": "2026-11-02"
        }
    )
    assert sell_res.status_code == 201

    # Assert cache invalidated again
    assert await fake_redis.get(summary_key) is None


@pytest.mark.anyio
async def test_tier3_stock_transaction_delete_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.2: Stock Transaction Deletion Invalidates Snapshot Caches.
    User creates a trade, establishes cache, deletes the trade via DELETE /transactions/{id},
    and verifies Redis cache is deleted.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="T3_DEL", name="Tier 3 Del Asset", currency="EUR")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 3 Del Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    tx_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 10.0,
            "price_per_unit": 50.0,
            "total_amount": 500.0,
            "transaction_date": "2026-11-01"
        }
    )
    tx_id = tx_res.json()["transaction_id"]

    # Establish cache
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(summary_key) is not None

    # Delete transaction
    del_res = await auth0_client_user_a.delete(f"/api/v1/transactions/{tx_id}")
    assert del_res.status_code == 204

    # Assert cache invalidated
    assert await fake_redis.get(summary_key) is None


@pytest.mark.anyio
async def test_tier3_cashflow_income_expense_crud_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.3: Cashflow CRUD Invalidates Annual Snapshot and Snapshot Caches.
    POST, PUT, and DELETE on /api/v1/cashflow must synchronously purge user snapshot caches.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    annual_key = cache_service.get_annual_snapshot_key(user_a_id)

    # Create account & category
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 3 Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Tier 3 Expense Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    # 1. Establish annual snapshot cache
    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert await fake_redis.get(annual_key) is not None

    # 2. POST cashflow expense -> asserts cache invalidated
    cf_res = await auth0_client_user_a.post(
        "/api/v1/cashflow",
        json={
            "title": "Groceries Run",
            "total_amount": 150.0,
            "currency": "EUR",
            "transaction_kind": "EXPENSE",
            "transaction_date": "2026-11-05",
            "payments": [{"account_id": acc_id, "amount": 150.0}],
            "items": [{"category_id": cat_id, "amount": 150.0}]
        }
    )
    assert cf_res.status_code == 201
    cf_id = cf_res.json()["cashflow_id"]
    assert await fake_redis.get(annual_key) is None

    # Re-establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert await fake_redis.get(annual_key) is not None

    # 3. PUT cashflow expense -> asserts cache invalidated
    put_res = await auth0_client_user_a.put(
        f"/api/v1/cashflow/{cf_id}",
        json={
            "title": "Groceries Run Updated",
            "total_amount": 180.0,
            "currency": "EUR",
            "transaction_kind": "EXPENSE",
            "transaction_date": "2026-11-05",
            "payments": [{"account_id": acc_id, "amount": 180.0}],
            "items": [{"category_id": cat_id, "amount": 180.0}]
        }
    )
    assert put_res.status_code == 200
    assert await fake_redis.get(annual_key) is None

    # Re-establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert await fake_redis.get(annual_key) is not None

    # 4. DELETE cashflow expense -> asserts cache invalidated
    del_res = await auth0_client_user_a.delete(f"/api/v1/cashflow/{cf_id}")
    assert del_res.status_code == 204
    assert await fake_redis.get(annual_key) is None


@pytest.mark.anyio
async def test_tier3_account_creation_and_update_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.4: Account CRUD Invalidates Snapshot Cache.
    Creating, updating, and deleting accounts triggers cache invalidation.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)

    # Establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(summary_key) is not None

    # Create account -> cache invalidated
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "New Savings", "account_type": "bank", "currency": "EUR"}
    )
    assert acc_res.status_code == 201
    acc_id = acc_res.json()["account_id"]
    assert await fake_redis.get(summary_key) is None

    # Re-establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(summary_key) is not None

    # Update account -> cache invalidated
    up_res = await auth0_client_user_a.put(
        f"/api/v1/accounts/{acc_id}",
        json={"account_name": "Updated Savings"}
    )
    assert up_res.status_code == 200
    assert await fake_redis.get(summary_key) is None

    # Re-establish cache
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(summary_key) is not None

    # Delete account -> cache invalidated
    del_res = await auth0_client_user_a.delete(f"/api/v1/accounts/{acc_id}")
    assert del_res.status_code == 204
    assert await fake_redis.get(summary_key) is None


@pytest.mark.anyio
async def test_tier3_asset_price_update_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.5: Asset Price Update Invalidates Snapshot Cache.
    When a price update occurs via POST /api/v1/prices/, user snapshot and
    portfolio summary caches are deleted so subsequent valuations reflect current market value.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="T3_PRICE", name="Tier 3 Price Asset", currency="EUR")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Tier 3 Price Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 10.0,
            "price_per_unit": 100.0,
            "total_amount": 1000.0,
            "transaction_date": "2026-11-01"
        }
    )

    # Establish cache
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(summary_key) is not None

    # Add updated price: 150.0 EUR
    price_res = await auth0_client_user_a.post(
        "/api/v1/prices/",
        json={
            "asset_id": asset_id,
            "price_date": "2026-11-10",
            "close_price": 150.0,
            "currency": "EUR"
        }
    )
    assert price_res.status_code == 201

    # Assert summary cache invalidated
    assert await fake_redis.get(summary_key) is None

    # Subsequent GET recomputes with new valuation (10 * 150 = 1500 EUR)
    res_summary = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_summary.status_code == 200
    assert res_summary.json()["total_current_value"] == 1500.0


@pytest.mark.anyio
async def test_tier3_manual_trigger_recalculate_invalidates_snapshot_cache(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.6: Manual Trigger Recalculate Invalidates Snapshot Cache.
    Calling POST /api/v1/snapshots/trigger-recalculate synchronously deletes
    all snapshot and portfolio caches for the authenticated user.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    snap_key = cache_service.get_snapshot_key(user_a_id)

    # Establish caches
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(summary_key) is not None
    assert await fake_redis.get(snap_key) is not None

    # Trigger recalculate
    recalc_res = await auth0_client_user_a.post(
        "/api/v1/snapshots/trigger-recalculate",
        json={"user_id": user_a_id, "start_date": "2026-01-01", "reason": "manual_e2e_test"}
    )
    assert recalc_res.status_code == 202

    # Assert both caches are cleared
    assert await fake_redis.get(summary_key) is None
    assert await fake_redis.get(snap_key) is None


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS (2 Comprehensive Journeys)
# ==============================================================================

@pytest.mark.anyio
async def test_tier4_full_wealth_management_lifecycle(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 4.1: Full Wealth Management Lifecycle.
    End-to-end journey covering:
    1. User onboarding & Demat setup -> initial summary cached (0 net worth).
    2. Cash deposit -> cache invalidated -> subsequent read verifies cash and re-caches.
    3. Cache hit verification -> repeat read serves from Redis.
    4. Stock buy -> cache invalidated -> read verifies 10 shares and 1000 EUR valuation.
    5. Price surge -> cache invalidated -> read verifies 1500 EUR valuation & unrealized gain.
    6. Stock sell (half) -> cache invalidated -> read verifies realized gain & 5 shares remaining.
    7. Salary income and rent expense -> annual snapshot invalidated -> read verifies delta.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    summary_key = cache_service.get_portfolio_summary_key(user_a_id)
    annual_key = cache_service.get_annual_snapshot_key(user_a_id)

    # 1. Onboard Demat & Bank Accounts
    demat_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Lifecycle Demat", "account_type": "demat", "currency": "EUR"}
    )
    assert demat_res.status_code == 201
    demat_id = demat_res.json()["account_id"]

    bank_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Lifecycle Bank", "account_type": "bank", "currency": "EUR"}
    )
    assert bank_res.status_code == 201
    bank_id = bank_res.json()["account_id"]

    initial_sum = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert initial_sum.status_code == 200
    assert initial_sum.json()["total_current_value"] == 0.0
    assert await fake_redis.get(summary_key) is not None

    # 2. Deposit Cash via Cashflow (Income: 5000 EUR)
    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Lifecycle Salary", "category_type": "INCOME"}
    )
    assert cat_res.status_code == 201
    salary_cat_id = cat_res.json()["category_id"]

    dep_res = await auth0_client_user_a.post(
        "/api/v1/cashflow",
        json={
            "title": "Initial Capital Deposit",
            "total_amount": 5000.0,
            "currency": "EUR",
            "transaction_kind": "INCOME",
            "transaction_date": "2026-11-01",
            "payments": [{"account_id": bank_id, "amount": 5000.0}],
            "items": [{"category_id": salary_cat_id, "amount": 5000.0}]
        }
    )
    assert dep_res.status_code == 201
    assert await fake_redis.get(summary_key) is None

    # 3. Read summary & verify cache hit
    sum_after_dep = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert sum_after_dep.status_code == 200
    assert await fake_redis.get(summary_key) is not None

    # 4. Buy 10 shares of AAPL @ 100 EUR
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="LC_AAPL", name="Lifecycle Apple", currency="EUR")
    buy_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": demat_id,
            "funding_account_id": bank_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 10.0,
            "price_per_unit": 100.0,
            "total_amount": 1000.0,
            "transaction_date": "2026-11-02"
        }
    )
    assert buy_res.status_code == 201
    assert await fake_redis.get(summary_key) is None

    sum_after_buy = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert sum_after_buy.status_code == 200
    assert sum_after_buy.json()["total_current_value"] == 1000.0
    assert len(sum_after_buy.json()["top_holdings"]) == 1

    # 5. Price surge to 150 EUR
    price_res = await auth0_client_user_a.post(
        "/api/v1/prices/",
        json={
            "asset_id": asset_id,
            "price_date": "2026-11-03",
            "close_price": 150.0,
            "currency": "EUR"
        }
    )
    assert price_res.status_code == 201
    assert await fake_redis.get(summary_key) is None

    sum_after_surge = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert sum_after_surge.status_code == 200
    assert sum_after_surge.json()["total_current_value"] == 1500.0
    assert sum_after_surge.json()["total_unrealized_pnl"] == 500.0

    # 6. Sell 5 shares @ 150 EUR
    sell_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": demat_id,
            "funding_account_id": bank_id,
            "asset_id": asset_id,
            "transaction_type": "sell",
            "quantity": 5.0,
            "price_per_unit": 150.0,
            "total_amount": 750.0,
            "transaction_date": "2026-11-04"
        }
    )
    assert sell_res.status_code == 201
    assert await fake_redis.get(summary_key) is None

    sum_after_sell = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert sum_after_sell.status_code == 200
    assert sum_after_sell.json()["total_current_value"] == 750.0
    assert sum_after_sell.json()["total_realized_pnl"] == 250.0

    # 7. Add expense & check annual snapshot
    rent_cat = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Lifecycle Rent", "category_type": "EXPENSE"}
    )
    assert rent_cat.status_code == 201
    rent_cat_id = rent_cat.json()["category_id"]

    await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert await fake_redis.get(annual_key) is not None

    rent_res = await auth0_client_user_a.post(
        "/api/v1/cashflow",
        json={
            "title": "Apartment Rent",
            "total_amount": 1000.0,
            "currency": "EUR",
            "transaction_kind": "EXPENSE",
            "transaction_date": "2026-11-05",
            "payments": [{"account_id": bank_id, "amount": 1000.0}],
            "items": [{"category_id": rent_cat_id, "amount": 1000.0}]
        }
    )
    assert rent_res.status_code == 201
    assert await fake_redis.get(annual_key) is None

    annual_final = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
    assert annual_final.status_code == 200
    assert annual_final.json()["total_income"] == 5000.0
    assert annual_final.json()["total_expenses"] == 1000.0


@pytest.mark.anyio
async def test_tier4_multi_user_concurrent_trading_and_caching_lifecycle(
    fake_redis,
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """
    Tier 4.2: Multi-User Concurrent Trading and Caching Lifecycle.
    Verifies that User A and User B concurrently operate on their portfolios:
    - Both establish independent caches.
    - User A trades -> only User A's cache is invalidated. User B's cache is preserved.
    - User B adds an expense -> only User B's cache is invalidated. User A's cache is preserved.
    - Both users read their summaries and receive accurate, tenant-isolated valuations.
    """
    user_a_id = await get_user_id(auth0_client_user_a)
    user_b_id = await get_user_id(auth0_client_user_b)

    key_sum_a = cache_service.get_portfolio_summary_key(user_a_id)
    key_sum_b = cache_service.get_portfolio_summary_key(user_b_id)

    # 1. Accounts setup
    acc_a = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Trading", "account_type": "demat", "currency": "EUR"}
    )
    acc_a_id = acc_a.json()["account_id"]

    acc_b = await auth0_client_user_b.post(
        "/api/v1/accounts",
        json={"account_name": "User B Trading", "account_type": "demat", "currency": "EUR"}
    )
    acc_b_id = acc_b.json()["account_id"]

    # 2. Both establish summary caches
    res_a1 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    res_b1 = await auth0_client_user_b.get("/api/v1/portfolio/summary")
    assert res_a1.status_code == 200
    assert res_b1.status_code == 200

    assert await fake_redis.get(key_sum_a) is not None
    assert await fake_redis.get(key_sum_b) is not None

    # 3. User A buys shares
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="CONCUR_ASSET", name="Concurrent Asset", currency="EUR")
    await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_a_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 20.0,
            "price_per_unit": 50.0,
            "total_amount": 1000.0,
            "transaction_date": "2026-11-01"
        }
    )

    # Assert User A cache is invalidated, User B cache remains intact
    assert await fake_redis.get(key_sum_a) is None
    assert await fake_redis.get(key_sum_b) is not None

    # 4. User A re-establishes cache
    res_a2 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_a2.status_code == 200
    assert res_a2.json()["total_current_value"] == 1000.0
    assert await fake_redis.get(key_sum_a) is not None

    # 5. User B adds an expense via cashflow
    cat_b = await auth0_client_user_b.post(
        "/api/v1/categories",
        json={"name": "User B Software", "category_type": "EXPENSE"}
    )
    cat_b_id = cat_b.json()["category_id"]

    await auth0_client_user_b.post(
        "/api/v1/cashflow",
        json={
            "title": "IDE Subscription",
            "total_amount": 30.0,
            "currency": "EUR",
            "transaction_kind": "EXPENSE",
            "transaction_date": "2026-11-02",
            "payments": [{"account_id": acc_b_id, "amount": 30.0}],
            "items": [{"category_id": cat_b_id, "amount": 30.0}]
        }
    )

    # Assert User B cache is invalidated, User A cache remains intact
    assert await fake_redis.get(key_sum_b) is None
    assert await fake_redis.get(key_sum_a) is not None

    # Final check: both users query summaries
    res_a_final = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    res_b_final = await auth0_client_user_b.get("/api/v1/portfolio/summary")

    assert res_a_final.json()["total_current_value"] == 1000.0
    assert res_b_final.json()["total_current_value"] == 0.0
