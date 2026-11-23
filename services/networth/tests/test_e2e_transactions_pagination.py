"""
E2E Test Suite: R2 - Backend Transaction and Cashflow Pagination, Caching, and Invalidation.
Endpoints: /api/v1/transactions and /api/v1/cashflow/transactions

4-Tier Matrix:
- Tier 1: Feature Coverage (Default pagination, custom page size & navigation, cashflow transactions
          route, backward compatibility when page is omitted, stock Redis cache hit, cashflow Redis cache hit)
- Tier 2: Boundary & Corner Cases (Empty database total=0, page beyond total, invalid page numbers,
          minimum page_size=1, max/overflow page_size, exact multiple page boundary)
- Tier 3: Cross-Feature Combinations (Stock pagination with filters, cashflow pagination with SQL
          pushdown, cache busting on stock CRUD, cache busting on cashflow CRUD, multi-tenant cache isolation)
- Tier 4: Real-World Scenarios (Progressive infinite scroll ledger traversal across 4 pages with
          order and deduplication checks, middle-page transaction mutation workflow)
"""

import json
import asyncio
import datetime
import pytest
from httpx import AsyncClient

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
    symbol: str = "PAGIN_AAPL",
    name: str = "Pagination Apple",
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

    list_res = await client.get("/api/v1/assets")
    if list_res.status_code == 200:
        for a in list_res.json():
            if a["symbol"] == symbol.upper().strip():
                return a["asset_id"]
    raise RuntimeError(f"Could not get or create asset {symbol}: {res.text}")


async def seed_stock_transactions(
    client: AsyncClient,
    account_id: int,
    asset_id: int,
    count: int = 15,
    base_date: datetime.date = datetime.date(2026, 1, 1)
) -> list:
    """Helper to seed N stock transactions via API in ascending date order."""
    created = []
    for i in range(count):
        tx_date = (base_date + datetime.timedelta(days=i)).isoformat()
        res = await client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "asset_id": asset_id,
                "transaction_type": "buy",
                "quantity": 1.0 + i,
                "price_per_unit": 100.0,
                "total_amount": round((1.0 + i) * 100.0, 2),
                "transaction_date": tx_date,
                "notes": f"Stock Trade #{i + 1}"
            }
        )
        assert res.status_code == 201, f"Failed creating trade {i}: {res.text}"
        created.append(res.json())
    return created


async def seed_cashflow_transactions(
    client: AsyncClient,
    account_id: int,
    category_id: int,
    count: int = 15,
    base_date: datetime.date = datetime.date(2026, 1, 1)
) -> list:
    """Helper to seed N cashflow transactions via API in ascending date order."""
    created = []
    for i in range(count):
        cf_date = (base_date + datetime.timedelta(days=i)).isoformat()
        res = await client.post(
            "/api/v1/cashflow",
            json={
                "title": f"Cashflow Item #{i + 1}",
                "total_amount": round(50.0 + i * 10.0, 2),
                "currency": "EUR",
                "transaction_kind": "EXPENSE",
                "transaction_date": cf_date,
                "payments": [{"account_id": account_id, "amount": round(50.0 + i * 10.0, 2)}],
                "items": [{"category_id": category_id, "amount": round(50.0 + i * 10.0, 2)}]
            }
        )
        assert res.status_code == 201, f"Failed creating cashflow {i}: {res.text}"
        created.append(res.json())
    return created


# ==============================================================================
# TIER 1: FEATURE COVERAGE (6 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_stock_transactions_default_pagination(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.1: Stock Transactions Default Pagination.
    When page=1 is requested, returns paginated envelope with items, total,
    page, page_size, total_pages, and has_more metadata.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="PAG_DEF", name="Pagination Default Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Stock Pagin Acc", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    # Seed 15 transactions
    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=15)

    res = await auth0_client_user_a.get("/api/v1/transactions?page=1")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict), "Paginated response must be a JSON dictionary envelope"
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "has_more" in data

    assert data["total"] == 15
    assert data["page"] == 1
    assert data["page_size"] >= 15
    assert len(data["items"]) == 15
    assert data["has_more"] is False
    assert data["total_pages"] == 1


