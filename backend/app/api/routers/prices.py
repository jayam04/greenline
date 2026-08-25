from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.database import get_db
from app.db.models import PriceHistory, User
from app.schemas.schemas import PriceHistoryCreate, PriceHistoryResponse
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import generate_daily_snapshot
from app.api.deps import get_current_user

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("/{asset_id}", response_model=List[PriceHistoryResponse])
async def get_price_history(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id)
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
    # Upsert manual price
    stmt = select(PriceHistory).where(
        PriceHistory.asset_id == price_in.asset_id,
        PriceHistory.price_date == price_in.price_date
    )
    res = await db.execute(stmt)
    ph = res.scalar_one_or_none()
    
    if ph is None:
        ph = PriceHistory(**price_in.model_dump())
        db.add(ph)
    else:
        ph.close_price = price_in.close_price
        ph.source = price_in.source
        
    await db.commit()
    await db.refresh(ph)
    
    # Re-trigger snapshot calculation
    await generate_daily_snapshot(db, price_in.price_date)
    return ph

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def trigger_price_refresh(
    asset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asset_ids = [asset_id] if asset_id else None
    count = await update_prices_for_assets(db, asset_ids)
    await generate_daily_snapshot(db)
    return {"message": f"Price update completed. {count} new price records added."}
