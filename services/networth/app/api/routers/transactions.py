from typing import List, Optional, Union
import asyncio
import datetime
import json
import math
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import aliased
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, User, PriceHistory
from app.schemas.schemas import TransactionCreate, TransactionUpdate, TransactionResponse, PaginatedTransactionResponse
from app.services.fifo_engine import recalculate_all_lots
from app.services.dividend_engine import sync_dividends_for_asset
from app.services.price_engine import cleanup_orphan_transaction_prices
from app.services.background_worker import background_worker
from app.services import cache_service
from app.api.deps import get_current_user, get_user_id

async def notify_snapshot_recalculate(
    user_id: int,
    start_date: Optional[datetime.date] = None,
    reason: str = "trade_event",
    auth_token: Optional[str] = None
) -> bool:
    return await background_worker.enqueue_recalculate(user_id=user_id, start_date=start_date, reason=reason)

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

@router.get("", response_model=Union[PaginatedTransactionResponse, List[TransactionResponse]])
@router.get("/", response_model=Union[PaginatedTransactionResponse, List[TransactionResponse]])
async def list_transactions(
    response: Response,
    account_id: Optional[int] = None,
    asset_id: Optional[int] = None,
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    page_size: Optional[int] = Query(None, ge=1, description="Items per page"),
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
    is_paginated = page is not None
    eff_page = page if is_paginated else 1
    eff_page_size = min(page_size, 500) if page_size is not None else (50 if is_paginated else limit)

    cache_key = None
    if is_paginated:
        cache_key = cache_service.get_transaction_page_key(
            user_id=u_id,
            page=eff_page,
            page_size=eff_page_size,
            account_id=account_id,
            asset_id=asset_id,
        )
        try:
            cached_val = await cache_service.get_cache(cache_key)
            if cached_val is not None:
                cached_data = json.loads(cached_val)
                if response is not None:
                    response.headers["X-Total-Count"] = str(cached_data.get("total", 0))
                    response.headers["X-Total-Pages"] = str(cached_data.get("total_pages", 0))
                    response.headers["X-Page"] = str(cached_data.get("page", eff_page))
                    response.headers["X-Page-Size"] = str(cached_data.get("page_size", eff_page_size))
                return cached_data
        except Exception:
            pass

    count_stmt = select(func.count(Transaction.transaction_id)).where(Transaction.user_id == u_id)
    if account_id is not None:
        count_stmt = count_stmt.where(Transaction.account_id == account_id)
    if asset_id is not None:
        count_stmt = count_stmt.where(Transaction.asset_id == asset_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    if total == 0:
        total_pages = 0
        has_more = False
    else:
        total_pages = math.ceil(total / eff_page_size) if eff_page_size > 0 else 0
        has_more = (eff_page * eff_page_size) < total

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
        .where(Transaction.user_id == u_id)
        
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if asset_id is not None:
        stmt = stmt.where(Transaction.asset_id == asset_id)

    stmt = stmt.order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id))

    if is_paginated:
        calc_offset = (eff_page - 1) * eff_page_size
        stmt = stmt.offset(calc_offset).limit(eff_page_size)
    else:
        stmt = stmt.offset(offset).limit(limit)
    
    res = await db.execute(stmt)
    rows = res.all()
    
    out = []
    for tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr in rows:
        out.append(_build_transaction_response(tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr))

    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Total-Pages"] = str(total_pages if is_paginated else (1 if total > 0 else 0))
        response.headers["X-Page"] = str(eff_page)
        response.headers["X-Page-Size"] = str(eff_page_size if is_paginated else limit)

    if not is_paginated:
        return out

    paginated_resp = PaginatedTransactionResponse(
        items=out,
        total=total,
        page=eff_page,
        page_size=eff_page_size,
        total_pages=total_pages,
        has_more=has_more
    )

    if cache_key is not None:
        try:
            await cache_service.set_cache(cache_key, paginated_resp.model_dump_json(), ttl_seconds=300)
        except Exception:
            pass

    return paginated_resp

