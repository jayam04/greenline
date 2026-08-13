from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, User
from app.schemas.schemas import TransactionCreate, TransactionUpdate, TransactionResponse
from app.services.fifo_engine import process_transaction_event, recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot
from app.api.deps import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    account_id: Optional[int] = Query(None),
    asset_id: Optional[int] = Query(None),
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Transaction, Account.account_name, Asset.symbol, Asset.name)\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)
        
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if asset_id:
        stmt = stmt.where(Transaction.asset_id == asset_id)
        
    stmt = stmt.order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id)).limit(limit).offset(offset)
    
    res = await db.execute(stmt)
    rows = res.all()
    
    out = []
    for tx, acc_name, symbol, asset_name in rows:
        t_dict = TransactionResponse.model_validate(tx).model_dump()
        t_dict["account_name"] = acc_name
        t_dict["asset_symbol"] = symbol
        t_dict["asset_name"] = asset_name
        out.append(TransactionResponse(**t_dict))
        
    return out

@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Transaction, Account.account_name, Asset.symbol, Asset.name)\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == transaction_id)
        
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    t_dict = TransactionResponse.model_validate(row[0]).model_dump()
    t_dict["account_name"] = row[1]
    t_dict["asset_symbol"] = row[2]
    t_dict["asset_name"] = row[3]
    return TransactionResponse(**t_dict)

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    tx_in: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tx = Transaction(**tx_in.model_dump())
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    
    # Run FIFO & Cash flow engine
    await recalculate_all_lots(db)
    await generate_daily_snapshot(db, tx.transaction_date)
    
    # Format response
    stmt = select(Transaction, Account.account_name, Asset.symbol, Asset.name)\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == tx.transaction_id)
    res = await db.execute(stmt)
    row = res.first()
    
    t_dict = TransactionResponse.model_validate(row[0]).model_dump()
    t_dict["account_name"] = row[1]
    t_dict["asset_symbol"] = row[2]
    t_dict["asset_name"] = row[3]
    return TransactionResponse(**t_dict)

@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    tx_in: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = tx_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(tx, field, val)

    await db.commit()
    
    # Recalculate derived state
    await recalculate_all_lots(db)
    await generate_daily_snapshot(db, tx.transaction_date)

    stmt_resp = select(Transaction, Account.account_name, Asset.symbol, Asset.name)\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == tx.transaction_id)
    res_resp = await db.execute(stmt_resp)
    row = res_resp.first()

    t_dict = TransactionResponse.model_validate(row[0]).model_dump()
    t_dict["account_name"] = row[1]
    t_dict["asset_symbol"] = row[2]
    t_dict["asset_name"] = row[3]
    return TransactionResponse(**t_dict)

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    await db.delete(tx)
    await db.commit()

    # Recalculate derived state
    await recalculate_all_lots(db)
    await generate_daily_snapshot(db)
