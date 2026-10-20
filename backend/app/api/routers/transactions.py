from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import aliased
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, User, PriceHistory
from app.schemas.schemas import TransactionCreate, TransactionUpdate, TransactionResponse
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import recalculate_past_snapshots
from app.services.dividend_engine import sync_dividends_for_asset
from app.services.price_engine import cleanup_orphan_transaction_prices
from app.api.deps import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])

FundingAccount = aliased(Account)

def _build_transaction_response(
    tx: Transaction,
    acc_name: Optional[str],
    acc_curr: Optional[str],
    symbol: Optional[str],
    asset_name: Optional[str],
    funding_acc_name: Optional[str] = None,
    funding_acc_curr: Optional[str] = None
) -> TransactionResponse:
    return TransactionResponse(
        transaction_id=tx.transaction_id,
        account_id=tx.account_id,
        funding_account_id=tx.funding_account_id,
        asset_id=tx.asset_id,
        transaction_type=tx.transaction_type,
        transaction_date=tx.transaction_date,
        quantity=tx.quantity,
        price_per_unit=tx.price_per_unit,
        total_amount=tx.total_amount,
        fees=tx.fees,
        taxes=tx.taxes,
        notes=tx.notes,
        account_name=acc_name,
        account_currency=acc_curr or "USD",
        funding_account_name=funding_acc_name or acc_name,
        funding_account_currency=funding_acc_curr or acc_curr or "USD",
        asset_symbol=symbol,
        asset_name=asset_name
    )

async def _adjust_price_history_for_split(db: AsyncSession, tx: Transaction):
    from app.db.models import Asset, Lot, PriceHistory
    from sqlalchemy import func
    
    if tx.transaction_type not in ["split", "bonus"] or not tx.asset_id or not tx.quantity:
        return
        
    stmt_asset = select(Asset).where(Asset.asset_id == tx.asset_id)
    res_asset = await db.execute(stmt_asset)
    asset = res_asset.scalars().first()
    
    if asset and asset.asset_type == "Private Equity":
        # Calculate old shares
        stmt_lots = select(func.sum(Lot.quantity_remaining)).where(
            Lot.account_id == tx.account_id,
            Lot.asset_id == tx.asset_id,
            Lot.buy_date <= tx.transaction_date,
            Lot.buy_transaction_id != tx.transaction_id
        )
        old_shares = (await db.execute(stmt_lots)).scalar() or 0.0
        
        if old_shares > 0:
            multiplier = (old_shares + float(tx.quantity)) / old_shares
            if multiplier > 0:
                stmt_ph = select(PriceHistory).where(
                    PriceHistory.asset_id == tx.asset_id,
                    PriceHistory.price_date <= tx.transaction_date
                )
                res_ph = await db.execute(stmt_ph)
                for ph in res_ph.scalars().all():
                    ph.close_price /= multiplier
                await db.commit()

async def _ensure_price_history_for_tx(db: AsyncSession, tx: Transaction):
    """
    If transaction has an asset_id and price_per_unit, ensure PriceHistory exists for that asset date.
    """
    if tx.transaction_type in ["buy", "sell"] and tx.asset_id and tx.price_per_unit and tx.price_per_unit > 0:
        ph_stmt = select(PriceHistory).where(
            PriceHistory.asset_id == tx.asset_id,
            PriceHistory.price_date == tx.transaction_date
        )
        ph_res = await db.execute(ph_stmt)
        ph = ph_res.scalar_one_or_none()
        if ph is None:
            db.add(PriceHistory(
                asset_id=tx.asset_id,
                price_date=tx.transaction_date,
                close_price=tx.price_per_unit,
                source="transaction"
            ))
            await db.flush()

@router.get("", response_model=List[TransactionResponse])
@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    account_id: Optional[int] = None,
    asset_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(
        Transaction, 
        Account.account_name, 
        Account.currency, 
        Asset.symbol, 
        Asset.name,
        FundingAccount.account_name,
        FundingAccount.currency
    )\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)
        
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if asset_id:
        stmt = stmt.where(Transaction.asset_id == asset_id)
        
    stmt = stmt.order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id)).limit(limit).offset(offset)
    
    res = await db.execute(stmt)
    rows = res.all()
    
    out = []
    for tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr in rows:
        out.append(_build_transaction_response(tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr))
        

    out.sort(key=lambda x: (x.transaction_date, x.transaction_id), reverse=True)
    out = out[:limit]
        
    return out

@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(
        Transaction, 
        Account.account_name, 
        Account.currency, 
        Asset.symbol, 
        Asset.name,
        FundingAccount.account_name,
        FundingAccount.currency
    )\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == transaction_id)
        
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    return _build_transaction_response(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
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
    
    # Auto-populate price history for transaction date if missing
    await _ensure_price_history_for_tx(db, tx)
    await _adjust_price_history_for_split(db, tx)

    # Run FIFO & Cash flow engine
    await recalculate_all_lots(db)
    
    # Recalculate past snapshots from transaction date to today
    await recalculate_past_snapshots(db, start_date=tx.transaction_date)

    # Sync dividends for asset if it's a buy/sell trade
    if tx.asset_id and tx.transaction_type in ["buy", "sell"]:
        try:
            await sync_dividends_for_asset(db, tx.asset_id)
        except Exception as de:
            print(f"[Dividend Sync Error on Create] {de}")
    
    # Format response
    stmt = select(
        Transaction, 
        Account.account_name, 
        Account.currency, 
        Asset.symbol, 
        Asset.name,
        FundingAccount.account_name,
        FundingAccount.currency
    )\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == tx.transaction_id)
    res = await db.execute(stmt)
    row = res.first()
    
    return _build_transaction_response(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

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
    await db.refresh(tx)

    # Auto-populate price history for transaction date if missing
    await _ensure_price_history_for_tx(db, tx)
    if tx.asset_id:
        await cleanup_orphan_transaction_prices(db, tx.asset_id)
        await db.commit()
    
    # Recalculate derived state
    await recalculate_all_lots(db)
    await recalculate_past_snapshots(db, start_date=tx.transaction_date)

    if tx.asset_id and tx.transaction_type in ["buy", "sell"]:
        try:
            await sync_dividends_for_asset(db, tx.asset_id)
        except Exception as de:
            print(f"[Dividend Sync Error on Update] {de}")

    stmt_resp = select(
        Transaction, 
        Account.account_name, 
        Account.currency, 
        Asset.symbol, 
        Asset.name,
        FundingAccount.account_name,
        FundingAccount.currency
    )\
        .outerjoin(Account, Transaction.account_id == Account.account_id)\
        .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)\
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)\
        .where(Transaction.transaction_id == tx.transaction_id)
    res_resp = await db.execute(stmt_resp)
    row = res_resp.first()

    return _build_transaction_response(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

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

    target_asset_id = tx.asset_id
    is_trade = tx.transaction_type in ["buy", "sell"]
    tx_date = tx.transaction_date
    await db.delete(tx)
    await db.commit()

    if target_asset_id:
        await cleanup_orphan_transaction_prices(db, target_asset_id)
        await db.commit()

    # Recalculate derived state
    await recalculate_all_lots(db)
    await recalculate_past_snapshots(db, start_date=tx_date)

    if target_asset_id and is_trade:
        try:
            await sync_dividends_for_asset(db, target_asset_id)
        except Exception as de:
            print(f"[Dividend Sync Error on Delete] {de}")
