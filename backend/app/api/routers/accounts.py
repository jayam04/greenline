from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Account, User, Transaction, CashflowTransaction, CashflowPayment, CashflowItem, Lot, PriceHistory
from app.schemas.schemas import AccountCreate, AccountUpdate, AccountResponse
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.cashflow_engine import resolve_transaction_kind

router = APIRouter(prefix="/accounts", tags=["accounts"])

async def calculate_all_account_cash_balances(db: AsyncSession) -> Dict[int, float]:
    """
    Computes pure uninvested liquid cash for every account.
    """
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()
    cash_balances = {a.account_id: 0.0 for a in accounts}

    # 1. Investment transactions cash movements
    tx_stmt = select(Transaction)
    tx_res = await db.execute(tx_stmt)
    for tx in tx_res.scalars().all():
        ttype = (tx.transaction_type or "").lower()
        qty = float(tx.quantity or 0.0)
        ppu = float(tx.price_per_unit or 0.0)
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)

        cash_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
        if cash_acc_id in cash_balances:
            if ttype == "buy":
                trade_cash = (qty * ppu + fees + taxes) if (qty > 0 and ppu > 0) else amt
                cash_balances[cash_acc_id] -= trade_cash
            elif ttype == "sell":
                trade_cash = (qty * ppu - fees - taxes) if (qty > 0 and ppu > 0) else amt
                cash_balances[cash_acc_id] += max(0.0, trade_cash)
            elif ttype in ["dividend", "interest"]:
                trade_cash = (amt - taxes) if ttype == "dividend" else amt
                cash_balances[cash_acc_id] += max(0.0, trade_cash)
            elif ttype == "deposit":
                cash_balances[cash_acc_id] += amt
            elif ttype in ["withdrawal", "fee"]:
                cash_balances[cash_acc_id] -= amt

    # 2. Cashflow payments
    c_stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category),
        selectinload(CashflowTransaction.payments)
    )
    c_res = await db.execute(c_stmt)
    for ctx in c_res.scalars().all():
        for p in ctx.payments:
            if p.account_id in cash_balances:
                cash_balances[p.account_id] += float(p.amount or 0.0)

    return {k: round(v, 2) for k, v in cash_balances.items()}

async def calculate_all_account_balances(db: AsyncSession) -> Dict[int, float]:
    """
    Computes total valuation (cash + open securities) for every account as a float dict.
    """
    cash_balances = await calculate_all_account_cash_balances(db)
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()
    
    securities_values = {a.account_id: 0.0 for a in accounts}

    # Securities valuation for open lots
    lot_stmt = select(Lot).where(Lot.quantity_remaining > 0)
    lot_res = await db.execute(lot_stmt)
    open_lots = lot_res.scalars().all()

    if open_lots:
        asset_ids = list(set(l.asset_id for l in open_lots))
        latest_prices: Dict[int, float] = {}
        for aid in asset_ids:
            ph_stmt = select(PriceHistory.close_price).where(PriceHistory.asset_id == aid).order_by(desc(PriceHistory.price_date)).limit(1)
            ph_res = await db.execute(ph_stmt)
            p = ph_res.scalar_one_or_none()
            if p is not None:
                latest_prices[aid] = float(p)

        for lot in open_lots:
            acc_id = lot.account_id
            if acc_id in securities_values:
                unit_price = latest_prices.get(lot.asset_id, float(lot.cost_per_unit or 0.0))
                securities_values[acc_id] += float(lot.quantity_remaining) * unit_price

    total_balances = {}
    for a in accounts:
        aid = a.account_id
        c_bal = cash_balances.get(aid, 0.0)
        s_val = securities_values.get(aid, 0.0)
        total_balances[aid] = round(c_bal + s_val, 2)

    return total_balances

async def calculate_all_account_details(db: AsyncSession) -> Dict[int, Dict[str, float]]:
    """
    Computes detailed cash_balance, securities_value, and current_balance dict for every account.
    """
    cash_balances = await calculate_all_account_cash_balances(db)
    total_balances = await calculate_all_account_balances(db)

    results = {}
    for aid, tot in total_balances.items():
        c_bal = cash_balances.get(aid, 0.0)
        s_val = round(tot - c_bal, 2)
        results[aid] = {
            "cash_balance": c_bal,
            "securities_value": s_val,
            "current_balance": tot
        }
    return results

@router.get("", response_model=List[AccountResponse])
@router.get("/", response_model=List[AccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Account)
    res = await db.execute(stmt)
    accounts = res.scalars().all()
    details = await calculate_all_account_details(db)

    results = []
    for a in accounts:
        resp = AccountResponse.model_validate(a)
        d = details.get(a.account_id, {"cash_balance": 0.0, "securities_value": 0.0, "current_balance": 0.0})
        resp.cash_balance = d["cash_balance"]
        resp.securities_value = d["securities_value"]
        resp.current_balance = d["current_balance"]
        results.append(resp)

    return results

@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_in: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    account = Account(**account_in.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    resp = AccountResponse.model_validate(account)
    resp.current_balance = 0.0
    resp.cash_balance = 0.0
    resp.securities_value = 0.0
    return resp

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Account).where(Account.account_id == account_id)
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    details = await calculate_all_account_details(db)
    d = details.get(account.account_id, {"cash_balance": 0.0, "securities_value": 0.0, "current_balance": 0.0})
    resp = AccountResponse.model_validate(account)
    resp.cash_balance = d["cash_balance"]
    resp.securities_value = d["securities_value"]
    resp.current_balance = d["current_balance"]
    return resp

@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    account_in: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Account).where(Account.account_id == account_id)
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    update_data = account_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(account, field, val)

    await db.commit()
    await db.refresh(account)
    details = await calculate_all_account_details(db)
    d = details.get(account.account_id, {"cash_balance": 0.0, "securities_value": 0.0, "current_balance": 0.0})
    resp = AccountResponse.model_validate(account)
    resp.cash_balance = d["cash_balance"]
    resp.securities_value = d["securities_value"]
    resp.current_balance = d["current_balance"]
    return resp

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Account).where(Account.account_id == account_id)
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    await db.commit()
    await recalculate_all_lots(db)
    await generate_daily_snapshot(db)
