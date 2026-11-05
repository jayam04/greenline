import datetime
import pytest

from app.db.models import User, Account, Category, Asset, Transaction
from conftest import get_test_sessionmaker
import app.mcp.server as mcp_server


@pytest.fixture
async def seeded_test_env():
    """Seed base reference data (user, accounts, categories, assets) for MCP tool tests."""
    TestSession = get_test_sessionmaker()

    async with TestSession() as session:
        # Seed test user
        user = await session.get(User, 1)
        if not user:
            user = User(user_id=1, username="test_mcp_user", password_hash="hash")
            session.add(user)

        # Seed accounts
        broker_acc = Account(
            account_id=1,
            account_name="Interactive Brokers",
            account_type="demat",
            currency="USD",
        )
        wallet_acc = Account(
            account_id=2,
            account_name="Splitwise",
            account_type="wallet",
            currency="EUR",
        )
        session.add_all([broker_acc, wallet_acc])

        # Seed categories
        groceries_cat = Category(
            category_id=1,
            name="Groceries",
            category_type="EXPENSE",
            default_label="ESSENTIAL",
        )
        salary_cat = Category(
            category_id=2,
            name="Salary",
            category_type="INCOME",
            default_label="INVESTMENT",
        )
        session.add_all([groceries_cat, salary_cat])

        # Seed asset
        asset_nvda = Asset(
            asset_id=1,
            symbol="NVDA",
            name="NVIDIA Corporation",
            asset_type="EQUITY",
            currency="USD",
            exchange="NASDAQ",
        )
        session.add(asset_nvda)

        await session.commit()

    return TestSession


@pytest.mark.anyio
async def test_mcp_server_tools_direct(seeded_test_env, monkeypatch):
    """Verify that all direct FastMCP tools function properly without staging dependencies."""
    TestSession = seeded_test_env
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", TestSession)

    # 1. get_ledger_context
    context = await mcp_server.get_ledger_context()
    assert "accounts" in context
    assert "categories" in context
    assert "assets" in context
    assert any(a["name"] == "Interactive Brokers" for a in context["accounts"])
    assert any(c["name"] == "Groceries" for c in context["categories"])
    assert any(ast["symbol"] == "NVDA" for ast in context["assets"])

    # 2. search_existing_transactions
    txs = await mcp_server.search_existing_transactions()
    assert isinstance(txs, list)

    # 3. read_categories
    cats_data = await mcp_server.read_categories()
    assert "categories" in cats_data
    assert "available_accounts" in cats_data
    assert any(c["category_id"] == 1 for c in cats_data["categories"])
    assert any(a["account_name"] == "Splitwise" for a in cats_data["available_accounts"])

    # 4. mutate_cashflow (direct transaction creation with negative amount for expense)
    cashflow_op = [
        {
            "merchant": "Whole Foods Market",
            "date": "2025-06-01",
            "currency": "EUR",
            "notes": "Weekly groceries",
            "payments": [{"account_name": "Splitwise", "amount": -65.50}],
            "items": [
                {
                    "category_id": 1,
                    "amount": -65.50,
                    "description": "Organic vegetables and fruits",
                    "label": "ESSENTIAL",
                }
            ],
        }
    ]
    mutate_res = await mcp_server.mutate_cashflow(cashflow_op)
    assert mutate_res["status"] == "success"
    assert len(mutate_res["results"]) == 1
    assert mutate_res["results"][0]["merchant"] == "Whole Foods Market"

    # 5. read_cashflows
    cf_read = await mcp_server.read_cashflows(merchant="Whole Foods")
    assert cf_read["count"] == 1
    assert cf_read["statements"][0]["merchant"] == "Whole Foods Market"
    assert cf_read["statements"][0]["total_amount"] == -65.50
    assert cf_read["statements"][0]["transaction_kind"] == "EXPENSE"

    # 6. read_stock_transactions
    stock_read_before = await mcp_server.read_stock_transactions()
    assert "transactions" in stock_read_before
    assert "available_assets" in stock_read_before
    assert "available_accounts" in stock_read_before
    assert any(a["symbol"] == "NVDA" for a in stock_read_before["available_assets"])

    # 7. mutate_stock_transactions
    stock_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "NVDA",
            "transaction_type": "buy",
            "date": "2025-06-02",
            "quantity": 10.0,
            "price_per_unit": 120.0,
            "fees": 5.0,
            "taxes": 0.0,
            "notes": "AI-initiated buy order",
        }
    ]
    stock_mutate_res = await mcp_server.mutate_stock_transactions(stock_op)
    assert stock_mutate_res["status"] == "success"
    assert len(stock_mutate_res["results"]) == 1
    assert stock_mutate_res["results"][0]["asset"] == "NVDA"
    assert stock_mutate_res["results"][0]["amount"] == 1205.0  # 10*120 + 5 fees

    # Verify transaction in read_stock_transactions
    stock_read_after = await mcp_server.read_stock_transactions(asset="NVDA")
    assert len(stock_read_after["transactions"]) >= 1
    assert stock_read_after["transactions"][0]["asset_symbol"] == "NVDA"
    assert stock_read_after["transactions"][0]["quantity"] == 10.0


