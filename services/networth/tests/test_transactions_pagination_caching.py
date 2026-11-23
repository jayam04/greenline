import pytest
import datetime
import json
from unittest.mock import AsyncMock

from app.services import cache_service


@pytest.mark.anyio
async def test_pagination_schemas():
    """Verify PaginatedTransactionResponse and PaginatedCashflowResponse schema contracts."""
    from app.schemas.schemas import (
        PaginatedTransactionResponse,
        PaginatedCashflowResponse,
        TransactionResponse,
        CashflowTransactionResponse,
    )

    tx_resp = TransactionResponse(
        transaction_id=1,
        account_id=10,
        asset_id=20,
        transaction_type="buy",
        transaction_date=datetime.date(2025, 1, 15),
        quantity=5.0,
        price_per_unit=100.0,
        total_amount=500.0,
        fees=1.0,
        taxes=0.5,
        currency="USD",
        source="manual",
    )

    p_tx = PaginatedTransactionResponse(
        items=[tx_resp],
        total=15,
        page=2,
        page_size=5,
        total_pages=3,
        has_more=True,
    )

    assert p_tx.total == 15
    assert p_tx.total_count == 15
    assert p_tx.page == 2
    assert p_tx.page_size == 5
    assert p_tx.total_pages == 3
    assert p_tx.has_more is True
    assert p_tx.has_next is True
    assert p_tx.has_prev is True
    assert len(p_tx.items) == 1

    cf_resp = CashflowTransactionResponse(
        cashflow_id=1,
        transaction_date=datetime.date(2025, 2, 1),
        title="Salary",
        total_amount=3000.0,
        currency="EUR",
        created_at=datetime.datetime(2025, 2, 1, 10, 0, 0),
        payments=[],
        items=[],
    )

    p_cf = PaginatedCashflowResponse(
        items=[cf_resp],
        total=1,
        page=1,
        page_size=10,
        total_pages=1,
        has_more=False,
    )

    assert p_cf.total == 1
    assert p_cf.total_count == 1
    assert p_cf.page == 1
    assert p_cf.page_size == 10
    assert p_cf.total_pages == 1
    assert p_cf.has_more is False
    assert p_cf.has_next is False
    assert p_cf.has_prev is False
    assert len(p_cf.items) == 1


@pytest.mark.anyio
async def test_stock_transactions_unpaginated_backward_compatibility(auth0_client_user_a):
    """
    Verify GET /api/v1/transactions without page query parameter returns a plain list
    and includes pagination headers.
    """
    res = await auth0_client_user_a.get("/api/v1/transactions")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list), "Unpaginated transactions request must return a plain list"
    assert "X-Total-Count" in res.headers
    assert "X-Total-Pages" in res.headers
    assert "X-Page" in res.headers
    assert "X-Page-Size" in res.headers