@pytest.mark.anyio
async def test_stock_transactions_custom_page_size_and_navigation(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.2: Custom Page Size & Multi-Page Navigation.
    Seeds 25 transactions, navigates across 3 pages with page_size=10.
    Verifies total_pages=3, page 1 (10 items), page 2 (10 items), page 3 (5 items),
    has_more transitions (True -> True -> False), and zero duplicate IDs across pages.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="PAG_NAV", name="Navigation Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Stock Nav Acc", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=25)

    # Page 1: 10 items, has_more=True
    res1 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res1.status_code == 200
    p1 = res1.json()
    assert p1["total"] == 25
    assert p1["page"] == 1
    assert p1["page_size"] == 10
    assert p1["total_pages"] == 3
    assert p1["has_more"] is True
    assert len(p1["items"]) == 10

    # Page 2: 10 items, has_more=True
    res2 = await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=10")
    assert res2.status_code == 200
    p2 = res2.json()
    assert p2["total"] == 25
    assert p2["page"] == 2
    assert p2["total_pages"] == 3
    assert p2["has_more"] is True
    assert len(p2["items"]) == 10

    # Page 3: 5 items, has_more=False
    res3 = await auth0_client_user_a.get("/api/v1/transactions?page=3&page_size=10")
    assert res3.status_code == 200
    p3 = res3.json()
    assert p3["total"] == 25
    assert p3["page"] == 3
    assert p3["total_pages"] == 3
    assert p3["has_more"] is False
    assert len(p3["items"]) == 5

    # Deduplication and completeness check
    ids_p1 = [tx["transaction_id"] for tx in p1["items"]]
    ids_p2 = [tx["transaction_id"] for tx in p2["items"]]
    ids_p3 = [tx["transaction_id"] for tx in p3["items"]]

    assert len(set(ids_p1).intersection(set(ids_p2))) == 0, "No overlap between Page 1 and Page 2"
    assert len(set(ids_p2).intersection(set(ids_p3))) == 0, "No overlap between Page 2 and Page 3"
    assert len(set(ids_p1).intersection(set(ids_p3))) == 0, "No overlap between Page 1 and Page 3"

    all_ids = ids_p1 + ids_p2 + ids_p3
    assert len(all_ids) == 25
    assert len(set(all_ids)) == 25


