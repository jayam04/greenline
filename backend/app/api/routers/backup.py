import datetime
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import json
from app.db.database import get_db
from app.db.models import (
    Account, Asset, Transaction, PriceHistory, CorporateAction, Dividend, User
)
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import recalculate_past_snapshots

router = APIRouter(prefix="/backup", tags=["backup"])

@router.get("/export")
async def export_portfolio_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports all portfolio data (Accounts, Assets, Transactions, Price History, Corporate Actions, Dividends) as JSON.
    """
    accs_res = await db.execute(select(Account))
    accs = accs_res.scalars().all()

    asts_res = await db.execute(select(Asset))
    asts = asts_res.scalars().all()

    txs_res = await db.execute(select(Transaction))
    txs = txs_res.scalars().all()

    phs_res = await db.execute(select(PriceHistory))
    phs = phs_res.scalars().all()

    cas_res = await db.execute(select(CorporateAction))
    cas = cas_res.scalars().all()

    divs_res = await db.execute(select(Dividend))
    divs = divs_res.scalars().all()

    export_data = {
        "version": "1.0",
        "exported_at": datetime.datetime.utcnow().isoformat(),
        "accounts": [
            {
                "account_id": a.account_id,
                "account_name": a.account_name,
                "broker_name": a.broker_name,
                "account_type": a.account_type,
                "currency": a.currency,
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
                "currency": a.currency
            } for a in asts
        ],
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "account_id": t.account_id,
                "asset_id": t.asset_id,
                "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date.isoformat(),
                "quantity": t.quantity,
                "price_per_unit": t.price_per_unit,
                "total_amount": t.total_amount,
                "fees": t.fees,
                "taxes": t.taxes,
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
        "dividends": [
            {
                "dividend_id": d.dividend_id,
                "asset_id": d.asset_id,
                "account_id": d.account_id,
                "ex_date": d.ex_date.isoformat() if d.ex_date else None,
                "pay_date": d.pay_date.isoformat(),
                "amount_per_share": d.amount_per_share,
                "total_amount": d.total_amount,
                "tax_withheld": d.tax_withheld
            } for d in divs
        ]
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=greenline_portfolio_backup_{datetime.date.today().isoformat()}.json"
        }
    )

@router.post("/import", status_code=status.HTTP_200_OK)
async def import_portfolio_data(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Imports portfolio data from an uploaded JSON file and recalculates lots & historical snapshots.
    """
    try:
        contents = await file.read()
        data = json.loads(contents.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON backup file: {str(e)}")

    if not isinstance(data, dict) or "accounts" not in data or "transactions" not in data:
        raise HTTPException(status_code=400, detail="Invalid portfolio backup format. Missing accounts/transactions.")

    # 1. Clear existing transactional & master data
    db.expire_all()
    await db.execute(delete(Transaction))
    await db.execute(delete(Asset))
    await db.execute(delete(Account))
    await db.execute(delete(PriceHistory))
    await db.execute(delete(CorporateAction))
    await db.commit()

    account_id_map: Dict[int, int] = {}
    asset_id_map: Dict[int, int] = {}

    # 2. Insert Accounts
    for acc in data.get("accounts", []):
        c_date = datetime.date.fromisoformat(acc["created_at"]) if acc.get("created_at") else datetime.date.today()
        new_acc = Account(
            account_name=acc["account_name"],
            broker_name=acc.get("broker_name"),
            account_type=acc["account_type"],
            currency=acc.get("currency", "USD"),
            created_at=c_date
        )
        db.add(new_acc)
        await db.flush()
        if "account_id" in acc:
            account_id_map[acc["account_id"]] = new_acc.account_id

    # 3. Insert Assets
    for ast in data.get("assets", []):
        new_ast = Asset(
            symbol=ast["symbol"].upper().strip(),
            isin=ast.get("isin"),
            name=ast["name"],
            asset_type=ast["asset_type"],
            exchange=ast.get("exchange"),
            sector=ast.get("sector"),
            currency=ast.get("currency", "USD")
        )
        db.add(new_ast)
        await db.flush()
        if "asset_id" in ast:
            asset_id_map[ast["asset_id"]] = new_ast.asset_id

    # 4. Insert Transactions
    earliest_tx_date: Optional[datetime.date] = None

    for tx in data.get("transactions", []):
        t_date = datetime.date.fromisoformat(tx["transaction_date"])
        if earliest_tx_date is None or t_date < earliest_tx_date:
            earliest_tx_date = t_date

        mapped_acc_id = account_id_map.get(tx["account_id"], tx["account_id"])
        mapped_ast_id = asset_id_map.get(tx["asset_id"]) if tx.get("asset_id") else None

        new_tx = Transaction(
            account_id=mapped_acc_id,
            asset_id=mapped_ast_id,
            transaction_type=tx["transaction_type"],
            transaction_date=t_date,
            quantity=tx.get("quantity"),
            price_per_unit=tx.get("price_per_unit"),
            total_amount=tx["total_amount"],
            fees=tx.get("fees", 0.0),
            taxes=tx.get("taxes", 0.0),
            notes=tx.get("notes")
        )
        db.add(new_tx)

    # 5. Insert Price History
    for ph in data.get("price_history", []):
        mapped_ast_id = asset_id_map.get(ph["asset_id"])
        if mapped_ast_id:
            db.add(PriceHistory(
                asset_id=mapped_ast_id,
                price_date=datetime.date.fromisoformat(ph["price_date"]),
                close_price=ph["close_price"],
                source=ph.get("source", "manual")
            ))

    await db.commit()

    # 6. Recalculate FIFO lots & snapshots back to earliest transaction date
    await recalculate_all_lots(db)

    if earliest_tx_date:
        await update_prices_for_assets(db, start_date=earliest_tx_date)
        await recalculate_past_snapshots(db, start_date=earliest_tx_date)
    else:
        await recalculate_past_snapshots(db, start_date=datetime.date.today())

    return {
        "message": "Portfolio backup imported successfully.",
        "imported": {
            "accounts": len(data.get("accounts", [])),
            "assets": len(data.get("assets", [])),
            "transactions": len(data.get("transactions", []))
        }
    }