@pytest.mark.anyio
async def test_stock_transactions_pagination_and_filtering(auth0_client_user_a):
    """
    Verify GET /api/v1/transactions?page=X&page_size=Y returns paginated response,
    correct slicing, and pushdown filtering by account_id and asset_id.
    """
    # 1. Setup accounts
    acc1_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Demat Pagination 1",
        "broker_name": "Broker A",
        "account_type": "demat",
        "currency": "EUR"
    })
    acc1_id = acc1_res.json()["account_id"]

    acc2_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Demat Pagination 2",
        "broker_name": "Broker B",
        "account_type": "demat",
        "currency": "EUR"
    })
    acc2_id = acc2_res.json()["account_id"]

    # 2. Setup assets
    ast1_res = await auth0_client_user_a.post("/api/v1/assets", json={
        "symbol": "PAG_ASSET_1",
        "name": "Paginated Asset 1",
        "asset_type": "stock",
        "currency": "EUR"
    })
    ast1_id = ast1_res.json()["asset_id"]

    ast2_res = await auth0_client_user_a.post("/api/v1/assets", json={
        "symbol": "PAG_ASSET_2",
        "name": "Paginated Asset 2",
        "asset_type": "stock",
        "currency": "EUR"
    })
    ast2_id = ast2_res.json()["asset_id"]

    # 3. Create 5 transactions:
    # tx1: acc1, ast1, 2025-01-01
    # tx2: acc1, ast1, 2025-01-02
    # tx3: acc1, ast2, 2025-01-03
    # tx4: acc2, ast2, 2025-01-04
    # tx5: acc2, ast1, 2025-01-05
    for i, (acc, ast) in enumerate([(acc1_id, ast1_id), (acc1_id, ast1_id), (acc1_id, ast2_id), (acc2_id, ast2_id), (acc2_id, ast1_id)], start=1):
        r = await auth0_client_user_a.post("/api/v1/transactions", json={
            "account_id": acc,
            "asset_id": ast,
            "transaction_type": "buy",
            "transaction_date": f"2025-01-0{i}",
            "quantity": 10.0,
            "price_per_unit": 20.0,
            "total_amount": 200.0,
            "currency": "EUR"
        })
        assert r.status_code in (200, 201)

    # Page 1 with page_size=2
    res_p1 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=2")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert isinstance(data_p1, dict)
    assert data_p1["total"] == 5
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 2
    assert data_p1["total_pages"] == 3
    assert data_p1["has_more"] is True
    assert data_p1["has_next"] is True
    assert data_p1["has_prev"] is False
    assert len(data_p1["items"]) == 2
    # Check descending order: newest first (2025-01-05, 2025-01-04)
    assert data_p1["items"][0]["transaction_date"] == "2025-01-05"
    assert data_p1["items"][1]["transaction_date"] == "2025-01-04"

    # Page 2 with page_size=2
    res_p2 = await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["page"] == 2
    assert len(data_p2["items"]) == 2
    assert data_p2["has_more"] is True
    assert data_p2["has_prev"] is True
    assert data_p2["items"][0]["transaction_date"] == "2025-01-03"
    assert data_p2["items"][1]["transaction_date"] == "2025-01-02"

    # Page 3 with page_size=2
    res_p3 = await auth0_client_user_a.get("/api/v1/transactions?page=3&page_size=2")
    assert res_p3.status_code == 200
    data_p3 = res_p3.json()
    assert data_p3["page"] == 3
    assert len(data_p3["items"]) == 1
    assert data_p3["has_more"] is False
    assert data_p3["has_next"] is False
    assert data_p3["has_prev"] is True
    assert data_p3["items"][0]["transaction_date"] == "2025-01-01"

    # Filter by account_id = acc1_id (should have 3 transactions)
    res_acc1 = await auth0_client_user_a.get(f"/api/v1/transactions?account_id={acc1_id}&page=1&page_size=10")
    assert res_acc1.status_code == 200
    data_acc1 = res_acc1.json()
    assert data_acc1["total"] == 3
    assert len(data_acc1["items"]) == 3
    assert all(it["account_id"] == acc1_id for it in data_acc1["items"])

    # Filter by asset_id = ast2_id (should have 2 transactions)
    res_ast2 = await auth0_client_user_a.get(f"/api/v1/transactions?asset_id={ast2_id}&page=1&page_size=10")
    assert res_ast2.status_code == 200
    data_ast2 = res_ast2.json()
    assert data_ast2["total"] == 2
    assert len(data_ast2["items"]) == 2
    assert all(it["asset_id"] == ast2_id for it in data_ast2["items"])


@pytest.mark.anyio
async def test_stock_transactions_search_and_type_filter(auth0_client_user_a):
    acc = (await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Search Trade Account", "broker_name": "Broker", "account_type": "demat", "currency": "EUR"
    })).json()["account_id"]
    asset = (await auth0_client_user_a.post("/api/v1/assets", json={
        "symbol": "SEARCHME", "name": "Searchable Equity", "asset_type": "stock", "currency": "EUR"
    })).json()["asset_id"]
    for kind, note in (("buy", "ordinary"), ("sell", "needle note")):
        res = await auth0_client_user_a.post("/api/v1/transactions", json={
            "account_id": acc, "asset_id": asset, "transaction_type": kind,
            "transaction_date": "2025-07-01", "quantity": 1, "price_per_unit": 10,
            "total_amount": 10, "notes": note
        })
        assert res.status_code in (200, 201)

    res = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=20&search=needle&type=sell")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_type"] == "sell"
    assert data["items"][0]["notes"] == "needle note"


