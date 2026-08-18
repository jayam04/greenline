import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import AppSetting, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

class AppSettingsSchema(BaseModel):
    link_brokerage_with_bank: bool = False

@router.get("", response_model=AppSettingsSchema)
@router.get("/", response_model=AppSettingsSchema)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    stmt = select(AppSetting).where(AppSetting.key == "link_brokerage_with_bank")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    
    val = False
    if setting and setting.value:
        try:
            val = json.loads(setting.value)
        except Exception:
            val = setting.value.lower() in ("true", "1", "yes")
            
    return AppSettingsSchema(link_brokerage_with_bank=bool(val))

@router.put("", response_model=AppSettingsSchema)
@router.put("/", response_model=AppSettingsSchema)
async def update_settings(
    payload: AppSettingsSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    stmt = select(AppSetting).where(AppSetting.key == "link_brokerage_with_bank")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()

    json_val = json.dumps(payload.link_brokerage_with_bank)
    if not setting:
        setting = AppSetting(key="link_brokerage_with_bank", value=json_val)
        db.add(setting)
    else:
        setting.value = json_val

    await db.commit()
    await db.refresh(setting)

    return AppSettingsSchema(link_brokerage_with_bank=payload.link_brokerage_with_bank)