@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
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
        .where(Transaction.transaction_id == transaction_id, Transaction.user_id == u_id)
        
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
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    u_id = current_user.user_id
    acc = await db.get(Account, tx_in.account_id)
    if not acc or acc.user_id != u_id:
        raise HTTPException(status_code=404, detail="Target account not found or access denied")
    if tx_in.funding_account_id:
        f_acc = await db.get(Account, tx_in.funding_account_id)
        if not f_acc or f_acc.user_id != u_id:
            raise HTTPException(status_code=404, detail="Funding account not found or access denied")

    tx = Transaction(**tx_in.model_dump(), user_id=u_id)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    
    # Auto-populate price history for transaction date if missing
    await _ensure_price_history_for_tx(db, tx)
    await _adjust_price_history_for_split(db, tx)

    tx_date = tx.transaction_date
    tx_asset_id = tx.asset_id
    tx_type = tx.transaction_type
    tx_id = tx.transaction_id

    # Run FIFO & Cash flow engine
    await recalculate_all_lots(db, user_id=u_id)
    
    # Non-blocking async notification to Networth microservice
    asyncio.create_task(
        notify_snapshot_recalculate(
            user_id=u_id,
            start_date=tx_date,
            reason="trade_created",
            auth_token=authorization
        )
    )
    await cache_service.invalidate_user_snapshot_cache(u_id)
    await cache_service.invalidate_user_transaction_cache(u_id)

    # Sync dividends for asset if it's a buy/sell trade
    if tx_asset_id and tx_type in ["buy", "sell"]:
        try:
            await sync_dividends_for_asset(db, tx_asset_id)
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
        .where(Transaction.transaction_id == tx_id, Transaction.user_id == u_id)
    res = await db.execute(stmt)
    row = res.first()
    
    return _build_transaction_response(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    tx_in: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    u_id = current_user.user_id
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id, Transaction.user_id == u_id)
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = tx_in.model_dump(exclude_unset=True)
    if "account_id" in update_data and update_data["account_id"] is not None:
        acc = await db.get(Account, update_data["account_id"])
        if not acc or acc.user_id != u_id:
            raise HTTPException(status_code=404, detail="Target account not found or access denied")
    if "funding_account_id" in update_data and update_data["funding_account_id"] is not None:
        f_acc = await db.get(Account, update_data["funding_account_id"])
        if not f_acc or f_acc.user_id != u_id:
            raise HTTPException(status_code=404, detail="Funding account not found or access denied")

    for field, val in update_data.items():
        setattr(tx, field, val)

    await db.commit()
    await db.refresh(tx)

    # Auto-populate price history for transaction date if missing
    await _ensure_price_history_for_tx(db, tx)
    if tx.asset_id:
        await cleanup_orphan_transaction_prices(db, tx.asset_id)
        await db.commit()

    tx_date = tx.transaction_date
    tx_asset_id = tx.asset_id
    tx_type = tx.transaction_type
    tx_id = tx.transaction_id
    
    # Recalculate derived state
    await recalculate_all_lots(db, user_id=u_id)
    asyncio.create_task(
        notify_snapshot_recalculate(
            user_id=u_id,
            start_date=tx_date,
            reason="trade_updated",
            auth_token=authorization
        )
    )
    await cache_service.invalidate_user_snapshot_cache(u_id)
    await cache_service.invalidate_user_transaction_cache(u_id)

    if tx_asset_id and tx_type in ["buy", "sell"]:
        try:
            await sync_dividends_for_asset(db, tx_asset_id)
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
        .where(Transaction.transaction_id == tx_id, Transaction.user_id == u_id)
    res_resp = await db.execute(stmt_resp)
    row = res_resp.first()

    return _build_transaction_response(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    u_id = current_user.user_id
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id, Transaction.user_id == u_id)
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
    await recalculate_all_lots(db, user_id=u_id)
    asyncio.create_task(
        notify_snapshot_recalculate(
            user_id=u_id,
            start_date=tx_date,
            reason="trade_deleted",
            auth_token=authorization
        )
    )
    await cache_service.invalidate_user_snapshot_cache(u_id)
    await cache_service.invalidate_user_transaction_cache(u_id)

    if target_asset_id and is_trade:
        try:
            await sync_dividends_for_asset(db, target_asset_id)
        except Exception as de:
            print(f"[Dividend Sync Error on Delete] {de}")