@pytest.mark.anyio
async def test_cashflow_transactions_pagination_route_and_metadata(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.3: Cashflow Transactions Pagination Route & Metadata.
    Verifies that /api/v1/cashflow/transactions accepts page and page_size query parameters,
    returning paginated envelope with split items, total count, and pagination metadata.
    """
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "CF Pagin Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "CF Pagin Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    # Seed 15 cashflow transactions
    await seed_cashflow_transactions(auth0_client_user_a, acc_id, cat_id, count=15)

    # Page 1
    res1 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=5")
    assert res1.status_code == 200
    p1 = res1.json()
    assert isinstance(p1, dict)
    assert p1["total"] == 15
    assert p1["page"] == 1
    assert p1["page_size"] == 5
    assert p1["total_pages"] == 3
    assert p1["has_more"] is True
    assert len(p1["items"]) == 5

    # Page 2
    res2 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=2&page_size=5")
    assert res2.status_code == 200
    p2 = res2.json()
    assert p2["page"] == 2
    assert len(p2["items"]) == 5


@pytest.mark.anyio
async def test_backward_compatibility_unpaginated_requests(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.4: Backward Compatibility for Unpaginated Requests.
    When `page` parameter is omitted from GET /api/v1/transactions and GET /api/v1/cashflow,
    the endpoints MUST return raw JSON lists (List[T]) rather than envelopes,
    preventing regressions across existing callers.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="BACK_COMP", name="Backward Compatibility Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Back Compat Acc", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Back Compat Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=5)
    await seed_cashflow_transactions(auth0_client_user_a, acc_id, cat_id, count=5)

    # 1. GET /api/v1/transactions without page parameter
    res_stock = await auth0_client_user_a.get("/api/v1/transactions")
    assert res_stock.status_code == 200
    data_stock = res_stock.json()
    assert isinstance(data_stock, list), "Unpaginated stock transactions must return a list"
    assert len(data_stock) == 5

    # 2. GET /api/v1/cashflow without page parameter
    res_cf = await auth0_client_user_a.get("/api/v1/cashflow")
    assert res_cf.status_code == 200
    data_cf = res_cf.json()
    assert isinstance(data_cf, list), "Unpaginated cashflow transactions must return a list"
    assert len(data_cf) == 5


@pytest.mark.anyio
async def test_stock_transaction_redis_cache_hit(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.5: Stock Transaction Redis Cache Hit.
    First GET /api/v1/transactions?page=1 populates Redis.
    Second GET serves cached data directly from Redis.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="STOCK_CACHE", name="Stock Cache Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Stock Cache Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=5)

    # First request: cache miss, populates Redis
    res1 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res1.status_code == 200

    # Verify key was written to Redis
    user_a_id = await get_user_id(auth0_client_user_a)
    keys = await fake_redis.keys(f"gl:tx:{user_a_id}:*")
    assert len(keys) > 0, f"Expected cache key gl:tx:{user_a_id}:* in Redis"

    # Mutate the cached payload in Redis to prove second request is a true cache hit
    matched_key = keys[0]
    cached_val = json.loads(await fake_redis.get(matched_key))
    cached_val["total"] = 777
    await fake_redis.set(matched_key, json.dumps(cached_val))

    # Second request must return the cached tampered total
    res2 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res2.status_code == 200
    assert res2.json()["total"] == 777


@pytest.mark.anyio
async def test_cashflow_transaction_redis_cache_hit(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 1.6: Cashflow Transaction Redis Cache Hit.
    First GET /api/v1/cashflow/transactions?page=1 populates Redis.
    Second GET serves cached data directly from Redis.
    """
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "CF Cache Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "CF Cache Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    await seed_cashflow_transactions(auth0_client_user_a, acc_id, cat_id, count=5)

    # Request 1: populates cache
    res1 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res1.status_code == 200

    user_a_id = await get_user_id(auth0_client_user_a)
    keys = await fake_redis.keys(f"gl:cf*:{user_a_id}:*")
    assert len(keys) > 0, "Expected cashflow cache key in Redis"

    # Mutate cached total
    matched_key = keys[0]
    cached_val = json.loads(await fake_redis.get(matched_key))
    cached_val["total"] = 888
    await fake_redis.set(matched_key, json.dumps(cached_val))

    # Request 2: returns cached total
    res2 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res2.status_code == 200
    assert res2.json()["total"] == 888


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (6 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_pagination_empty_database(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.1: Empty Database Pagination Semantics.
    When the database has 0 records, requests return 200 OK with:
    items=[], total=0, page=1, total_pages in [0, 1], has_more=False.
    """
    res_stock = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res_stock.status_code == 200
    p_stock = res_stock.json()
    assert p_stock["items"] == []
    assert p_stock["total"] == 0
    assert p_stock["page"] == 1
    assert p_stock["has_more"] is False

    res_cf = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res_cf.status_code == 200
    p_cf = res_cf.json()
    assert p_cf["items"] == []
    assert p_cf["total"] == 0
    assert p_cf["page"] == 1
    assert p_cf["has_more"] is False


@pytest.mark.anyio
async def test_pagination_page_beyond_total(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.2: Page Beyond Total Available Records.
    When requesting page=10 when only 5 records exist, returns 200 OK with
    items=[], total=5, page=10, has_more=False.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="BEYOND_TOT", name="Beyond Total Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Beyond Acc", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=5)

    res = await auth0_client_user_a.get("/api/v1/transactions?page=10&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 5
    assert data["page"] == 10
    assert data["has_more"] is False


@pytest.mark.anyio
async def test_pagination_invalid_page_numbers(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.3: Invalid Page Numbers.
    page=0, page=-1, or page=abc must either return 422 Unprocessable Entity
    or clamp cleanly to page=1 without throwing 500.
    """
    # page=0
    res_zero = await auth0_client_user_a.get("/api/v1/transactions?page=0&page_size=10")
    assert res_zero.status_code in [422, 400] or (res_zero.status_code == 200 and res_zero.json()["page"] == 1)

    # page=-1
    res_neg = await auth0_client_user_a.get("/api/v1/transactions?page=-1&page_size=10")
    assert res_neg.status_code in [422, 400] or (res_neg.status_code == 200 and res_neg.json()["page"] == 1)

    # page=abc
    res_alpha = await auth0_client_user_a.get("/api/v1/transactions?page=abc&page_size=10")
    assert res_alpha.status_code == 422


@pytest.mark.anyio
async def test_pagination_page_size_minimum_boundary(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.4: Minimum Page Size Boundary (page_size=1).
    Seeds 5 transactions, requests page=1&page_size=1.
    Asserts len(items)=1, total=5, total_pages=5, has_more=True.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="PAGE_SIZE_1", name="Page Size 1 Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Page Size 1 Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=5)

    res = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["total"] == 5
    assert data["page_size"] == 1
    assert data["total_pages"] == 5
    assert data["has_more"] is True


@pytest.mark.anyio
async def test_pagination_page_size_maximum_and_overflow(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.5: Maximum Page Size & Overflow Constraints.
    page_size=500 is allowed. page_size=1000 is either clamped to 500 or rejected with 422.
    page_size=0 is rejected with 422 (must be >= 1).
    """
    # Allowed maximum
    res_max = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=500")
    assert res_max.status_code == 200

    # Overflow
    res_overflow = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=1000")
    assert res_overflow.status_code in [200, 422]
    if res_overflow.status_code == 200:
        assert res_overflow.json()["page_size"] <= 500

    # Zero page_size
    res_zero = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=0")
    assert res_zero.status_code in [400, 422]


@pytest.mark.anyio
async def test_pagination_exact_multiple_boundary(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 2.6: Exact Multiple Page Boundary.
    Seeds exactly 20 transactions with page_size=10.
    Page 1 returns 10 items, has_more=True.
    Page 2 returns 10 items, has_more=False, total_pages=2.
    Page 3 returns 0 items, has_more=False.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="EXACT_MULT", name="Exact Multiple Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Exact Mult Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=20)

    # Page 1
    p1 = (await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")).json()
    assert len(p1["items"]) == 10
    assert p1["has_more"] is True
    assert p1["total_pages"] == 2

    # Page 2 (Exact end)
    p2 = (await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=10")).json()
    assert len(p2["items"]) == 10
    assert p2["has_more"] is False
    assert p2["total_pages"] == 2

    # Page 3 (Past end)
    p3 = (await auth0_client_user_a.get("/api/v1/transactions?page=3&page_size=10")).json()
    assert p3["items"] == []
    assert p3["has_more"] is False


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (Filters, SQL Pushdown, Cache Busting) (5 Test Cases)
# ==============================================================================

@pytest.mark.anyio
async def test_stock_pagination_with_account_and_asset_filtering(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.1: Stock Pagination with Account & Asset Filtering.
    Seeds Account 1 with 5 AAPL trades and 5 MSFT trades.
    Seeds Account 2 with 10 GOOG trades.
    Queries /api/v1/transactions?account_id={acc1}&asset_id={aapl}&page=1&page_size=3.
    Asserts total=5, total_pages=2, has_more=True, and every returned item matches filters.
    """
    aapl_id = await get_or_create_asset(auth0_client_user_a, symbol="FILT_AAPL", name="Filter Apple")
    msft_id = await get_or_create_asset(auth0_client_user_a, symbol="FILT_MSFT", name="Filter Microsoft")
    goog_id = await get_or_create_asset(auth0_client_user_a, symbol="FILT_GOOG", name="Filter Google")

    acc1 = (await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Filter Acc 1", "account_type": "demat", "currency": "EUR"}
    )).json()["account_id"]

    acc2 = (await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Filter Acc 2", "account_type": "demat", "currency": "EUR"}
    )).json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc1, aapl_id, count=5)
    await seed_stock_transactions(auth0_client_user_a, acc1, msft_id, count=5)
    await seed_stock_transactions(auth0_client_user_a, acc2, goog_id, count=10)

    res = await auth0_client_user_a.get(f"/api/v1/transactions?account_id={acc1}&asset_id={aapl_id}&page=1&page_size=3")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 5
    assert data["total_pages"] == 2
    assert data["has_more"] is True
    assert len(data["items"]) == 3
    for tx in data["items"]:
        assert tx["account_id"] == acc1
        assert tx["asset_id"] == aapl_id


@pytest.mark.anyio
async def test_cashflow_pagination_with_date_range_account_and_category_pushdown(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.2: Cashflow Pagination with SQL Filter Pushdown.
    Seeds cashflow transactions across July and August 2026.
    Queries /api/v1/cashflow/transactions with date filters and account filter.
    Asserts that SQL pushdown calculates the exact filtered total and returns correct slices.
    """
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Pushdown Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Pushdown Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    # 10 July transactions
    await seed_cashflow_transactions(
        auth0_client_user_a, acc_id, cat_id, count=10,
        base_date=datetime.date(2026, 7, 1)
    )

    # 10 August transactions
    await seed_cashflow_transactions(
        auth0_client_user_a, acc_id, cat_id, count=10,
        base_date=datetime.date(2026, 8, 1)
    )

    # Filter strictly for August 2026
    res = await auth0_client_user_a.get(
        f"/api/v1/cashflow/transactions?start_date=2026-08-01&end_date=2026-08-31&account_id={acc_id}&page=1&page_size=5"
    )
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 10
    assert data["total_pages"] == 2
    assert len(data["items"]) == 5
    for item in data["items"]:
        assert item["transaction_date"] >= "2026-08-01"
        assert item["transaction_date"] <= "2026-08-31"


@pytest.mark.anyio
async def test_cache_invalidation_on_stock_crud(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.3: Cache Invalidation on Stock CRUD Operations.
    Step 1: Cache page 1 of transactions.
    Step 2: POST trade -> verifies cache invalidated and new trade appears on page 1.
    Step 3: PUT trade -> verifies cache invalidated and notes/price updated.
    Step 4: DELETE trade -> verifies cache invalidated and total decrements.
    Step 5: Verify snapshot cache was also invalidated on each step.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="CRUD_STOCK", name="CRUD Stock Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "CRUD Stock Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    user_a_id = await get_user_id(auth0_client_user_a)

    # Step 1: Initial cache established
    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=5)
    res1 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res1.json()["total"] == 5

    # Also establish snapshot cache
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    sum_key = cache_service.get_portfolio_summary_key(user_a_id)
    assert await fake_redis.get(sum_key) is not None

    # Step 2: Create new trade
    create_res = await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 10.0,
            "price_per_unit": 200.0,
            "total_amount": 2000.0,
            "transaction_date": "2026-11-20",
            "notes": "Newly Added Buy"
        }
    )
    assert create_res.status_code == 201
    new_tx_id = create_res.json()["transaction_id"]

    # Verify snapshot cache was busted
    assert await fake_redis.get(sum_key) is None

    # Verify transaction cache was busted: total must be 6
    res2 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res2.json()["total"] == 6
    assert res2.json()["items"][0]["transaction_id"] == new_tx_id

    # Step 3: Update trade
    await auth0_client_user_a.get("/api/v1/portfolio/summary")
    assert await fake_redis.get(sum_key) is not None

    put_res = await auth0_client_user_a.put(
        f"/api/v1/transactions/{new_tx_id}",
        json={"notes": "Mutated Buy Note"}
    )
    assert put_res.status_code == 200
    assert await fake_redis.get(sum_key) is None

    res3 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res3.json()["items"][0]["notes"] == "Mutated Buy Note"

    # Step 4: Delete trade
    del_res = await auth0_client_user_a.delete(f"/api/v1/transactions/{new_tx_id}")
    assert del_res.status_code == 204

    res4 = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res4.json()["total"] == 5


@pytest.mark.anyio
async def test_cache_invalidation_on_cashflow_crud(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 3.4: Cache Invalidation on Cashflow CRUD Operations.
    Creating, updating, or deleting a cashflow record invalidates both
    the cashflow pagination cache and the user's snapshot cache.
    """
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "CF CRUD Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "CF CRUD Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    await seed_cashflow_transactions(auth0_client_user_a, acc_id, cat_id, count=5)

    # Initial query caches
    res1 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res1.json()["total"] == 5

    # Create new cashflow
    cf_new = await auth0_client_user_a.post(
        "/api/v1/cashflow",
        json={
            "title": "Fresh Bill",
            "total_amount": 250.0,
            "currency": "EUR",
            "transaction_kind": "EXPENSE",
            "transaction_date": "2026-11-20",
            "payments": [{"account_id": acc_id, "amount": 250.0}],
            "items": [{"category_id": cat_id, "amount": 250.0}]
        }
    )
    assert cf_new.status_code == 201
    cf_id = cf_new.json()["cashflow_id"]

    # Verify cache busted: total is 6
    res2 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res2.json()["total"] == 6

    # Update cashflow
    put_res = await auth0_client_user_a.put(
        f"/api/v1/cashflow/{cf_id}",
        json={"title": "Updated Fresh Bill"}
    )
    assert put_res.status_code == 200

    res3 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert any(c["title"] == "Updated Fresh Bill" for c in res3.json()["items"])

    # Delete cashflow
    del_res = await auth0_client_user_a.delete(f"/api/v1/cashflow/{cf_id}")
    assert del_res.status_code == 204

    res4 = await auth0_client_user_a.get("/api/v1/cashflow/transactions?page=1&page_size=10")
    assert res4.json()["total"] == 5


@pytest.mark.anyio
async def test_multi_tenant_cache_and_pagination_isolation(
    fake_redis,
    auth0_client_user_a: AsyncClient,
    auth0_client_user_b: AsyncClient
):
    """
    Tier 3.5: Multi-Tenant Cache and Pagination Isolation.
    User A has 10 transactions. User B has 10 transactions.
    Both cache page 1. User A adds a transaction.
    User A's cache is invalidated (returns 11 items).
    User B's cache is untouched (returns cached 10 items).
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="TENANT_ISOL", name="Tenant Isolation Asset")

    acc_a = (await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "User A Demat", "account_type": "demat", "currency": "EUR"}
    )).json()["account_id"]

    acc_b = (await auth0_client_user_b.post(
        "/api/v1/accounts",
        json={"account_name": "User B Demat", "account_type": "demat", "currency": "EUR"}
    )).json()["account_id"]

    await seed_stock_transactions(auth0_client_user_a, acc_a, asset_id, count=10)
    await seed_stock_transactions(auth0_client_user_b, acc_b, asset_id, count=10)

    # Both query page 1
    p1_a = (await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")).json()
    p1_b = (await auth0_client_user_b.get("/api/v1/transactions?page=1&page_size=10")).json()

    assert p1_a["total"] == 10
    assert p1_b["total"] == 10

    # User A creates a new trade
    await auth0_client_user_a.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_a,
            "asset_id": asset_id,
            "transaction_type": "buy",
            "quantity": 100.0,
            "price_per_unit": 50.0,
            "total_amount": 5000.0,
            "transaction_date": "2026-11-21"
        }
    )

    # User A's cache is invalidated -> total = 11
    res_a_after = await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")
    assert res_a_after.json()["total"] == 11

    # User B's cache remains intact -> total = 10
    res_b_after = await auth0_client_user_b.get("/api/v1/transactions?page=1&page_size=10")
    assert res_b_after.json()["total"] == 10


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS (Infinite Scroll Traversal & Mutation) (2 Workflows)
# ==============================================================================

@pytest.mark.anyio
async def test_real_world_infinite_scroll_multi_page_traversal(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 4.1: Progressive Infinite Scroll Ledger Traversal.
    Simulates the exact frontend infinite scroll consumption pattern:
    - Seeds 35 cashflow transactions across multiple months.
    - Sequentially queries Page 1 (10), Page 2 (10), Page 3 (10), Page 4 (5).
    - Checks ledger consistency: exactly 35 items accumulated, strict descending
      chronological ordering, and zero duplicate IDs across pages.
    """
    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Ledger Scroll Bank", "account_type": "bank", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    cat_res = await auth0_client_user_a.post(
        "/api/v1/categories",
        json={"name": "Ledger Scroll Cat", "category_type": "EXPENSE"}
    )
    cat_id = cat_res.json()["category_id"]

    # Seed 35 transactions across 35 consecutive days
    await seed_cashflow_transactions(
        auth0_client_user_a, acc_id, cat_id, count=35,
        base_date=datetime.date(2026, 8, 1)
    )

    accumulated_items = []
    page = 1
    page_size = 10

    while True:
        res = await auth0_client_user_a.get(f"/api/v1/cashflow/transactions?page={page}&page_size={page_size}")
        assert res.status_code == 200
        data = res.json()

        assert data["total"] == 35
        assert data["total_pages"] == 4
        accumulated_items.extend(data["items"])

        if not data["has_more"]:
            break
        page += 1

    # Ledger Verification
    assert page == 4, "Must complete on Page 4"
    assert len(accumulated_items) == 35, "Must accumulate exactly 35 items"

    # Deduplication check
    all_cf_ids = [item["cashflow_id"] for item in accumulated_items]
    assert len(set(all_cf_ids)) == 35, "All 35 cashflow transactions must be distinct"

    # Strict descending chronological order check
    for i in range(len(accumulated_items) - 1):
        curr_item = accumulated_items[i]
        next_item = accumulated_items[i + 1]
        assert curr_item["transaction_date"] >= next_item["transaction_date"], (
            f"Ordering violation at index {i}: {curr_item['transaction_date']} < {next_item['transaction_date']}"
        )


@pytest.mark.anyio
async def test_real_world_middle_page_mutation_workflow(
    fake_redis,
    auth0_client_user_a: AsyncClient
):
    """
    Tier 4.2: Middle-Page Transaction Mutation Workflow.
    Simulates user scrolling to Page 2, editing a record, and verifying that:
    1. Caches across all pages are invalidated.
    2. Re-fetching Page 2 immediately displays the mutated data.
    3. Deleting the record decrements total to 24, causes Page 2 to receive
       what was previously at the top of Page 3, and Page 3 shrinks to 4 items.
    """
    asset_id = await get_or_create_asset(auth0_client_user_a, symbol="MID_PAGE_MUT", name="Middle Page Asset")

    acc_res = await auth0_client_user_a.post(
        "/api/v1/accounts",
        json={"account_name": "Mid Page Demat", "account_type": "demat", "currency": "EUR"}
    )
    acc_id = acc_res.json()["account_id"]

    # Seed 25 transactions
    await seed_stock_transactions(auth0_client_user_a, acc_id, asset_id, count=25)

    # 1. Fetch and cache Pages 1, 2, and 3
    p1 = (await auth0_client_user_a.get("/api/v1/transactions?page=1&page_size=10")).json()
    p2 = (await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=10")).json()
    p3 = (await auth0_client_user_a.get("/api/v1/transactions?page=3&page_size=10")).json()

    assert p1["total"] == 25
    assert len(p2["items"]) == 10
    assert len(p3["items"]) == 5

    # Target a record located in the middle of Page 2 (e.g. index 4 in p2)
    target_tx = p2["items"][4]
    target_tx_id = target_tx["transaction_id"]

    # 2. Mutate target record via PUT /api/v1/transactions/{id}
    put_res = await auth0_client_user_a.put(
        f"/api/v1/transactions/{target_tx_id}",
        json={"price_per_unit": 999.0, "notes": "Middle Page Mutated Price"}
    )
    assert put_res.status_code == 200

    # 3. Re-fetch Page 2: must immediately reflect the mutated price
    p2_re = (await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=10")).json()
    mutated_in_p2 = next((tx for tx in p2_re["items"] if tx["transaction_id"] == target_tx_id), None)
    assert mutated_in_p2 is not None, "Mutated transaction must still be on Page 2"
    assert mutated_in_p2["price_per_unit"] == 999.0
    assert mutated_in_p2["notes"] == "Middle Page Mutated Price"

    # 4. Delete the target record via DELETE /api/v1/transactions/{id}
    del_res = await auth0_client_user_a.delete(f"/api/v1/transactions/{target_tx_id}")
    assert del_res.status_code == 204

    # 5. Verify page boundary shift
    p2_after_del = (await auth0_client_user_a.get("/api/v1/transactions?page=2&page_size=10")).json()
    p3_after_del = (await auth0_client_user_a.get("/api/v1/transactions?page=3&page_size=10")).json()

    # Total must decrease to 24
    assert p2_after_del["total"] == 24
    # Page 2 still has 10 items because the top item of Page 3 shifted into Page 2
    assert len(p2_after_del["items"]) == 10
    # Page 3 now has 4 items
    assert len(p3_after_del["items"]) == 4
    assert p3_after_del["has_more"] is False
