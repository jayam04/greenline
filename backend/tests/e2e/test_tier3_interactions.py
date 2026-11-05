import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Asset,
    Transaction,
    Lot,
    LotSale,
    CashflowTransaction,
    CashflowPayment,
    CashflowItem,
)
import app.mcp.server as mcp_server
from conftest import get_test_sessionmaker


# ==============================================================================
# Tier 3: Cross-Feature Interactions — Direct MCP Ledger Persistence
# ==============================================================================

@pytest.mark.anyio
async def test_mcp_cashflow_persistence_direct_no_staging(
    e2e_session: AsyncSession,
    e2e_seeded_env,
    monkeypatch
):
    """
    Verify cashflow mutations via MCP tool persist directly to core domain tables
    (CashflowTransaction, CashflowPayment, CashflowItem) without touching or requiring staging.
    """
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", get_test_sessionmaker())

    op = [
        {
            "merchant": "Bistro Central",
            "date": "2025-06-15",
            "currency": "EUR",
            "notes": "Dinner with colleagues",
            "payments": [{"account_name": "Checking Account", "amount": -85.00}],
            "items": [
                {
                    "category_id": 1,
                    "amount": -85.00,
                    "description": "Team dinner",
                    "label": "DISCRETIONARY",
                }
            ],
        }
    ]

    res = await mcp_server.mutate_cashflow(op)
    assert res.get("status") == "success"
    assert len(res.get("results", [])) == 1

    # Verify directly in core database tables
    stmt = select(CashflowTransaction).where(CashflowTransaction.title == "Bistro Central")
    db_tx = (await e2e_session.execute(stmt)).scalar_one_or_none()
    assert db_tx is not None, "CashflowTransaction must be persisted in database"
    assert abs(db_tx.total_amount) == 85.00

    pmt_stmt = select(CashflowPayment).where(CashflowPayment.cashflow_id == db_tx.cashflow_id)
    payments = (await e2e_session.execute(pmt_stmt)).scalars().all()
    assert len(payments) == 1
    assert payments[0].amount == -85.00

    item_stmt = select(CashflowItem).where(CashflowItem.cashflow_id == db_tx.cashflow_id)
    items = (await e2e_session.execute(item_stmt)).scalars().all()
    assert len(items) == 1
    assert abs(items[0].amount) == 85.00

    # Verify read_cashflows tool retrieves the persisted record
    read_res = await mcp_server.read_cashflows(merchant="Bistro")
    assert read_res["count"] == 1
    assert read_res["statements"][0]["merchant"] == "Bistro Central"
    assert read_res["statements"][0]["total_amount"] == -85.00


@pytest.mark.anyio
async def test_mcp_stock_persistence_and_fifo_snapshots(
    e2e_session: AsyncSession,
    e2e_seeded_env,
    monkeypatch
):
    """
    Verify stock transactions mutate directly into Transaction & Asset tables,
    triggering FIFO lot recalculation and snapshot generation cleanly.
    """
    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", get_test_sessionmaker())

    # 1. Buy 10 MSFT with force_create_asset=True
    buy_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "MSFT",
            "transaction_type": "buy",
            "date": "2025-06-10",
            "quantity": 10.0,
            "price_per_unit": 400.0,
            "fees": 2.0,
            "taxes": 0.0,
            "notes": "E2E AI Buy MSFT",
            "force_create_asset": True,
        }
    ]
    buy_res = await mcp_server.mutate_stock_transactions(buy_op)
    assert buy_res.get("status") == "success"

    # Verify Asset created
    asset_stmt = select(Asset).where(Asset.symbol == "MSFT")
    msft_asset = (await e2e_session.execute(asset_stmt)).scalar_one_or_none()
    assert msft_asset is not None, "MSFT asset should be auto-created"

    # Verify Transaction created
    tx_stmt = select(Transaction).where(Transaction.asset_id == msft_asset.asset_id)
    txs = (await e2e_session.execute(tx_stmt)).scalars().all()
    assert len(txs) == 1
    assert txs[0].transaction_type == "buy"
    assert txs[0].quantity == 10.0

    # 2. Sell 4 MSFT
    sell_op = [
        {
            "account_name": "Interactive Brokers",
            "symbol": "MSFT",
            "transaction_type": "sell",
            "date": "2025-06-20",
            "quantity": 4.0,
            "price_per_unit": 420.0,
            "fees": 1.0,
            "taxes": 0.0,
            "notes": "E2E AI Sell MSFT",
        }
    ]
    sell_res = await mcp_server.mutate_stock_transactions(sell_op)
    assert sell_res.get("status") == "success"

    # Verify FIFO lots updated
    lot_stmt = select(Lot).where(Lot.asset_id == msft_asset.asset_id)
    lot = (await e2e_session.execute(lot_stmt)).scalar_one_or_none()
    assert lot is not None
    assert lot.quantity_remaining == 6.0  # 10 - 4

    # Verify read_stock_transactions reflects both trades
    read_stocks = await mcp_server.read_stock_transactions(asset="MSFT")
    assert len(read_stocks["transactions"]) == 2


