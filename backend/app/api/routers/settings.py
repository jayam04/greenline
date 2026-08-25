import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import AppSetting, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

class AppSettingsSchema(BaseModel):
    link_brokerage_with_bank: bool = False
    master_currency: str = "EUR"
    fiscal_year_start: str = "01-01"

@router.get("", response_model=AppSettingsSchema)
@router.get("/", response_model=AppSettingsSchema)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    stmt = select(AppSetting).where(
        AppSetting.key.in_(["link_brokerage_with_bank", "master_currency", "fiscal_year_start"])
    )
    res = await db.execute(stmt)
    settings_map = {s.key: s.value for s in res.scalars().all()}

    link_val = False
    if "link_brokerage_with_bank" in settings_map:
        try:
            link_val = json.loads(settings_map["link_brokerage_with_bank"])
        except Exception:
            link_val = settings_map["link_brokerage_with_bank"].lower() in ("true", "1", "yes")

    curr_val = "EUR"
    if "master_currency" in settings_map:
        try:
            curr_val = json.loads(settings_map["master_currency"])
        except Exception:
            curr_val = settings_map["master_currency"]

    fy_val = "01-01"
    if "fiscal_year_start" in settings_map:
        try:
            fy_val = json.loads(settings_map["fiscal_year_start"])
        except Exception:
            fy_val = settings_map["fiscal_year_start"]

    return AppSettingsSchema(
        link_brokerage_with_bank=bool(link_val),
        master_currency=str(curr_val).strip().upper() or "EUR",
        fiscal_year_start=str(fy_val).strip() or "01-01"
    )

@router.put("", response_model=AppSettingsSchema)
@router.put("/", response_model=AppSettingsSchema)
async def update_settings(
    payload: AppSettingsSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    # 1. Update link_brokerage_with_bank
    stmt_link = select(AppSetting).where(AppSetting.key == "link_brokerage_with_bank")
    res_link = await db.execute(stmt_link)
    s_link = res_link.scalar_one_or_none()
    link_json = json.dumps(payload.link_brokerage_with_bank)
    if not s_link:
        db.add(AppSetting(key="link_brokerage_with_bank", value=link_json))
    else:
        s_link.value = link_json

    # 2. Update master_currency
    norm_curr = payload.master_currency.strip().upper() or "EUR"
    stmt_curr = select(AppSetting).where(AppSetting.key == "master_currency")
    res_curr = await db.execute(stmt_curr)
    s_curr = res_curr.scalar_one_or_none()
    curr_json = json.dumps(norm_curr)
    if not s_curr:
        db.add(AppSetting(key="master_currency", value=curr_json))
    else:
        s_curr.value = curr_json

    # 3. Update fiscal_year_start
    norm_fy = payload.fiscal_year_start.strip() or "01-01"
    stmt_fy = select(AppSetting).where(AppSetting.key == "fiscal_year_start")
    res_fy = await db.execute(stmt_fy)
    s_fy = res_fy.scalar_one_or_none()
    fy_json = json.dumps(norm_fy)
    if not s_fy:
        db.add(AppSetting(key="fiscal_year_start", value=fy_json))
    else:
        s_fy.value = fy_json

    await db.commit()

    return AppSettingsSchema(
        link_brokerage_with_bank=payload.link_brokerage_with_bank,
        master_currency=norm_curr,
        fiscal_year_start=norm_fy
    )
