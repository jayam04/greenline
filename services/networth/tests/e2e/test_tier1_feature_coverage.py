import os
import re
import pytest
from pathlib import Path
from httpx import AsyncClient

from app.main import app
import app.mcp.server as mcp_server

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ==============================================================================
# Tier 1: Feature Coverage — UI & Navigation (R1)
# ==============================================================================

def test_ui_sidebar_ai_import_removed():
    """Verify that the AI Import item and unused Sparkles icon are absent from Sidebar.tsx."""
    sidebar_file = PROJECT_ROOT / "frontend" / "src" / "components" / "Sidebar.tsx"
    assert sidebar_file.exists(), "Sidebar.tsx must exist"
    content = sidebar_file.read_text(encoding="utf-8")

    # Assert "AI Import" is not in the navigation items
    assert "AI Import" not in content, "Sidebar.tsx must not contain 'AI Import'"
    assert '"/import"' not in content and "'/import'" not in content, "Sidebar.tsx must not route to '/import'"
    assert "Sparkles" not in content, "Sidebar.tsx should not import or reference Sparkles icon"


def test_ui_import_pages_and_routes_removed():
    """Verify that frontend /import route and associated workbench files are deleted."""
    import_dir = PROJECT_ROOT / "frontend" / "src" / "app" / "import"
    assert not import_dir.exists(), "frontend/src/app/import directory must be deleted"

    workbench_test = PROJECT_ROOT / "frontend" / "src" / "__tests__" / "ImportWorkbench.test.tsx"
    assert not workbench_test.exists(), "ImportWorkbench.test.tsx must be deleted"


def test_ui_no_active_links_to_import():
    """Verify no UI components contain active links or router pushes targeting /import."""
    src_dir = PROJECT_ROOT / "frontend" / "src"
    assert src_dir.exists()

    link_pattern = re.compile(r'href=[\'"][/]import[\'"]')
    push_pattern = re.compile(r'router\.push\([\'"][/]import[\'"]')

    for path in src_dir.rglob("*.tsx"):
        content = path.read_text(encoding="utf-8")
        assert not link_pattern.search(content), f"Found link to /import in {path}"
        assert not push_pattern.search(content), f"Found router.push('/import') in {path}"

    # Verify portfolio JSON backup import route remains preserved in accounts page
    accounts_page = src_dir / "app" / "accounts" / "page.tsx"
    if accounts_page.exists():
        accounts_content = accounts_page.read_text(encoding="utf-8")
        assert "/api/v1/backup/import" in accounts_content, "Portfolio JSON backup import must be preserved"


# ==============================================================================
# Tier 1: Feature Coverage — Backend API & Services (R2)
# ==============================================================================

def test_backend_import_router_unregistered():
    """Verify that /api/v1/import router is completely unregistered from FastAPI app."""
    prefixes = [
        getattr(r.original_router, "prefix", "")
        for r in app.routes
        if hasattr(r, "original_router")
    ]
    assert "/import" not in prefixes, f"Found registered /import router prefix in app: {prefixes}"


@pytest.mark.anyio
async def test_backend_import_http_endpoints_return_404(e2e_client: AsyncClient):
    """Verify all former /api/v1/import HTTP endpoints return 404 Not Found."""
    endpoints_to_test = [
        ("POST", "/api/v1/import/upload"),
        ("GET", "/api/v1/import/batches"),
        ("GET", "/api/v1/import/batches/1"),
        ("GET", "/api/v1/import/batches/1/records"),
        ("PATCH", "/api/v1/import/batches/1/records/1"),
        ("DELETE", "/api/v1/import/batches/1/records/1"),
        ("POST", "/api/v1/import/batches/1/records"),
        ("POST", "/api/v1/import/batches/1/commit"),
    ]

    for method, path in endpoints_to_test:
        res = await e2e_client.request(method, path)
        assert res.status_code == 404, f"Expected 404 for removed endpoint {method} {path}, got {res.status_code}"


# ==============================================================================
# Tier 1: Feature Coverage — FastMCP Server & Direct Tools (R3)
# ==============================================================================

def test_fastmcp_server_loads_cleanly():
    """Verify FastMCP server instance loads without module or runtime errors."""
    assert hasattr(mcp_server, "mcp"), "mcp_server must instantiate FastMCP server object 'mcp'"


def test_fastmcp_server_seven_direct_tools():
    """Verify all 7 direct transactional/ledger tools exist and staging tools are removed."""
    expected_direct_tools = [
        "get_ledger_context",
        "search_existing_transactions",
        "read_categories",
        "read_cashflows",
        "mutate_cashflow",
        "read_stock_transactions",
        "mutate_stock_transactions",
    ]
    for tool_name in expected_direct_tools:
        assert hasattr(mcp_server, tool_name), f"Direct tool {tool_name} must exist on mcp_server"

    removed_staging_tools = [
        "create_staging_batch",
        "stage_transactions",
        "commit_batch",
    ]
    for tool_name in removed_staging_tools:
        assert not hasattr(mcp_server, tool_name), f"Staging tool {tool_name} must be removed from mcp_server"


# ==============================================================================
# Tier 1: Feature Coverage — MCP REST & OpenAPI Specifications (R3)
# ==============================================================================

@pytest.mark.anyio
async def test_mcp_openapi_spec_compliance(e2e_client: AsyncClient):
    """
    Verify /openapi.json and /api/v1/mcp/openapi.json conform to:
    - Publicly accessible without authentication
    - OpenAPI 3.1.0 specification
    - Exposed paths limited strictly to /api/v1/mcp/{categories, cashflow, stocks}
    - No /api/v1/import or non-mcp routes
    - ChatGPT Actions description limit <= 300 characters
    """
    for endpoint in ["/openapi.json", "/api/v1/mcp/openapi.json"]:
        res = await e2e_client.get(endpoint)
        assert res.status_code == 200, f"Endpoint {endpoint} must be publicly accessible without auth"
        spec = res.json()

        assert spec.get("openapi") == "3.1.0", f"OpenAPI version must be 3.1.0 in {endpoint}"
        paths = spec.get("paths", {})

        # Verify only MCP paths are exposed
        for p in paths.keys():
            assert p.startswith("/api/v1/mcp/"), f"Unexpected path {p} exposed in MCP OpenAPI spec"
            assert "import" not in p, f"Import path {p} must not appear in MCP OpenAPI spec"

        # Verify operation descriptions <= 300 characters for ChatGPT Actions
        for path_name, path_item in paths.items():
            for method, op in path_item.items():
                if isinstance(op, dict):
                    desc = op.get("description", "")
                    assert len(desc) <= 300, (
                        f"Description for {method.upper()} {path_name} exceeds 300 chars ({len(desc)} chars): '{desc}'"
                    )


@pytest.mark.anyio
async def test_mcp_api_key_auth(e2e_client: AsyncClient, e2e_primary_api_key: str):
    """Verify MCP endpoints can authenticate via X-API-Key and Authorization: Bearer."""
    raw_key = e2e_primary_api_key

    # Authenticate via X-API-Key header
    res_x = await e2e_client.get("/api/v1/mcp/categories", headers={"X-API-Key": raw_key})
    assert res_x.status_code == 200, f"X-API-Key authentication failed: {res_x.text}"
    body_x = res_x.json()
    assert "categories" in body_x
    assert "available_accounts" in body_x

    # Authenticate via Authorization: Bearer header
    res_bearer = await e2e_client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {raw_key}"})
    assert res_bearer.status_code == 200, f"Bearer authentication failed: {res_bearer.text}"
