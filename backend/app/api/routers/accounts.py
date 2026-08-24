from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Account, User, Transaction, CashflowTransaction, CashflowPayment, CashflowItem
from app.schemas.schemas import AccountCreate, AccountUpdate, AccountResponse
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.cashflow_engine import resolve_transaction_kind

router = APIRouter(prefix="/accounts", tags=["accounts"])

async def calculate_all_account_balances(db: AsyncSession) -> Dict[int, float]:
    """
    Computes current net cash/balance for every account combining
    investment transactions and cashflow income/expense/transfers.
    """
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()
    balances = {a.account_id: 0.0 for a in accounts}

    # 1. Investment transactions
    tx_stmt = select(Transaction)
    tx_res = await db.execute(tx_stmt)
    for tx in tx_res.scalars().all():
        ttype = (tx.transaction_type or "").lower()
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)
        if tx.account_id in balances:
            if ttype in ["deposit", "sell", "dividend", "interest"]:
                balances[tx.account_id] += (amt - fees - taxes)
            elif ttype in ["withdrawal", "buy", "fee"]:
                balances[tx.account_id] -= (amt + fees + taxes)

    # 2. Cashflow payments
    c_stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category),
        selectinload(CashflowTransaction.payments)
    )
    c_res = await db.execute(c_stmt)
    for ctx in c_res.scalars().all():
        for p in ctx.payments:
            if p.account_id in balances:
                balances[p.account_id] += float(p.amount or 0.0)

    return {k: round(v, 2) for k, v in balances.items()}

@router.get("", response_model=List[AccountResponse])
@router.get("/", response_model=List[AccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Account)
    res = await db.execute(stmt)
    accounts = res.scalars().all()
    balances = await calculate_all_account_balances(db)

    results = []
    for a in accounts:
        resp = AccountResponse.model_validate(a)
        resp.current_balance = balances.get(a.account_id, 0.0)
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
    balances = await calculate_all_account_balances(db)
    resp = AccountResponse.model_validate(account)
    resp.current_balance = balances.get(account.account_id, 0.0)
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
    balances = await calculate_all_account_balances(db)
    resp = AccountResponse.model_validate(account)
    resp.current_balance = balances.get(account.account_id, 0.0)
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
