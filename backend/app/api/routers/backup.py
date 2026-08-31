import os
import json
import datetime
from typing import Dict, Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.database import get_db
from app.db.models import (
    Account, Asset, Transaction, PriceHistory, CorporateAction, 
    ExpectedDividend, Category, CashflowTransaction, CashflowPayment, 
    CashflowItem, AppSetting, User
)
from app.schemas.schemas import (
    BackupConfigResponse, BackupConfigUpdate, BackupListResponse, 
    BackupItemResponse, BackupCreateRequest
)
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import recalculate_past_snapshots
from app.services.backup_service import (
    get_autobackup_config, update_autobackup_config, list_backups,
    create_backup, restore_from_backup, delete_backup, ensure_backup_dir
)

router = APIRouter(prefix="/backup", tags=["backup"])

@router.get("/config", response_model=BackupConfigResponse)
async def get_backup_configuration(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns the current auto-backup configuration and active database information."""
    return await get_autobackup_config(db)

@router.put("/config", response_model=BackupConfigResponse)
async def update_backup_configuration(
    payload: BackupConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates auto-backup interval, retention max copies, and enabled state."""
    return await update_autobackup_config(
        db,
        enabled=payload.autobackup_enabled,
        interval_hours=payload.autobackup_interval_hours,
        max_copies=payload.autobackup_max_copies
    )

@router.get("/list", response_model=BackupListResponse)
async def list_stored_backups(
    current_user: User = Depends(get_current_user)
):
    """Returns a list of all stored backup snapshots with metadata."""
    items = list_backups()
    return BackupListResponse(
        total_count=len(items),
        backups=[BackupItemResponse(**item) for item in items]
    )

@router.post("/create", response_model=BackupItemResponse)
async def trigger_manual_backup(
    payload: Optional[BackupCreateRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates an immediate manual backup snapshot of the active database."""
    note = payload.note if payload else None
    res = await create_backup(db, kind="manual", note=note)
    return BackupItemResponse(**res)

@router.get("/download/{filename}")
async def download_backup_file(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Downloads a specific backup file."""
    backup_dir = ensure_backup_dir()
    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

@router.post("/restore/{filename}")
async def restore_database_from_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restores the active database from a stored backup file with pre-restore safety snapshot."""
    try:
        res = await restore_from_backup(filename, db)
        return res
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database restore failed: {str(e)}")

@router.delete("/{filename}")
async def delete_backup_snapshot(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Deletes a specific backup snapshot from storage."""
    deleted = delete_backup(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backup file not found.")
    return {"status": "success", "deleted_file": filename}

@router.get("/export")
async def export_all_portfolio_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports comprehensive system data (Accounts, Assets, Transactions, Price History, 
    Corporate Actions, Expected Dividends, Categories, Cashflows, Settings) as JSON.
    """
    accs = (await db.execute(select(Account))).scalars().all()
    asts = (await db.execute(select(Asset))).scalars().all()
    txs = (await db.execute(select(Transaction))).scalars().all()
    phs = (await db.execute(select(PriceHistory))).scalars().all()
    cas = (await db.execute(select(CorporateAction))).scalars().all()
    exp_divs = (await db.execute(select(ExpectedDividend))).scalars().all()
    cats = (await db.execute(select(Category))).scalars().all()
    c_txs = (await db.execute(select(CashflowTransaction))).scalars().all()
    c_pmts = (await db.execute(select(CashflowPayment))).scalars().all()
    c_items = (await db.execute(select(CashflowItem))).scalars().all()
    app_sets = (await db.execute(select(AppSetting))).scalars().all()

    export_data = {
        "version": "2.0",
        "exported_at": datetime.datetime.utcnow().isoformat(),
        "accounts": [
            {
                "account_id": a.account_id,
                "account_name": a.account_name,
                "broker_name": a.broker_name,
                "account_type": a.account_type,
                "currency": a.currency,
                "default_dividend_account_id": a.default_dividend_account_id,
                "created_at": a.created_at.isoformat() if a.created_at else None
            } for a in accs
        ],
        "assets": [
            {
                "asset_id": a.asset_id,
                "symbol": a.symbol,
                "isin": a.isin,
                "name": a.name,
                "asset_type": a.asset_type,
                "exchange": a.exchange,
                "sector": a.sector,
                "industry": a.industry,
                "currency": a.currency
            } for a in asts
        ],
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "account_id": t.account_id,
                "funding_account_id": t.funding_account_id,
                "asset_id": t.asset_id,
                "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date.isoformat(),
                "quantity": t.quantity,
                "price_per_unit": t.price_per_unit,
                "total_amount": t.total_amount,
                "fees": t.fees,
                "taxes": t.taxes,
                "source": t.source,
                "expected_dividend_id": t.expected_dividend_id,
                "notes": t.notes
            } for t in txs
        ],
        "price_history": [
            {
                "price_id": p.price_id,
                "asset_id": p.asset_id,
                "price_date": p.price_date.isoformat(),
                "close_price": p.close_price,
                "source": p.source
            } for p in phs
        ],
        "corporate_actions": [
            {
                "action_id": c.action_id,
                "asset_id": c.asset_id,
                "action_type": c.action_type,
                "action_date": c.action_date.isoformat(),
                "ratio": c.ratio,
                "notes": c.notes
            } for c in cas
        ],
        "expected_dividends": [
            {
                "expected_dividend_id": ed.expected_dividend_id,
                "asset_id": ed.asset_id,
                "account_id": ed.account_id,
                "ex_date": ed.ex_date.isoformat() if ed.ex_date else None,
                "pay_date": ed.pay_date.isoformat() if ed.pay_date else None,
                "eligible_shares": ed.eligible_shares,
                "dividend_rate": ed.dividend_rate,
                "expected_amount": ed.expected_amount,
                "currency": ed.currency,
                "source": ed.source,
                "matched_transaction_id": ed.matched_transaction_id,
                "status": ed.status
            } for ed in exp_divs
        ],
        "categories": [
            {
                "category_id": cat.category_id,
                "name": cat.name,
                "category_type": cat.category_type,
                "default_label": cat.default_label,
                "parent_id": cat.parent_id,
                "icon": cat.icon,
                "color": cat.color
            } for cat in cats
        ],
        "cashflow_transactions": [
            {
                "cashflow_id": ct.cashflow_id,
                "transaction_date": ct.transaction_date.isoformat(),
                "title": ct.title,
                "total_amount": ct.total_amount,
                "currency": ct.currency,
                "transaction_kind": ct.transaction_kind,
                "notes": ct.notes
            } for ct in c_txs
        ],
        "cashflow_payments": [
            {
                "payment_id": cp.payment_id,
                "cashflow_id": cp.cashflow_id,
                "account_id": cp.account_id,
                "amount": cp.amount
            } for cp in c_pmts
        ],
        "cashflow_items": [
            {
                "item_id": ci.item_id,
                "cashflow_id": ci.cashflow_id,
                "category_id": ci.category_id,
                "amount": ci.amount,
                "label": ci.label,
                "description": ci.description
            } for ci in c_items
        ],
        "app_settings": [
            {
                "key": s.key,
                "value": s.value
            } for s in app_sets
        ]
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=greenline_full_backup_{datetime.date.today().isoformat()}.json"
        }
    )
