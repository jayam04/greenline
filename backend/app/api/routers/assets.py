import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import yfinance as yf
from app.db.database import get_db, AsyncSessionLocal
from app.db.models import Asset, User
from app.schemas.schemas import AssetCreate, AssetUpdate, AssetResponse
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot
from app.services.price_engine import fetch_asset_price_history

router = APIRouter(prefix="/assets", tags=["assets"])

def map_quote_type_to_asset_type(quote_type: str) -> str:
    qt = (quote_type or "").upper()
    if "ETF" in qt:
        return "etf"
    elif "MUTUAL" in qt:
        return "mutual_fund"
    elif "CRYPTO" in qt:
        return "crypto"
    elif "INDEX" in qt:
        return "index"
    elif "BOND" in qt:
        return "bond"
    return "stock"

def _fetch_yf_ticker_info(symbol: str) -> Dict[str, Any]:
    """Synchronous yfinance info lookup to be executed in a threadpool."""
    ticker = yf.Ticker(symbol)
    return ticker.info or {}

def _search_yf_quotes(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Synchronous yfinance search to be executed in a threadpool."""
    try:
        search = yf.Search(query, max_results=max_results)
        return getattr(search, "quotes", []) or []
    except Exception as e:
        print(f"[Yahoo Search Error] {e}")
        return []

async def _bg_fetch_asset_price_history(asset_id: int, symbol: str) -> None:
    """Safely fetch and save price history for an asset in the background using a fresh DB session."""
    async with AsyncSessionLocal() as session:
        try:
            await fetch_asset_price_history(session, asset_id, symbol)
        except Exception as pe:
            print(f"[Price History Init Warning] {pe}")

@router.get("/lookup")
async def lookup_asset_metadata(
    symbol: str = Query(..., description="Ticker symbol e.g. AAPL or RELIANCE.NS"),
    current_user: User = Depends(get_current_user)
):
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        info = await asyncio.to_thread(_fetch_yf_ticker_info, clean_symbol)

        # Extract fields from Yahoo Finance info
        name = info.get("longName") or info.get("shortName") or clean_symbol
        exchange = info.get("exchange") or info.get("fullExchangeName") or "UNKNOWN"
        sector = info.get("sector") or info.get("category") or ""
        industry = info.get("industry") or info.get("industryKey") or ""
        currency = info.get("currency") or info.get("financialCurrency") or "USD"
        isin = info.get("isin") or None

        quote_type = str(info.get("quoteType", "")).upper()
        asset_type = map_quote_type_to_asset_type(quote_type)

        return {
            "symbol": clean_symbol,
            "isin": isin,
            "name": name,
            "exchange": exchange,
            "sector": sector,
            "industry": industry,
            "asset_type": asset_type,
            "currency": currency.upper(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch metadata for symbol {clean_symbol}: {str(e)}")

@router.get("/search")
async def search_assets(
    q: str = Query(..., min_length=1, description="Search query by ISIN, ticker, or name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query_str = q.strip()
    if not query_str:
        return []

    # 1. Search local DB assets first
    search_term = f"%{query_str}%"
    db_stmt = select(Asset).where(
        or_(
            Asset.symbol.ilike(search_term),
            Asset.name.ilike(search_term),
            Asset.isin.ilike(search_term)
        )
    ).limit(6)
    db_res = await db.execute(db_stmt)
    local_assets = db_res.scalars().all()

    results: List[Dict[str, Any]] = []
    seen_symbols = set()

    for la in local_assets:
        sym = la.symbol.upper()
        seen_symbols.add(sym)
        results.append({
            "asset_id": la.asset_id,
            "symbol": la.symbol,
            "isin": la.isin,
            "name": la.name,
            "exchange": la.exchange or "LOCAL",
            "asset_type": la.asset_type,
            "sector": la.sector or "",
            "industry": la.industry or "",
            "currency": la.currency or "USD",
            "in_master": True
        })

    # 2. Query Yahoo Finance Search API for online results via threadpool
    quotes = await asyncio.to_thread(_search_yf_quotes, query_str, 8)
    for quote in quotes:
        sym = quote.get("symbol")
        if not sym:
            continue
        sym_upper = sym.upper()
        if sym_upper in seen_symbols:
            continue
        seen_symbols.add(sym_upper)

        name = quote.get("longname") or quote.get("shortname") or sym_upper
        exchange = quote.get("exchange") or quote.get("dispExchange") or "UNKNOWN"
        q_type = quote.get("quoteType", "")
        asset_type = map_quote_type_to_asset_type(q_type)
        sector = quote.get("sector") or ""
        industry = quote.get("industry") or ""

        results.append({
            "asset_id": None,
            "symbol": sym_upper,
            "isin": quote.get("isin") or None,
            "name": name,
            "exchange": exchange,
            "asset_type": asset_type,
            "sector": sector,
            "industry": industry,
            "currency": "USD",
            "in_master": False
        })

    return results

@router.post("/get-or-create", response_model=AssetResponse)
async def get_or_create_asset(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    symbol = str(payload.get("symbol", "")).strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    # 1. Check if asset exists in DB
    stmt = select(Asset).where(Asset.symbol == symbol)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    # 2. Fetch full metadata from Yahoo Finance to enrich record
    name = payload.get("name") or symbol
    exchange = payload.get("exchange") or "UNKNOWN"
    sector = payload.get("sector") or ""
    industry = payload.get("industry") or ""
    currency = payload.get("currency") or "USD"
    asset_type = payload.get("asset_type") or "stock"
    isin = payload.get("isin") or None

    try:
        info = await asyncio.to_thread(_fetch_yf_ticker_info, symbol)
        if info:
            name = info.get("longName") or info.get("shortName") or name
            exchange = info.get("exchange") or info.get("fullExchangeName") or exchange
            sector = info.get("sector") or info.get("category") or sector
            industry = info.get("industry") or info.get("industryKey") or industry
            currency = (info.get("currency") or info.get("financialCurrency") or currency).upper()
            quote_type = str(info.get("quoteType", "")).upper()
            if quote_type:
                asset_type = map_quote_type_to_asset_type(quote_type)
            isin = info.get("isin") or isin
    except Exception as e:
        print(f"[Yahoo Enrichment Warning] {e}")

    new_asset = Asset(
        symbol=symbol,
        isin=isin,
        name=name,
        asset_type=asset_type,
        exchange=exchange,
        sector=sector if sector else None,
        industry=industry if industry else None,
        currency=currency
    )
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)

    # Initial price history fetch in background so valuation and charts populate
    background_tasks.add_task(_bg_fetch_asset_price_history, new_asset.asset_id, symbol)

    return new_asset

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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asset_dict = asset_in.model_dump()
    asset_dict["symbol"] = asset_dict["symbol"].upper().strip()

    asset = Asset(**asset_dict)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    background_tasks.add_task(_bg_fetch_asset_price_history, asset.asset_id, asset.symbol)

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
