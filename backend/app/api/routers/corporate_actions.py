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
    action = CorporateAction(**action_in.model_dump())
    db.add(action)
    await db.commit()
    await db.refresh(action)

    # Adjust open lots if split or bonus
    if action.action_type in ["split", "bonus"]:
        try:
            parts = action.ratio.split(":")
            if len(parts) == 2:
                new_num, old_den = float(parts[0]), float(parts[1])
                multiplier = new_num / old_den if old_den > 0 else 1.0
                
                stmt = select(Lot).where(Lot.asset_id == action.asset_id, Lot.quantity_remaining > 0)
                res = await db.execute(stmt)
                for lot in res.scalars().all():
                    lot.quantity_remaining *= multiplier
                    lot.quantity_original *= multiplier
                    lot.cost_per_unit /= multiplier
                await db.commit()
        except Exception:
            pass

    return action
