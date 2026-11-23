import pytest
import datetime
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
import fakeredis.aioredis

from app.db.models import User, Account, Asset, Transaction, CashflowTransaction, CashflowItem, Category, PriceHistory
from app.services import cache_service


@pytest.fixture
def fake_redis():
    """Provides an isolated FakeRedis client for the test."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache_service.set_redis_client(client)
    yield client
    cache_service.set_redis_client(None)


@pytest.mark.anyio
async def test_cache_service_contracts(fake_redis):
    """Direct test of cache_service contract functions."""
    key = "gl:snap:1:acc:all:start:inc"
    assert await cache_service.get_cache(key) is None

    # Set cache with TTL
    await cache_service.set_cache(key, json.dumps({"test": 123}), ttl_seconds=300)
    cached = await cache_service.get_cache(key)
    assert cached is not None
    assert json.loads(cached) == {"test": 123}

    # Set another key for same user and another user
    key_summary = "gl:summary:1:acc:all"
    key_annual = "gl:annual:1:fy:01-01:curr:EUR"
    key_user2 = "gl:snap:2:acc:all:start:inc"
    await cache_service.set_cache(key_summary, json.dumps({"summary": 1}))
    await cache_service.set_cache(key_annual, json.dumps({"annual": 1}))
    await cache_service.set_cache(key_user2, json.dumps({"user2": 1}))

    # Invalidate user 1 snapshot cache
    await cache_service.invalidate_user_snapshot_cache(1)

    assert await cache_service.get_cache(key) is None
    assert await cache_service.get_cache(key_summary) is None
    assert await cache_service.get_cache(key_annual) is None
    # User 2 must still be cached
    assert await cache_service.get_cache(key_user2) is not None

    # Test transaction and cashflow cache invalidation contracts
    tx_key = "gl:tx:1:p:1:s:10"
    cf_key = "gl:cf:1:p:1:s:10"
    await cache_service.set_cache(tx_key, "tx_data")
    await cache_service.set_cache(cf_key, "cf_data")
    await cache_service.invalidate_user_transaction_cache(1)
    assert await cache_service.get_cache(tx_key) is None
    assert await cache_service.get_cache(cf_key) == "cf_data"

    await cache_service.invalidate_user_cashflow_cache(1)
    assert await cache_service.get_cache(cf_key) is None


@pytest.mark.anyio
async def test_snapshot_endpoint_redis_cache_hit_and_miss(fake_redis, auth0_client_user_a):
    """Verify GET /api/v1/snapshots populates Redis and serves subsequent hits from Redis."""
    me_res = await auth0_client_user_a.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    user_id = me_res.json()["user_id"]

    acc_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Checking A",
        "broker_name": "Bank A",
        "account_type": "savings",
        "currency": "EUR"
    })
    assert acc_res.status_code in (200, 201)

    # First request: computes and caches in Redis
    res1 = await auth0_client_user_a.get("/api/v1/snapshots")
    assert res1.status_code == 200
    expected_key = cache_service.get_snapshot_key(user_id, account_id=None, start_date=None)
    cached_val = await fake_redis.get(expected_key)
    assert cached_val is not None, f"Expected key {expected_key} in Redis"

    # Second request: hits Redis cache
    res2 = await auth0_client_user_a.get("/api/v1/snapshots")
    assert res2.status_code == 200
    assert res1.json() == res2.json()

    # Manual invalidation busts the key
    await cache_service.invalidate_user_snapshot_cache(user_id)
    assert await fake_redis.get(expected_key) is None


@pytest.mark.anyio
async def test_portfolio_summary_and_annual_snapshot_caching(fake_redis, auth0_client_user_a):
    """Verify /api/v1/portfolio/summary and /api/v1/portfolio/annual_snapshot cache in Redis."""
    me_res = await auth0_client_user_a.get("/api/v1/auth/me")
    user_id = me_res.json()["user_id"]

    # 1. Portfolio summary
    res_sum1 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_sum1.status_code == 200
    sum_key = cache_service.get_portfolio_summary_key(user_id, account_id=None)
    assert await fake_redis.get(sum_key) is not None

    res_sum2 = await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert res_sum2.status_code == 200
    assert res_sum1.json() == res_sum2.json()

    # 2. Annual snapshot
    res_ann1 = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot?fiscal_year_start=01-01&master_currency=EUR")
    assert res_ann1.status_code == 200
    ann_key = cache_service.get_annual_snapshot_key(user_id, fiscal_year_start="01-01", master_currency="EUR")
    assert await fake_redis.get(ann_key) is not None

    res_ann2 = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot?fiscal_year_start=01-01&master_currency=EUR")
    assert res_ann2.status_code == 200
    assert res_ann1.json() == res_ann2.json()

    # Invalidation busts both
    await cache_service.invalidate_user_snapshot_cache(user_id)
    assert await fake_redis.get(sum_key) is None
    assert await fake_redis.get(ann_key) is None


@pytest.mark.anyio
async def test_crud_invalidation_on_transactions(fake_redis, auth0_client_user_a, test_db_session):
    """Verify transaction POST, PUT, DELETE immediately busts the snapshot cache."""
    session, _ = test_db_session
    me = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    user_id = me["user_id"]

    # Setup account via API
    acc_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Demat Tx",
        "broker_name": "Broker",
        "account_type": "demat",
        "currency": "EUR"
    })
    assert acc_res.status_code in (200, 201)
    acc_id = acc_res.json()["account_id"]

    # Setup asset via API
    ast_res = await auth0_client_user_a.post("/api/v1/assets", json={
        "symbol": "TEST_CACHE_TX",
        "name": "Test Asset",
        "asset_type": "stock",
        "currency": "EUR"
    })
    assert ast_res.status_code in (200, 201)
    ast_id = ast_res.json()["asset_id"]

    # Prime cache
    await auth0_client_user_a.get("/api/v1/snapshots")
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    snap_key = cache_service.get_snapshot_key(user_id)
    sum_key = cache_service.get_portfolio_summary_key(user_id)
    assert await fake_redis.get(snap_key) is not None
    assert await fake_redis.get(sum_key) is not None

    # 1. POST transaction -> should bust cache
    tx_payload = {
        "account_id": acc_id,
        "asset_id": ast_id,
        "transaction_type": "buy",
        "transaction_date": "2025-01-10",
        "quantity": 10.0,
        "price_per_unit": 50.0,
        "total_amount": 500.0,
        "currency": "EUR"
    }
    tx_res = await auth0_client_user_a.post("/api/v1/transactions", json=tx_payload)
    assert tx_res.status_code in (200, 201)
    tx_id = tx_res.json()["transaction_id"]

    assert await fake_redis.get(snap_key) is None, "POST /transactions must bust snapshot cache"
    assert await fake_redis.get(sum_key) is None, "POST /transactions must bust portfolio summary cache"

    # Prime cache again
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # 2. PUT transaction -> should bust cache
    put_payload = dict(tx_payload)
    put_payload["quantity"] = 12.0
    put_payload["total_amount"] = 600.0
    put_res = await auth0_client_user_a.put(f"/api/v1/transactions/{tx_id}", json=put_payload)
    assert put_res.status_code == 200
    assert await fake_redis.get(snap_key) is None, "PUT /transactions must bust snapshot cache"

    # Prime cache again
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # 3. DELETE transaction -> should bust cache
    del_res = await auth0_client_user_a.delete(f"/api/v1/transactions/{tx_id}")
    assert del_res.status_code in (200, 204)
    assert await fake_redis.get(snap_key) is None, "DELETE /transactions must bust snapshot cache"


@pytest.mark.anyio
async def test_crud_invalidation_on_cashflow(fake_redis, auth0_client_user_a, test_db_session):
    """Verify cashflow POST, PUT, DELETE immediately busts the snapshot cache."""
    session, _ = test_db_session
    me = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    user_id = me["user_id"]

    acc = Account(user_id=user_id, account_name="Savings CF", broker_name="Bank CF", account_type="savings", currency="EUR")
    cat = Category(user_id=user_id, name="Salary", category_type="income")
    session.add_all([acc, cat])
    await session.commit()
    await session.refresh(acc)
    await session.refresh(cat)

    # Prime cache
    await auth0_client_user_a.get("/api/v1/snapshots")
    snap_key = cache_service.get_snapshot_key(user_id)
    assert await fake_redis.get(snap_key) is not None

    # 1. POST cashflow
    cf_payload = {
        "title": "Salary Payday",
        "transaction_date": "2025-02-01",
        "currency": "EUR",
        "payments": [{"account_id": acc.account_id, "amount": 3000.0}],
        "items": [{"category_id": cat.category_id, "amount": 3000.0, "description": "Paycheck"}]
    }
    cf_res = await auth0_client_user_a.post("/api/v1/cashflow", json=cf_payload)
    assert cf_res.status_code in (200, 201)
    cf_id = cf_res.json()["cashflow_id"]
    assert await fake_redis.get(snap_key) is None, "POST /cashflow must bust snapshot cache"

    # Prime cache again
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # 2. PUT cashflow
    put_payload = dict(cf_payload)
    put_payload["title"] = "Updated Salary"
    put_res = await auth0_client_user_a.put(f"/api/v1/cashflow/{cf_id}", json=put_payload)
    assert put_res.status_code == 200
    assert await fake_redis.get(snap_key) is None, "PUT /cashflow must bust snapshot cache"

    # Prime cache again
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # 3. DELETE cashflow
    del_res = await auth0_client_user_a.delete(f"/api/v1/cashflow/{cf_id}")
    assert del_res.status_code in (200, 204)
    assert await fake_redis.get(snap_key) is None, "DELETE /cashflow must bust snapshot cache"


@pytest.mark.anyio
async def test_crud_invalidation_on_accounts_and_prices(fake_redis, auth0_client_user_a, test_db_session):
    """Verify account and price mutations invalidate the snapshot cache."""
    session, _ = test_db_session
    me = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    user_id = me["user_id"]

    # Prime cache
    await auth0_client_user_a.get("/api/v1/snapshots")
    snap_key = cache_service.get_snapshot_key(user_id)
    assert await fake_redis.get(snap_key) is not None

    # POST account
    acc_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "New Account",
        "broker_name": "New Broker",
        "account_type": "savings",
        "currency": "EUR"
    })
    assert acc_res.status_code in (200, 201)
    acc_id = acc_res.json()["account_id"]
    assert await fake_redis.get(snap_key) is None, "POST /accounts must bust snapshot cache"

    # Prime cache
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # PUT account
    await auth0_client_user_a.put(f"/api/v1/accounts/{acc_id}", json={
        "account_name": "Updated Account",
        "broker_name": "New Broker",
        "account_type": "savings",
        "currency": "EUR"
    })
    assert await fake_redis.get(snap_key) is None, "PUT /accounts must bust snapshot cache"

    # Prime cache
    await auth0_client_user_a.get("/api/v1/snapshots")
    assert await fake_redis.get(snap_key) is not None

    # DELETE account
    await auth0_client_user_a.delete(f"/api/v1/accounts/{acc_id}")
    assert await fake_redis.get(snap_key) is None, "DELETE /accounts must bust snapshot cache"


@pytest.mark.anyio
async def test_multi_tenant_cache_isolation(fake_redis, auth0_client_user_a, auth0_client_user_b):
    """Verify User A's cache is isolated from User B's cache and invalidations don't cross boundaries."""
    me_a = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    me_b = (await auth0_client_user_b.get("/api/v1/auth/me")).json()
    user_a = me_a["user_id"]
    user_b = me_b["user_id"]
    assert user_a != user_b

    # Prime caches for both users
    await auth0_client_user_a.get("/api/v1/snapshots")
    await auth0_client_user_b.get("/api/v1/snapshots")

    key_a = cache_service.get_snapshot_key(user_a)
    key_b = cache_service.get_snapshot_key(user_b)

    assert await fake_redis.get(key_a) is not None
    assert await fake_redis.get(key_b) is not None

    # Invalidate user A only
    await cache_service.invalidate_user_snapshot_cache(user_a)

    assert await fake_redis.get(key_a) is None, "User A cache must be invalidated"
    assert await fake_redis.get(key_b) is not None, "User B cache must NOT be invalidated"


@pytest.mark.anyio
async def test_graceful_degradation_when_redis_offline(auth0_client_user_a):
    """Verify that when Redis is completely unavailable or raises errors, endpoints continue to work."""
    # Mock a failing Redis client
    failing_client = AsyncMock()
    failing_client.get.side_effect = ConnectionError("Redis is offline")
    failing_client.set.side_effect = ConnectionError("Redis is offline")

    async def failing_scan_iter(match=None, count=None):
        raise ConnectionError("Redis is offline")
        yield

    failing_client.scan_iter = failing_scan_iter
    cache_service.set_redis_client(failing_client)

    try:
        # Endpoints should gracefully degrade and return HTTP 200
        res_snap = await auth0_client_user_a.get("/api/v1/snapshots")
        assert res_snap.status_code == 200

        res_sum = await auth0_client_user_a.get("/api/v1/portfolio/summary")
        assert res_sum.status_code == 200

        res_ann = await auth0_client_user_a.get("/api/v1/portfolio/annual_snapshot")
        assert res_ann.status_code == 200

        # Invalidation must also not raise
        await cache_service.invalidate_user_snapshot_cache(1)
    finally:
        cache_service.set_redis_client(None)