@pytest.mark.anyio
async def test_mutate_cashflow_validations_and_deletion(seeded_test_env, monkeypatch):
    """Test validation rules (generic merchant, balance check, missing account) and deletion in mutate_cashflow."""
    TestSession = seeded_test_env
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", TestSession)

    # 1. Generic merchant name rejection
    with pytest.raises(ValueError, match="Invalid merchant"):
        await mcp_server.mutate_cashflow([
            {
                "merchant": "expense",
                "payments": [{"account_name": "Splitwise", "amount": -10.0}],
                "items": [{"category_id": 1, "amount": -10.0}],
            }
        ])

    # 2. Balance check failure: sum(payments) != sum(items)
    with pytest.raises(ValueError, match="Balance check failed"):
        await mcp_server.mutate_cashflow([
            {
                "merchant": "Local Bakery",
                "payments": [{"account_name": "Splitwise", "amount": -10.0}],
                "items": [{"category_id": 1, "amount": -15.0}],
            }
        ])

    # 3. Missing account name
    with pytest.raises(ValueError, match="Account 'NonExistentBank' not found"):
        await mcp_server.mutate_cashflow([
            {
                "merchant": "Local Bakery",
                "payments": [{"account_name": "NonExistentBank", "amount": -10.0}],
                "items": [{"category_id": 1, "amount": -10.0}],
            }
        ])

    # 4. Unknown category ID
    with pytest.raises(ValueError, match="Category ID 9999 not found"):
        await mcp_server.mutate_cashflow([
            {
                "merchant": "Local Bakery",
                "payments": [{"account_name": "Splitwise", "amount": -10.0}],
                "items": [{"category_id": 9999, "amount": -10.0}],
            }
        ])

    # 5. Create and then delete a transaction
    create_res = await mcp_server.mutate_cashflow([
        {
            "merchant": "Bookstore",
            "date": "2025-06-05",
            "payments": [{"account_name": "Splitwise", "amount": -25.0}],
            "items": [{"category_id": 1, "amount": -25.0}],
        }
    ])
    created_id = create_res["results"][0]["cashflow_id"]

    # Delete the created transaction
    del_res = await mcp_server.mutate_cashflow([
        {"action": "delete", "cashflow_id": created_id}
    ])
    assert del_res["status"] == "success"

    # Confirm deletion in read_cashflows
    read_res = await mcp_server.read_cashflows(merchant="Bookstore")
    assert read_res["count"] == 0


