import json
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import AppSetting, User
from app.services import cache_service
from app.api.deps import get_current_user, get_user_id

router = APIRouter(prefix="/settings", tags=["settings"])

class AppSettingsSchema(BaseModel):
    link_brokerage_with_bank: bool = False
    master_currency: str = "EUR"
    fiscal_year_start: str = "01-01"
    app_font: str = "general-sans"
    community_pseudonym: Optional[str] = None

@router.get("", response_model=AppSettingsSchema)
@router.get("/", response_model=AppSettingsSchema)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    u_id = get_user_id(current_user)
    stmt = select(AppSetting).where(
        AppSetting.user_id.in_([0, u_id]),
        AppSetting.key.in_(["link_brokerage_with_bank", "master_currency", "fiscal_year_start", "app_font", "community_pseudonym"])
    )
    res = await db.execute(stmt)
    # Order by user_id so user's own setting overrides default user 0 setting
    all_settings = res.scalars().all()
    all_settings.sort(key=lambda s: s.user_id)
    settings_map = {s.key: s.value for s in all_settings}

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

    font_val = "general-sans"
    if "app_font" in settings_map:
        try:
            font_val = json.loads(settings_map["app_font"])
        except Exception:
            font_val = settings_map["app_font"]
    if str(font_val).strip().lower() not in ("general-sans", "inter", "rx100", "spline-sans", "spine-sans"):
        font_val = "general-sans"
    else:
        font_val = str(font_val).strip().lower()

    pseudo_val = None
    if "community_pseudonym" in settings_map:
        try:
            pseudo_val = json.loads(settings_map["community_pseudonym"])
        except Exception:
            pseudo_val = settings_map["community_pseudonym"]
        if pseudo_val is not None:
            pseudo_val = str(pseudo_val).strip() or None

    return AppSettingsSchema(
        link_brokerage_with_bank=bool(link_val),
        master_currency=str(curr_val).strip().upper() or "EUR",
        fiscal_year_start=str(fy_val).strip() or "01-01",
        app_font=font_val,
        community_pseudonym=pseudo_val
    )

@router.put("", response_model=AppSettingsSchema)
@router.put("/", response_model=AppSettingsSchema)
async def update_settings(
    payload: AppSettingsSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppSettingsSchema:
    u_id = get_user_id(current_user)
    # 1. Update link_brokerage_with_bank
    stmt_link = select(AppSetting).where(AppSetting.user_id == u_id, AppSetting.key == "link_brokerage_with_bank")
    res_link = await db.execute(stmt_link)
    s_link = res_link.scalar_one_or_none()
    link_json = json.dumps(payload.link_brokerage_with_bank)
    if not s_link:
        db.add(AppSetting(user_id=u_id, key="link_brokerage_with_bank", value=link_json))
    else:
        s_link.value = link_json

    # 2. Update master_currency
    norm_curr = payload.master_currency.strip().upper() or "EUR"
    stmt_curr = select(AppSetting).where(AppSetting.user_id == u_id, AppSetting.key == "master_currency")
    res_curr = await db.execute(stmt_curr)
    s_curr = res_curr.scalar_one_or_none()
    curr_json = json.dumps(norm_curr)
    if not s_curr:
        db.add(AppSetting(user_id=u_id, key="master_currency", value=curr_json))
    else:
        s_curr.value = curr_json

    # 3. Update fiscal_year_start
    norm_fy = payload.fiscal_year_start.strip() or "01-01"
    stmt_fy = select(AppSetting).where(AppSetting.user_id == u_id, AppSetting.key == "fiscal_year_start")
    res_fy = await db.execute(stmt_fy)
    s_fy = res_fy.scalar_one_or_none()
    fy_json = json.dumps(norm_fy)
    if not s_fy:
        db.add(AppSetting(user_id=u_id, key="fiscal_year_start", value=fy_json))
    else:
        s_fy.value = fy_json

    # 4. Update app_font
    norm_font = payload.app_font.strip().lower()
    if norm_font not in ("general-sans", "inter", "rx100", "spline-sans", "spine-sans"):
        norm_font = "general-sans"
    stmt_font = select(AppSetting).where(AppSetting.user_id == u_id, AppSetting.key == "app_font")
    res_font = await db.execute(stmt_font)
    s_font = res_font.scalar_one_or_none()
    font_json = json.dumps(norm_font)
    if not s_font:
        db.add(AppSetting(user_id=u_id, key="app_font", value=font_json))
    else:
        s_font.value = font_json

    # 5. Update community_pseudonym
    stmt_pseudo = select(AppSetting).where(AppSetting.user_id == u_id, AppSetting.key == "community_pseudonym")
    res_pseudo = await db.execute(stmt_pseudo)
    s_pseudo = res_pseudo.scalar_one_or_none()

    if "community_pseudonym" in payload.model_fields_set:
        norm_pseudo = payload.community_pseudonym.strip() if payload.community_pseudonym is not None else None
        if norm_pseudo == "":
            norm_pseudo = None

        if norm_pseudo is not None:
            pseudo_json = json.dumps(norm_pseudo)
            if not s_pseudo:
                db.add(AppSetting(user_id=u_id, key="community_pseudonym", value=pseudo_json))
            else:
                s_pseudo.value = pseudo_json
            current_pseudo = norm_pseudo
        else:
            if s_pseudo:
                await db.delete(s_pseudo)
            current_pseudo = None
    else:
        # Field was omitted in request payload; preserve existing setting
        if s_pseudo:
            try:
                current_pseudo = json.loads(s_pseudo.value)
            except Exception:
                current_pseudo = s_pseudo.value
            if current_pseudo is not None:
                current_pseudo = str(current_pseudo).strip() or None
        else:
            current_pseudo = None

    await db.commit()
    await cache_service.invalidate_user_snapshot_cache(u_id)

    return AppSettingsSchema(
        link_brokerage_with_bank=payload.link_brokerage_with_bank,
        master_currency=norm_curr,
        fiscal_year_start=norm_fy,
        app_font=norm_font,
        community_pseudonym=current_pseudo
    )