@pytest.mark.anyio
async def test_stock_transactions_caching_and_invalidation(auth0_client_user_a, mock_redis_cache):
    """
    Verify stock transactions are cached in Redis and invalidated on POST, PUT, DELETE.
    """
    me = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    user_id = me["user_id"]

    acc_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Cache Tx Demat",
        "broker_name": "Broker C",
        "account_type": "demat",
        "currency": "EUR"
    })
    acc_id = acc_res.json()["account_id"]

    ast_res = await auth0_client_user_a.post("/api/v1/assets", json={
        "symbol": "CACHE_AST",
        "name": "Cache Asset",
        "asset_type": "stock",
        "currency": "EUR"
    })
    ast_id = ast_res.json()["asset_id"]

    # Initial query caches the page
    res1 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res1.status_code == 200

    cache_key = cache_service.get_transaction_page_key(
        user_id=user_id,
        page=1,
        page_size=10,
        account_id=None,
        asset_id=None,
    )
    cached_val = await mock_redis_cache.get(cache_key)
    assert cached_val is not None, f"Expected cache key {cache_key} to be set in Redis"
    cached_obj = json.loads(cached_val)
    assert cached_obj["total"] == res1.json()["total"]

    # 1. POST transaction -> must invalidate transaction cache AND snapshot cache
    snap_key = cache_service.get_snapshot_key(user_id)
    await mock_redis_cache.set(snap_key, "snapshot_data")

    tx_res = await auth0_client_user_a.post("/api/v1/transactions", json={
        "account_id": acc_id,
        "asset_id": ast_id,
        "transaction_type": "buy",
        "transaction_date": "2025-03-01",
        "quantity": 5.0,
        "price_per_unit": 50.0,
        "total_amount": 250.0,
        "currency": "EUR"
    })
    assert tx_res.status_code in (200, 201)
    tx_id = tx_res.json()["transaction_id"]

    assert await mock_redis_cache.get(cache_key) is None, "POST /transactions must invalidate transaction cache"
    assert await mock_redis_cache.get(snap_key) is None, "POST /transactions must invalidate snapshot cache"

    # Re-cache transaction page
    res2 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res2.status_code == 200
    assert await mock_redis_cache.get(cache_key) is not None

    # 2. PUT transaction -> must invalidate transaction cache
    put_res = await auth0_client_user_a.put(f"/api/v1/transactions/{tx_id}", json={
        "quantity": 6.0,
        "total_amount": 300.0,
    })
    assert put_res.status_code == 200
    assert await mock_redis_cache.get(cache_key) is None, "PUT /transactions must invalidate transaction cache"

    # Re-cache transaction page
    await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert await mock_redis_cache.get(cache_key) is not None

    # 3. DELETE transaction -> must invalidate transaction cache
    del_res = await auth0_client_user_a.delete(f"/api/v1/transactions/{tx_id}")
    assert del_res.status_code in (200, 204)
    assert await mock_redis_cache.get(cache_key) is None, "DELETE /transactions must invalidate transaction cache"


@pytest.mark.anyio
async def test_cashflow_unpaginated_backward_compatibility(auth0_client_user_a):
    """
    Verify GET /api/v1/cashflow without page query parameter returns a plain list
    and includes pagination headers.
    """
    res = await auth0_client_user_a.get("/api/v1/cashflow")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list), "Unpaginated cashflow request must return a plain list"
    assert "X-Total-Count" in res.headers
    assert "X-Total-Pages" in res.headers
    assert "X-Page" in res.headers
    assert "X-Page-Size" in res.headers


@pytest.mark.anyio
async def test_cashflow_paginated_and_explicit_transactions_route(auth0_client_user_a):
    """
    Verify /api/v1/cashflow/transactions is an explicit route that handles pagination,
    returning PaginatedCashflowResponse with items, total, and correct page numbers.
    """
    # Create an account and category
    acc_res = await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Checking CF Route",
        "broker_name": "Bank CF",
        "account_type": "savings",
        "currency": "EUR"
    })
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post("/api/v1/categories", json={
        "name": "Groceries Route",
        "category_type": "EXPENSE",
        "default_label": "ESSENTIAL"
    })
    cat_id = cat_res.json()["category_id"]

    # Create 3 cashflow transactions
    for i in range(1, 4):
        await auth0_client_user_a.post("/api/v1/cashflow", json={
            "title": f"Grocery Trip {i}",
            "transaction_date": f"2025-02-0{i}",
            "currency": "EUR",
            "payments": [{"account_id": acc_id, "amount": 50.0 * i}],
            "items": [{"category_id": cat_id, "amount": 50.0 * i, "description": f"Item {i}"}]
        })

    # Call /api/v1/cashflow/transactions with page=1, page_size=2
    res = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=2")
    assert res.status_code == 200, f"Expected 200 from /api/v1/cashflow/transactions, got {res.status_code}: {res.text}"
    data = res.json()
    assert isinstance(data, dict)
    assert data["total"] >= 3
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["has_more"] is True

    # Call page 2
    res_p2 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=2&page_size=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["page"] == 2
    assert len(data_p2["items"]) >= 1

    # Call unpaginated /api/v1/cashflow/transactions -> should also succeed
    res_unpag = await auth0_client_user_a.get("/api/v1/cashflow/transactions")
    assert res_unpag.status_code == 200


