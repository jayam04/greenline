import re
import pytest
from pathlib import Path
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ==============================================================================
# Tier 4: Real-World Scenarios — End-to-End AI Assistant Financial Session
# ==============================================================================

@pytest.mark.anyio
async def test_real_world_ai_assistant_full_session(
    e2e_client: AsyncClient,
    e2e_primary_api_key: str,
    e2e_seeded_env
):
    """
    Simulates a comprehensive real-world external AI assistant (ChatGPT / Claude) session:
    1. AI Agent authenticates using gl_mcp_ API key
    2. AI Agent queries available ledger categories and accounts
    3. AI Agent checks recent cashflow statements
    4. AI Agent executes a monthly expense transaction (Groceries)
    5. AI Agent verifies cashflow statement was recorded
    6. AI Agent queries stock positions
    7. AI Agent executes a stock trade (BUY)
    8. AI Agent executes a stock trade (SELL) triggering FIFO engine
    9. AI Agent queries updated portfolio positions
    """
    headers = {"Authorization": f"Bearer {e2e_primary_api_key}"}

    # Step 1: AI queries available categories and accounts
    cat_res = await e2e_client.get("/api/v1/mcp/categories", headers=headers)
    assert cat_res.status_code == 200, f"Failed to get categories: {cat_res.text}"
    cat_data = cat_res.json()
    assert "categories" in cat_data
    assert "available_accounts" in cat_data

    # Map target category and account
    groceries_cat = next(c for c in cat_data["categories"] if c["name"] == "Groceries")
    checking_acc = next(a for a in cat_data["available_accounts"] if a["account_name"] == "Checking Account")
    broker_acc = next(a for a in cat_data["available_accounts"] if a["account_name"] == "Interactive Brokers")

    # Step 2: AI checks initial cashflow statements
    initial_cf = await e2e_client.get("/api/v1/mcp/cashflow?merchant=Trader+Joe", headers=headers)
    assert initial_cf.status_code == 200
    assert initial_cf.json().get("total_count") == 0

    # Step 3: AI records grocery expense via mutate_cashflow REST endpoint
    cf_mutation_payload = {
        "operations": [
            {
                "merchant": "Trader Joe's",
                "date": "2025-06-12",
                "currency": "EUR",
                "notes": "Weekly household groceries",
                "payments": [{"account_name": checking_acc["account_name"], "amount": -78.45}],
                "items": [
                    {
                        "category_id": groceries_cat["category_id"],
                        "amount": -78.45,
                        "description": "Produce and dairy",
                        "label": "ESSENTIAL",
                    }
                ],
            }
        ]
    }
    cf_mut_res = await e2e_client.post("/api/v1/mcp/cashflow", headers=headers, json=cf_mutation_payload)
    assert cf_mut_res.status_code == 200, f"Cashflow mutation failed: {cf_mut_res.text}"

    # Step 4: AI verifies cashflow was recorded
    cf_verify = await e2e_client.get("/api/v1/mcp/cashflow?merchant=Trader+Joe", headers=headers)
    assert cf_verify.status_code == 200
    statements = cf_verify.json().get("statements", [])
    assert len(statements) == 1
    assert statements[0]["merchant"] == "Trader Joe's"
    assert statements[0]["total_amount"] == -78.45

    # Step 5: AI queries stocks endpoint
    stocks_before = await e2e_client.get("/api/v1/mcp/stocks", headers=headers)
    assert stocks_before.status_code == 200
    assert "available_accounts" in stocks_before.json()

    # Step 6: AI buys 5 shares of NVDA
    buy_stock_payload = {
        "operations": [
            {
                "account_name": broker_acc["account_name"],
                "symbol": "NVDA",
                "transaction_type": "buy",
                "date": "2025-06-15",
                "quantity": 5.0,
                "price_per_unit": 130.0,
                "fees": 1.50,
                "taxes": 0.0,
                "notes": "AI-initiated monthly investment",
            }
        ]
    }
    buy_res = await e2e_client.post("/api/v1/mcp/stocks", headers=headers, json=buy_stock_payload)
    assert buy_res.status_code == 200, f"Stock BUY failed: {buy_res.text}"

    # Step 7: AI verifies NVDA transaction was recorded
    stocks_after_buy = await e2e_client.get("/api/v1/mcp/stocks?asset=NVDA", headers=headers)
    assert stocks_after_buy.status_code == 200
    txs_buy = stocks_after_buy.json().get("transactions", [])
    assert any(t["transaction_type"] == "buy" and t["quantity"] == 5.0 for t in txs_buy)

    # Step 8: AI sells 2 shares of NVDA
    sell_stock_payload = {
        "operations": [
            {
                "account_name": broker_acc["account_name"],
                "symbol": "NVDA",
                "transaction_type": "sell",
                "date": "2025-06-25",
                "quantity": 2.0,
                "price_per_unit": 140.0,
                "fees": 1.50,
                "taxes": 0.0,
                "notes": "AI profit taking",
            }
        ]
    }
    sell_res = await e2e_client.post("/api/v1/mcp/stocks", headers=headers, json=sell_stock_payload)
    assert sell_res.status_code == 200, f"Stock SELL failed: {sell_res.text}"

    # Step 9: AI verifies portfolio reflects both trades
    stocks_final = await e2e_client.get("/api/v1/mcp/stocks?asset=NVDA", headers=headers)
    assert stocks_final.status_code == 200
    txs_final = stocks_final.json().get("transactions", [])
    assert len(txs_final) == 2


