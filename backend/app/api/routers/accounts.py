from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Account, User, Transaction, CashflowTransaction, CashflowItem, Lot, PriceHistory
from app.schemas.schemas import AccountCreate, AccountUpdate, AccountResponse
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.cashflow_engine import compute_transaction_cash_movement

router = APIRouter(prefix="/accounts", tags=["accounts"])

async def calculate_all_account_details(db: AsyncSession) -> Dict[int, Dict[str, float]]:
    """
    Computes detailed cash_balance, securities_value, and current_balance for every account in a single pass.
    """
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()
    account_ids = {a.account_id for a in accounts}

    cash_balances: Dict[int, float] = {a.account_id: 0.0 for a in accounts}
    securities_values: Dict[int, float] = {a.account_id: 0.0 for a in accounts}

    # 1. Investment transactions cash movements
    tx_stmt = select(Transaction)
    tx_res = await db.execute(tx_stmt)
    for tx in tx_res.scalars().all():
        cash_acc_id, delta = compute_transaction_cash_movement(tx, account_ids)
        if cash_acc_id in cash_balances:
            cash_balances[cash_acc_id] += delta

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

    # 3. Securities valuation for open lots with single batch price fetch
    lot_stmt = select(Lot).where(Lot.quantity_remaining > 0)
    lot_res = await db.execute(lot_stmt)
    open_lots = lot_res.scalars().all()

    if open_lots:
        asset_ids = list(set(l.asset_id for l in open_lots))
        latest_prices: Dict[int, float] = {}

        if asset_ids:
            latest_date_subq = (
                select(PriceHistory.asset_id, func.max(PriceHistory.price_date).label("max_date"))
                .where(PriceHistory.asset_id.in_(asset_ids))
                .group_by(PriceHistory.asset_id)
                .subquery()
            )
            ph_stmt = (
                select(PriceHistory.asset_id, PriceHistory.close_price)
                .join(
                    latest_date_subq,
                    (PriceHistory.asset_id == latest_date_subq.c.asset_id) &
                    (PriceHistory.price_date == latest_date_subq.c.max_date)
                )
            )
            ph_res = await db.execute(ph_stmt)
            for aid, close_px in ph_res.all():
                if close_px is not None:
                    latest_prices[aid] = float(close_px)

        for lot in open_lots:
            acc_id = lot.account_id
            if acc_id in securities_values:
                unit_price = latest_prices.get(lot.asset_id, float(lot.cost_per_unit or 0.0))
                securities_values[acc_id] += float(lot.quantity_remaining) * unit_price

    results = {}
    for a in accounts:
        aid = a.account_id
        c_bal = round(cash_balances.get(aid, 0.0), 2)
        s_val = round(securities_values.get(aid, 0.0), 2)
        results[aid] = {
            "cash_balance": c_bal,
            "securities_value": s_val,
            "current_balance": round(c_bal + s_val, 2)
        }

    return results

async def calculate_all_account_cash_balances(db: AsyncSession) -> Dict[int, float]:
    """Computes pure uninvested liquid cash for every account."""
    details = await calculate_all_account_details(db)
    return {k: v["cash_balance"] for k, v in details.items()}

async def calculate_all_account_balances(db: AsyncSession) -> Dict[int, float]:
    """Computes total valuation (cash + open securities) for every account."""
    details = await calculate_all_account_details(db)
    return {k: v["current_balance"] for k, v in details.items()}

async def calculate_all_account_securities_values(db: AsyncSession) -> Dict[int, float]:
    """Computes securities valuation for every account."""
    details = await calculate_all_account_details(db)
    return {k: v["securities_value"] for k, v in details.items()}

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