@pytest.mark.anyio
async def test_cashflow_query_pushdown_filtering(auth0_client_user_a):
    """
    Verify child table filters (account_id, category_id, label) and date filters
    are pushed down into SQL queries, ensuring total count and pagination slices are exact.
    """
    # 1. Accounts
    acc1 = (await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Acc Filter 1", "broker_name": "Bank", "account_type": "savings", "currency": "EUR"
    })).json()["account_id"]

    acc2 = (await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Acc Filter 2", "broker_name": "Bank", "account_type": "savings", "currency": "EUR"
    })).json()["account_id"]

    # 2. Categories with labels
    cat_ess = (await auth0_client_user_a.post("/api/v1/categories", json={
        "name": "Utilities Essential", "category_type": "EXPENSE", "default_label": "ESSENTIAL"
    })).json()["category_id"]

    cat_disc = (await auth0_client_user_a.post("/api/v1/categories", json={
        "name": "Dining Discretionary", "category_type": "EXPENSE", "default_label": "DISCRETIONARY"
    })).json()["category_id"]

    # 3. Create cashflows:
    # cf1: acc1, cat_ess (inherited ESSENTIAL), date: 2025-03-01
    await auth0_client_user_a.post("/api/v1/cashflow", json={
        "title": "Power Bill",
        "transaction_date": "2025-03-01",
        "payments": [{"account_id": acc1, "amount": 100.0}],
        "items": [{"category_id": cat_ess, "amount": 100.0, "description": "Electric"}]
    })

    # cf2: acc2, cat_disc (inherited DISCRETIONARY), date: 2025-03-05
    await auth0_client_user_a.post("/api/v1/cashflow", json={
        "title": "Dinner Out",
        "transaction_date": "2025-03-05",
        "payments": [{"account_id": acc2, "amount": 75.0}],
        "items": [{"category_id": cat_disc, "amount": 75.0, "description": "Sushi"}]
    })

    # cf3: acc1, cat_disc, explicit override label LUXURY, date: 2025-03-10
    await auth0_client_user_a.post("/api/v1/cashflow", json={
        "title": "VIP Club",
        "transaction_date": "2025-03-10",
        "payments": [{"account_id": acc1, "amount": 500.0}],
        "items": [{"category_id": cat_disc, "amount": 500.0, "label": "LUXURY", "description": "VIP bottle"}]
    })

    # Pushdown Test A: Filter by account_id = acc1 (cf1 and cf3)
    r_acc = await auth0_client_user_a.get(f"/api/v1/cashflow/transactions?account_id={acc1}&page=1&page_size=10")
    assert r_acc.status_code == 200
    d_acc = r_acc.json()
    assert d_acc["total"] == 2
    assert all(any(p["account_id"] == acc1 for p in it["payments"]) for it in d_acc["items"])

    # Pushdown Test B: Filter by category_id = cat_ess (cf1 only)
    r_cat = await auth0_client_user_a.get(f"/api/v1/cashflow/transactions?category_id={cat_ess}&page=1&page_size=10")
    assert r_cat.status_code == 200
    d_cat = r_cat.json()
    assert d_cat["total"] == 1
    assert d_cat["items"][0]["title"] == "Power Bill"

    # Pushdown Test C: Filter by label = ESSENTIAL (inherited, cf1)
    r_lbl_ess = await auth0_client_user_a.get("/api/v1/cashflow/transactions?label=ESSENTIAL&page=1&page_size=10")
    assert r_lbl_ess.status_code == 200
    d_lbl_ess = r_lbl_ess.json()
    assert d_lbl_ess["total"] == 1
    assert d_lbl_ess["items"][0]["title"] == "Power Bill"

    # Pushdown Test D: Filter by label = LUXURY (explicit override, cf3)
    r_lbl_lux = await auth0_client_user_a.get("/api/v1/cashflow/transactions?label=LUXURY&page=1&page_size=10")
    assert r_lbl_lux.status_code == 200
    d_lbl_lux = r_lbl_lux.json()
    assert d_lbl_lux["total"] == 1
    assert d_lbl_lux["items"][0]["title"] == "VIP Club"

    # Pushdown Test E: Date range filter
    r_date = await auth0_client_user_a.get("/api/v1/cashflow/transactions?start_date=2025-03-02&end_date=2025-03-06&page=1&page_size=10")
    assert r_date.status_code == 200
    d_date = r_date.json()
    assert d_date["total"] == 1
    assert d_date["items"][0]["title"] == "Dinner Out"


