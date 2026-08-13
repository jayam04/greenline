from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import NetworthSnapshot, User
from app.schemas.schemas import NetworthSnapshotResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

@router.get("/", response_model=List[NetworthSnapshotResponse])
async def list_snapshots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(NetworthSnapshot)
        .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
        .order_by(asc(NetworthSnapshot.snapshot_date))
    )
    res = await db.execute(stmt)
    return res.scalars().all()
