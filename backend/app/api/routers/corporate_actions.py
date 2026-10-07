from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import CorporateAction, Lot, User
from app.schemas.schemas import CorporateActionCreate, CorporateActionResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/corporate-actions", tags=["corporate-actions"])

@router.get("/", response_model=List[CorporateActionResponse])
async def list_corporate_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(CorporateAction)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/", response_model=CorporateActionResponse, status_code=status.HTTP_201_CREATED)
async def create_corporate_action(
    action_in: CorporateActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.services.fifo_engine import recalculate_all_lots
    from app.db.models import Asset, PriceHistory

    action = CorporateAction(**action_in.model_dump())
    db.add(action)
    await db.commit()
    await db.refresh(action)

    # If asset is Private Equity, automatically adjust historical prices
    stmt_asset = select(Asset).where(Asset.asset_id == action.asset_id)
    res_asset = await db.execute(stmt_asset)
    asset = res_asset.scalars().first()

    if asset and asset.asset_type == "Private Equity" and action.action_type in ["split", "bonus"]:
        try:
            parts = action.ratio.split(":")
            if len(parts) == 2:
                new_num, old_den = float(parts[0]), float(parts[1])
                multiplier = new_num / old_den if old_den > 0 else 1.0
                if multiplier > 0:
                    stmt_ph = select(PriceHistory).where(
                        PriceHistory.asset_id == action.asset_id,
                        PriceHistory.price_date <= action.action_date
                    )
                    res_ph = await db.execute(stmt_ph)
                    for ph in res_ph.scalars().all():
                        ph.close_price /= multiplier
                    await db.commit()
        except Exception:
            pass

    # Fully recalculate all lots with the new action interleaving
    await recalculate_all_lots(db)

    return action