@pytest.mark.anyio
async def test_cashflow_caching_and_invalidation(auth0_client_user_a, mock_redis_cache):
    """
    Verify cashflow transaction pages are cached in Redis and invalidated on POST, PUT, DELETE.
    """
    me = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    user_id = me["user_id"]

    acc = (await auth0_client_user_a.post("/api/v1/accounts", json={
        "account_name": "Cache CF Acc", "broker_name": "Bank", "account_type": "savings", "currency": "EUR"
    })).json()["account_id"]

    cat = (await auth0_client_user_a.post("/api/v1/categories", json={
        "name": "Cache CF Cat", "category_type": "EXPENSE"
    })).json()["category_id"]

    # Initial query caches the page
    res = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res.status_code == 200

    cache_key = cache_service.get_cashflow_page_key(
        user_id=user_id,
        page=1,
        page_size=10,
    )
    cached_val = await mock_redis_cache.get(cache_key)
    assert cached_val is not None, f"Expected cache key {cache_key} in Redis"

    # 1. POST cashflow -> invalidates cashflow cache
    cf_res = await auth0_client_user_a.post("/api/v1/cashflow", json={
        "title": "Bust Cashflow Cache",
        "transaction_date": "2025-04-01",
        "payments": [{"account_id": acc, "amount": 100.0}],
        "items": [{"category_id": cat, "amount": 100.0, "description": "Test"}]
    })
    assert cf_res.status_code in (200, 201)
    cf_id = cf_res.json()["cashflow_id"]
    assert await mock_redis_cache.get(cache_key) is None, "POST /cashflow must bust cashflow cache"

    # Re-prime cache
    await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert await mock_redis_cache.get(cache_key) is not None

    # 2. PUT cashflow -> invalidates cashflow cache
    put_res = await auth0_client_user_a.put(f"/api/v1/cashflow/{cf_id}", json={
        "title": "Bust Cashflow Cache Updated",
    })
    assert put_res.status_code == 200
    assert await mock_redis_cache.get(cache_key) is None, "PUT /cashflow must bust cashflow cache"

    # Re-prime cache
    await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert await mock_redis_cache.get(cache_key) is not None

    # 3. DELETE cashflow -> invalidates cashflow cache
    del_res = await auth0_client_user_a.delete(f"/api/v1/cashflow/{cf_id}")
    assert del_res.status_code in (200, 204)
    assert await mock_redis_cache.get(cache_key) is None, "DELETE /cashflow must bust cashflow cache"


@pytest.mark.anyio
async def test_multi_tenant_pagination_cache_isolation(auth0_client_user_a, auth0_client_user_b, mock_redis_cache):
    """
    Verify User A and User B have separate cache keys and mutations do not invalidate another user's cache.
    """
    me_a = (await auth0_client_user_a.get("/api/v1/auth/me")).json()
    me_b = (await auth0_client_user_b.get("/api/v1/auth/me")).json()
    user_a = me_a["user_id"]
    user_b = me_b["user_id"]
    assert user_a != user_b

    # Prime caches
    await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    await auth0_client_user_b.get("/api/v1/transactions?page=1&page_size=10")

    key_a = cache_service.get_transaction_page_key(user_id=user_a, page=1, page_size=10)
    key_b = cache_service.get_transaction_page_key(user_id=user_b, page=1, page_size=10)

    assert await mock_redis_cache.get(key_a) is not None
    assert await mock_redis_cache.get(key_b) is not None

    # Invalidate User A
    await cache_service.invalidate_user_transaction_cache(user_a)

    assert await mock_redis_cache.get(key_a) is None, "User A cache must be deleted"
    assert await mock_redis_cache.get(key_b) is not None, "User B cache must NOT be deleted"


@pytest.mark.anyio
async def test_pagination_caching_graceful_degradation(auth0_client_user_a):
    """
    Verify that if Redis throws an exception during get/set/invalidate,
    the pagination endpoints still return 200 HTTP response.
    """
    failing_client = AsyncMock()
    failing_client.get.side_effect = ConnectionError("Redis is offline")
    failing_client.set.side_effect = ConnectionError("Redis is offline")

    async def failing_scan_iter(match=None, count=None):
        raise ConnectionError("Redis is offline")
        yield

    failing_client.scan_iter = failing_scan_iter
    cache_service.set_redis_client(failing_client)

    try:
        res_tx = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
        assert res_tx.status_code == 200

        res_cf = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
        assert res_cf.status_code == 200
    finally:
        cache_service.set_redis_client(None)