# ==============================================================================
# Tier 3: Cross-Feature Interactions — Backup Import Preservation
# ==============================================================================

@pytest.mark.anyio
async def test_backup_import_preservation(
    e2e_client: AsyncClient,
    e2e_primary_api_key: str,
    e2e_seeded_env
):
    """
    Verify portfolio JSON backup export & import (/api/v1/backup/export and /api/v1/backup/import)
    are fully functional and distinct from the removed /api/v1/import router.
    """
    import json
    headers = {"Authorization": f"Bearer {e2e_primary_api_key}"}

    # 1. Export backup JSON
    export_res = await e2e_client.get("/api/v1/backup/export", headers=headers)
    assert export_res.status_code == 200, f"Backup export failed: {export_res.text}"
    backup_data = export_res.json()
    assert "version" in backup_data or "accounts" in backup_data or "data" in backup_data

    # 2. Re-import backup JSON via /api/v1/backup/import (multipart file upload)
    backup_bytes = json.dumps(backup_data).encode("utf-8")
    files = {"file": ("backup.json", backup_bytes, "application/json")}

    import_res = await e2e_client.post(
        "/api/v1/backup/import",
        headers=headers,
        files=files
    )
    assert import_res.status_code == 200, f"Portfolio backup import failed: {import_res.text}"


# ==============================================================================
# Tier 3: Cross-Feature Interactions — Multi-User API Key Tenant Isolation
# ==============================================================================

@pytest.mark.anyio
async def test_mcp_multi_user_api_key_isolation(
    e2e_client: AsyncClient,
    e2e_primary_api_key: str,
    e2e_secondary_api_key: str,
    e2e_seeded_env
):
    """
    Verify strict multi-user API key isolation:
    - User 1's API keys are not visible to User 2
    - User 2 cannot revoke or access User 1's API keys
    """
    u1_headers = {"Authorization": f"Bearer {e2e_primary_api_key}"}
    u2_headers = {"Authorization": f"Bearer {e2e_secondary_api_key}"}

    # 1. User 1 lists API keys
    u1_res = await e2e_client.get("/api/v1/auth/api-keys", headers=u1_headers)
    assert u1_res.status_code == 200
    u1_keys = u1_res.json()
    assert len(u1_keys) >= 1
    u1_key_id = u1_keys[0]["key_id"]

    # 2. User 2 lists API keys: must NOT include User 1's key
    u2_res = await e2e_client.get("/api/v1/auth/api-keys", headers=u2_headers)
    assert u2_res.status_code == 200
    u2_keys = u2_res.json()
    assert not any(k["key_id"] == u1_key_id for k in u2_keys), "User 2 leaked User 1's API key"

    # 3. User 2 attempts to delete User 1's API key: must return 404
    del_res = await e2e_client.delete(f"/api/v1/auth/api-keys/{u1_key_id}", headers=u2_headers)
    assert del_res.status_code == 404, f"Expected 404 when User 2 deletes User 1's key, got {del_res.status_code}"
