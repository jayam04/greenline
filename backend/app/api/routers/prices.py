from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.db.database import get_db
from app.db.models import PriceHistory, Asset, User, Transaction
from app.schemas.schemas import PriceHistoryCreate, PriceHistoryResponse, CustomPriceResponse
from app.services.price_engine import update_prices_for_assets, cleanup_orphan_transaction_prices
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots
from app.api.deps import get_current_user, get_user_id

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("/custom", response_model=List[CustomPriceResponse])
async def list_custom_prices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all manual/custom valuation points recorded by users."""
    u_id = get_user_id(current_user)
    stmt = (
        select(PriceHistory, Asset.symbol, Asset.name, Asset.currency)
        .join(Asset, PriceHistory.asset_id == Asset.asset_id)
        .where(PriceHistory.source == "manual", PriceHistory.user_id == u_id)
        .order_by(desc(PriceHistory.price_date), desc(PriceHistory.price_id))
    )
    res = await db.execute(stmt)
    results = []
    for ph, sym, name, curr in res.all():
        results.append(CustomPriceResponse(
            price_id=ph.price_id,
            asset_id=ph.asset_id,
            asset_symbol=sym or "",
            asset_name=name,
            currency=curr or "USD",
            price_date=ph.price_date,
            close_price=ph.close_price,
            source=ph.source
        ))
    return results

@router.get("/{asset_id}", response_model=List[PriceHistoryResponse])
async def get_price_history(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id, PriceHistory.user_id.in_([0, u_id]))
        .order_by(desc(PriceHistory.price_date))
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/", response_model=PriceHistoryResponse, status_code=status.HTTP_201_CREATED)
async def add_manual_price(
    price_in: PriceHistoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
    import math
    if price_in.close_price is None or math.isnan(price_in.close_price) or math.isinf(price_in.close_price) or price_in.close_price <= 0:
        raise HTTPException(status_code=400, detail="Close price must be a valid positive number.")
    if price_in.close_price > 1_000_000_000:
        raise HTTPException(status_code=400, detail="Close price exceeds maximum allowed financial limit.")

    # Upsert manual price
    stmt = select(PriceHistory).where(
        PriceHistory.asset_id == price_in.asset_id,
        PriceHistory.price_date == price_in.price_date
    )
    res = await db.execute(stmt)
    ph = res.scalar_one_or_none()
    
    if ph is not None:
        if ph.source in ["yfinance", "api"]:
            raise HTTPException(
                status_code=400,
                detail="Market price history already exists for this date. Custom valuation cannot overwrite market price history."
            )
        ph.close_price = price_in.close_price
        ph.source = price_in.source or "manual"
    else:
        ph_data = price_in.model_dump()
        ph_data["user_id"] = u_id
        ph_data["source"] = price_in.source or "manual"
        ph = PriceHistory(**ph_data)
        db.add(ph)
        
    await db.commit()
    await db.refresh(ph)
    
    # Re-trigger snapshot calculation
    await generate_daily_snapshot(db, price_in.price_date, user_id=u_id)
    return ph

@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(
    price_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
    stmt = select(PriceHistory).where(PriceHistory.price_id == price_id, PriceHistory.user_id == u_id)
    res = await db.execute(stmt)
    ph = res.scalar_one_or_none()
    if not ph:
        raise HTTPException(status_code=404, detail="Price record not found")

    p_date = ph.price_date
    await db.delete(ph)
    await db.commit()

    # Re-trigger daily snapshot from that date
    await generate_daily_snapshot(db, p_date, user_id=u_id)

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def trigger_price_refresh(
    asset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u_id = get_user_id(current_user)
    # Clean up orphan transaction prices first
    await cleanup_orphan_transaction_prices(db, asset_id)
    if asset_id:
        asset_ids = [asset_id]
    else:
        # Prioritize assets held by the current user
        user_asset_stmt = select(Transaction.asset_id).where(Transaction.user_id == u_id).distinct()
        user_asset_ids = (await db.execute(user_asset_stmt)).scalars().all()
        asset_ids = [a for a in set(user_asset_ids) if a is not None]
        if not asset_ids and u_id == 0:
            asset_ids = None  # Admin fallback

    count = await update_prices_for_assets(db, asset_ids) if (asset_ids or u_id == 0) else 0
    
    # Recalculate past snapshots from earliest transaction date to keep timeline consistent
    min_tx_stmt = select(func.min(Transaction.transaction_date)).where(Transaction.user_id == u_id)
    min_tx = (await db.execute(min_tx_stmt)).scalar_one_or_none()
    if min_tx:
        await recalculate_past_snapshots(db, start_date=min_tx, user_id=u_id)
    else:
        await generate_daily_snapshot(db, user_id=u_id)

    return {"message": f"Price update completed. {count} new price records added."}
