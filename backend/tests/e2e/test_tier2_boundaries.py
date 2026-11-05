import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey
from app.services.mcp_openapi_service import build_mcp_openapi_spec
import app.mcp.server as mcp_server
from conftest import get_test_sessionmaker


# ==============================================================================
# Tier 2: Boundary & Corner Cases — Authentication Boundaries
# ==============================================================================

@pytest.mark.anyio
async def test_mcp_auth_boundary_invalid_key(e2e_client: AsyncClient):
    """Verify non-existent API key returns 401 Unauthorized."""
    res = await e2e_client.get(
        "/api/v1/mcp/categories",
        headers={"X-API-Key": "gl_mcp_non_existent_key_99999999999999999999"}
    )
    assert res.status_code == 401, f"Expected 401 for invalid key, got {res.status_code}"


@pytest.mark.anyio
async def test_mcp_auth_boundary_revoked_key(
    e2e_client: AsyncClient,
    e2e_session: AsyncSession,
    e2e_primary_api_key: str
):
    """Verify inactive / revoked API key returns 401 Unauthorized."""
    raw_key = e2e_primary_api_key

    # Deactivate the key directly in DB
    await e2e_session.execute(
        update(ApiKey).where(ApiKey.user_id == 1).values(is_active=False)
    )
    await e2e_session.commit()

    # Attempt request with deactivated key
    res = await e2e_client.get("/api/v1/mcp/categories", headers={"X-API-Key": raw_key})
    assert res.status_code == 401, f"Expected 401 for revoked key, got {res.status_code}"


@pytest.mark.anyio
async def test_mcp_auth_boundary_empty_and_whitespace_headers(e2e_client: AsyncClient):
    """Verify empty or whitespace-only auth headers return 401."""
    empty_headers = [
        {"X-API-Key": ""},
        {"X-API-Key": "   "},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer   "},
        {"Authorization": ""},
    ]
    for h in empty_headers:
        res = await e2e_client.get("/api/v1/mcp/categories", headers=h)
        assert res.status_code == 401, f"Expected 401 for header {h}, got {res.status_code}"


@pytest.mark.anyio
async def test_mcp_auth_permissive_formatting(e2e_client: AsyncClient, e2e_primary_api_key: str):
    """
    Verify auth parser gracefully handles formatting quirks from ChatGPT Actions:
    - Double 'Bearer Bearer ...' prefix
    - Quoted keys '"gl_mcp_..."'
    - Whitespace padded keys
    """
    raw_key = e2e_primary_api_key

    quirky_headers = [
        {"Authorization": f"Bearer Bearer {raw_key}"},
        {"Authorization": f'Bearer "{raw_key}"'},
        {"Authorization": f"Bearer  {raw_key}  "},
        {"Authorization": f"Token {raw_key}"},
    ]

    for h in quirky_headers:
        res = await e2e_client.get("/api/v1/mcp/categories", headers=h)
        assert res.status_code == 200, f"Expected 200 for quirky header {h}, got {res.status_code}: {res.text}"


# ==============================================================================
# Tier 2: Boundary & Corner Cases — Subpath Invalidation & HTTP Verbs
# ==============================================================================

@pytest.mark.anyio
async def test_import_route_boundary_deep_and_nested_subpaths(e2e_client: AsyncClient):
    """Verify non-existent nested paths under /api/v1/import with various verbs return 404."""
    test_calls = [
        ("GET", "/api/v1/import/deeply/nested/batches/100"),
        ("POST", "/api/v1/import/unknown/subpath"),
        ("PUT", "/api/v1/import/batches/1/records"),
        ("DELETE", "/api/v1/import/batches/123/records/456"),
        ("PATCH", "/api/v1/import/nonexistent"),
    ]
    for method, path in test_calls:
        res = await e2e_client.request(method, path)
        assert res.status_code == 404, f"Expected 404 for {method} {path}, got {res.status_code}"


# ==============================================================================
# Tier 2: Boundary & Corner Cases — MCP OpenAPI Boundary Rules
# ==============================================================================

def test_mcp_openapi_boundary_chatgpt_actions_invariants():
    """
    Verify OpenAPI specification boundary constraints:
    1. OpenAPI version is exactly 3.1.0
    2. Operation descriptions <= 300 characters across all operations
    3. Stripping of internal parameters (offset, X-API-Key)
    4. BearerAuth security scheme configuration
    """
    spec = build_mcp_openapi_spec()
    assert spec["openapi"] == "3.1.0"
    assert "paths" in spec

    # Security schemes check
    components = spec.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    assert "BearerAuth" in security_schemes
    assert security_schemes["BearerAuth"]["type"] == "http"
    assert security_schemes["BearerAuth"]["scheme"] == "bearer"

    # Descriptions & parameter stripping
    for path, path_item in spec["paths"].items():
        for method, op in path_item.items():
            if not isinstance(op, dict):
                continue
            desc = op.get("description", "")
            assert len(desc) <= 300, f"Operation {method} {path} description length {len(desc)} > 300: '{desc}'"

            # Check parameters
            params = op.get("parameters", [])
            param_names = [p.get("name") for p in params]
            assert "X-API-Key" not in param_names, f"X-API-Key leaked into parameters in {path}"
            assert "offset" not in param_names, f"offset leaked into parameters in {path}"


# ==============================================================================
# Tier 2: Boundary & Corner Cases — MCP Tool Input Validation
# ==============================================================================

@pytest.mark.anyio
async def test_mcp_mutate_cashflow_boundary_unbalanced_entries(
    e2e_seeded_env,
    monkeypatch
):
    """Verify mutate_cashflow raises ValueError for unbalanced transactions (sum(payments) != sum(items))."""
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", get_test_sessionmaker())

    unbalanced_op = [
        {
            "merchant": "Unbalanced Market",
            "date": "2025-06-01",
            "currency": "EUR",
            "notes": "Unbalanced payments and items",
            "payments": [{"account_name": "Checking Account", "amount": -100.00}],
            "items": [
                {
                    "category_id": 1,
                    "amount": -80.00,  # 20.00 mismatch
                    "description": "Mismatched items",
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="(?i)balance check failed"):
        await mcp_server.mutate_cashflow(unbalanced_op)


@pytest.mark.anyio
async def test_mcp_mutate_cashflow_boundary_invalid_account(
    e2e_seeded_env,
    monkeypatch
):
    """Verify mutate_cashflow raises ValueError for unknown accounts."""
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", get_test_sessionmaker())

    invalid_acc_op = [
        {
            "merchant": "Mystery Store",
            "date": "2025-06-01",
            "currency": "EUR",
            "payments": [{"account_name": "NonExistentBank", "amount": -50.00}],
            "items": [{"category_id": 1, "amount": -50.00, "description": "Goods"}],
        }
    ]
    with pytest.raises(ValueError, match="(?i)not found"):
        await mcp_server.mutate_cashflow(invalid_acc_op)


@pytest.mark.anyio
async def test_mcp_search_transactions_boundary_empty_query(
    e2e_seeded_env,
    monkeypatch
):
    """Verify search_existing_transactions handles non-matching queries gracefully returning empty list."""
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", get_test_sessionmaker())

    res = await mcp_server.search_existing_transactions(query="NON_EXISTENT_QUERY_999999")
    assert isinstance(res, list)
    assert len(res) == 0
