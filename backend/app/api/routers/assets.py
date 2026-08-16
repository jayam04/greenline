from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import yfinance as yf
from app.db.database import get_db
from app.db.models import Asset, User
from app.schemas.schemas import AssetCreate, AssetUpdate, AssetResponse
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot

router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("/lookup")
async def lookup_asset_metadata(
    symbol: str = Query(..., description="Ticker symbol e.g. AAPL or RELIANCE.NS"),
    current_user: User = Depends(get_current_user)
):
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        ticker = yf.Ticker(clean_symbol)
        info = ticker.info or {}

        # Extract fields from Yahoo Finance info
        name = info.get("longName") or info.get("shortName") or clean_symbol
        exchange = info.get("exchange") or info.get("fullExchangeName") or "UNKNOWN"
        sector = info.get("sector") or info.get("category") or ""
        currency = info.get("currency") or info.get("financialCurrency") or "USD"

        quote_type = str(info.get("quoteType", "")).upper()
        asset_type = "stock"
        if "ETF" in quote_type:
            asset_type = "etf"
        elif "MUTUAL" in quote_type:
            asset_type = "mutual_fund"
        elif "CRYPTO" in quote_type:
            asset_type = "crypto"

        return {
            "symbol": clean_symbol,
            "name": name,
            "exchange": exchange,
            "sector": sector,
            "asset_type": asset_type,
            "currency": currency.upper(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch metadata for symbol {clean_symbol}: {str(e)}")

@router.get("/", response_model=List[AssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Asset)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Asset).where(Asset.asset_id == asset_id)
    res = await db.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_in: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asset_dict = asset_in.model_dump()
    asset_dict["symbol"] = asset_dict["symbol"].upper().strip()

    asset = Asset(**asset_dict)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset

@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    asset_in: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Asset).where(Asset.asset_id == asset_id)
    res = await db.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    update_data = asset_in.model_dump(exclude_unset=True)
    if "symbol" in update_data and update_data["symbol"]:
        update_data["symbol"] = update_data["symbol"].upper().strip()

    for field, val in update_data.items():
        setattr(asset, field, val)

    await db.commit()
    await db.refresh(asset)
    return asset

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Asset).where(Asset.asset_id == asset_id)
    res = await db.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    await db.delete(asset)
    await db.commit()
    await recalculate_all_lots(db)
    await generate_daily_snapshot(db)