# ==============================================================================
# Tier 4: Real-World Scenarios — Cleanliness & Architectural Invariant Audit
# ==============================================================================

def test_real_world_frontend_cleanliness_audit():
    """Verify complete absence of AI Import frontend assets and links."""
    # 1. Route directory deleted
    import_dir = PROJECT_ROOT / "frontend" / "src" / "app" / "import"
    assert not import_dir.exists(), "frontend/src/app/import directory must be deleted"

    # 2. Test file deleted
    workbench_test = PROJECT_ROOT / "frontend" / "src" / "__tests__" / "ImportWorkbench.test.tsx"
    assert not workbench_test.exists(), "frontend/src/__tests__/ImportWorkbench.test.tsx must be deleted"

    # 3. Sidebar clean
    sidebar_file = PROJECT_ROOT / "frontend" / "src" / "components" / "Sidebar.tsx"
    assert sidebar_file.exists()
    sidebar_text = sidebar_file.read_text(encoding="utf-8")
    assert "AI Import" not in sidebar_text
    assert "Sparkles" not in sidebar_text

    # 4. Zero links to /import across all frontend TSX files
    link_regex = re.compile(r'href=[\'"][/]import[\'"]')
    for tsx_file in (PROJECT_ROOT / "frontend" / "src").rglob("*.tsx"):
        content = tsx_file.read_text(encoding="utf-8")
        assert not link_regex.search(content), f"Found link to /import in {tsx_file}"


def test_real_world_backend_cleanliness_audit():
    """Verify complete absence of backend AI Import router, pipelines, and dead imports."""
    # 1. Router module deleted
    import_router_file = PROJECT_ROOT / "backend" / "app" / "api" / "routers" / "import_router.py"
    assert not import_router_file.exists(), "backend/app/api/routers/import_router.py must be deleted"

    # 2. Schema module deleted
    import_schemas_file = PROJECT_ROOT / "backend" / "app" / "schemas" / "import_schemas.py"
    assert not import_schemas_file.exists(), "backend/app/schemas/import_schemas.py must be deleted"

    # 3. Services AI directory deleted
    ai_dir = PROJECT_ROOT / "backend" / "app" / "services" / "ai"
    assert not ai_dir.exists(), "backend/app/services/ai directory must be deleted"

    # 4. Obsolete backend test files deleted
    test_import_and_mcp = PROJECT_ROOT / "backend" / "tests" / "test_import_router_and_mcp.py"
    assert not test_import_and_mcp.exists(), "backend/tests/test_import_router_and_mcp.py must be deleted"

    test_ai_staging = PROJECT_ROOT / "backend" / "tests" / "test_ai_staging_and_matcher.py"
    assert not test_ai_staging.exists(), "backend/tests/test_ai_staging_and_matcher.py must be deleted"

    # 5. main.py has no import_router
    main_file = PROJECT_ROOT / "backend" / "app" / "main.py"
    main_text = main_file.read_text(encoding="utf-8")
    assert "import_router" not in main_text, "backend/app/main.py must not reference import_router"

    # 6. server.py has no app.services.ai or staging models
    server_file = PROJECT_ROOT / "backend" / "app" / "mcp" / "server.py"
    server_text = server_file.read_text(encoding="utf-8")
    assert "app.services.ai" not in server_text, "backend/app/mcp/server.py must not import app.services.ai"
    assert "ImportBatch" not in server_text, "backend/app/mcp/server.py must not reference ImportBatch"
    assert "StagedRecord" not in server_text, "backend/app/mcp/server.py must not reference StagedRecord"

    # 7. requirements.txt does not contain pypdf or openpyxl
    reqs_file = PROJECT_ROOT / "backend" / "requirements.txt"
    reqs_text = reqs_file.read_text(encoding="utf-8")
    assert "pypdf" not in reqs_text, "backend/requirements.txt must not contain pypdf"
    assert "openpyxl" not in reqs_text, "backend/requirements.txt must not contain openpyxl"