@pytest.mark.anyio
async def test_mutate_stock_force_create_sell_and_deletion(seeded_test_env, monkeypatch):
    """Test stock mutation features: force_create_asset, sell transaction, and deletion."""
    TestSession = seeded_test_env
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", TestSession)

    # 1. Buy with force_create_asset for an unlisted asset
    buy_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "TSLA",
            "asset_name": "Tesla Inc",
            "force_create_asset": True,
            "transaction_type": "buy",
            "date": "2025-06-03",
            "quantity": 5.0,
            "price_per_unit": 200.0,
            "fees": 2.0,
            "taxes": 0.0,
            "notes": "Force-create TSLA buy",
        }
    ]
    buy_res = await mcp_server.mutate_stock_transactions(buy_op)
    assert buy_res["status"] == "success"
    assert buy_res["results"][0]["asset"] == "TSLA"
    assert buy_res["results"][0]["amount"] == 1002.0  # 5 * 200 + 2
    buy_tx_id = buy_res["results"][0]["transaction_id"]

    # 2. Sell transaction for TSLA
    sell_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "TSLA",
            "transaction_type": "sell",
            "date": "2025-06-04",
            "quantity": 2.0,
            "price_per_unit": 220.0,
            "fees": 1.0,
            "taxes": 0.0,
            "notes": "Partial sell TSLA",
        }
    ]
    sell_res = await mcp_server.mutate_stock_transactions(sell_op)
    assert sell_res["status"] == "success"
    assert sell_res["results"][0]["type"] == "sell"
    assert sell_res["results"][0]["amount"] == 439.0  # 2 * 220 - 1

    # 3. Read back transactions for TSLA
    tsla_reads = await mcp_server.read_stock_transactions(asset="TSLA")
    assert tsla_reads["total_count"] == 2

    # 4. Delete the buy transaction
    del_op = [{"action": "delete", "transaction_id": buy_tx_id}]
    del_res = await mcp_server.mutate_stock_transactions(del_op)
    assert del_res["status"] == "success"

    # 5. Historical stock transaction mutation (assert success without StaleDataError)
    hist_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "NVDA",
            "transaction_type": "buy",
            "date": "2025-01-10",
            "quantity": 5.0,
            "price_per_unit": 100.0,
            "fees": 1.0,
            "taxes": 0.0,
            "notes": "Historical backfill NVDA buy",
        }
    ]
    hist_res = await mcp_server.mutate_stock_transactions(hist_op)
    assert hist_res["status"] == "success"
    assert len(hist_res["results"]) == 1
    assert hist_res["results"][0]["asset"] == "NVDA"
    assert hist_res["results"][0]["amount"] == 501.0
    hist_tx_id = hist_res["results"][0]["transaction_id"]

    # Verify transaction persisted in database with correct historical date
    async with TestSession() as session:
        tx = await session.get(Transaction, hist_tx_id)
        assert tx is not None
        assert tx.transaction_date == datetime.date(2025, 1, 10)
        assert tx.quantity == 5.0


@pytest.mark.anyio
async def test_mcp_server_decoupled_from_staging():
    """Verify that staging tools and AI staging service imports are completely removed from mcp.server."""
    # Assert staging tools are removed from module namespace
    assert not hasattr(mcp_server, "create_staging_batch"), "create_staging_batch should be removed"
    assert not hasattr(mcp_server, "stage_transactions"), "stage_transactions should be removed"
    assert not hasattr(mcp_server, "commit_batch"), "commit_batch should be removed"

    # Assert remaining 7 tools exist on module
    expected_tools = [
        "get_ledger_context",
        "search_existing_transactions",
        "read_categories",
        "read_cashflows",
        "mutate_cashflow",
        "read_stock_transactions",
        "mutate_stock_transactions",
    ]
    for tool_name in expected_tools:
        assert hasattr(mcp_server, tool_name), f"Expected tool {tool_name} to exist on mcp_server"

    # Assert FastMCP tool manager has exactly the 7 expected direct tools
    assert hasattr(mcp_server.mcp, "_tool_manager")
    registered_tools = list(mcp_server.mcp._tool_manager._tools.keys())
    assert set(registered_tools) == set(expected_tools)
    assert "create_staging_batch" not in registered_tools
    assert "stage_transactions" not in registered_tools
    assert "commit_batch" not in registered_tools
