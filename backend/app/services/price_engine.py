import asyncio
import datetime
import math
from typing import List, Optional
import yfinance as yf
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Asset, PriceHistory

def _fetch_history_sync(symbol: str, start_date: Optional[datetime.date] = None) -> Optional[pd.DataFrame]:
    """Synchronous yfinance history call to be executed in a threadpool."""
    ticker = yf.Ticker(symbol)
    if start_date:
        start_str = start_date.strftime("%Y-%m-%d")
        return ticker.history(start=start_str)
    else:
        return ticker.history(period="1y")

async def update_prices_for_assets(
    db: AsyncSession, 
    asset_ids: Optional[List[int]] = None,
    start_date: Optional[datetime.date] = None
) -> int:
    """
    Fetches price history from yfinance for given assets (or all assets if None).
    If start_date is provided, queries historical price data starting from start_date to today.
    Returns number of prices inserted/updated.
    """
    stmt = select(Asset)
    if asset_ids:
        stmt = stmt.where(Asset.asset_id.in_(asset_ids))

    res = await db.execute(stmt)
    assets: List[Asset] = res.scalars().all()
    count = 0

    for asset in assets:
        symbol = (asset.symbol or "").strip()
        if not symbol:
            continue
            
        try:
            hist = await asyncio.to_thread(_fetch_history_sync, symbol, start_date)

            if hist is None or hist.empty:
                continue

            for date_idx, row in hist.iterrows():
                try:
                    p_date = date_idx.date()
                except Exception:
                    continue

                raw_close = row.get("Close")
                if raw_close is None or pd.isna(raw_close):
                    continue

                try:
                    c_price = float(raw_close)
                    if math.isnan(c_price) or math.isinf(c_price) or c_price <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                # Check if price exists
                check_stmt = select(PriceHistory).where(
                    PriceHistory.asset_id == asset.asset_id,
                    PriceHistory.price_date == p_date
                )
                check_res = await db.execute(check_stmt)
                ph = check_res.scalar_one_or_none()

                if ph is None:
                    ph = PriceHistory(
                        asset_id=asset.asset_id,
                        price_date=p_date,
                        close_price=c_price,
                        source="yfinance"
                    )
                    db.add(ph)
                    count += 1
                else:
                    ph.close_price = c_price
                    ph.source = "yfinance"

            await db.commit()

            # Also sync dividends for this asset
            try:
                from app.services.dividend_engine import sync_dividends_for_asset
                await sync_dividends_for_asset(db, asset.asset_id)
            except Exception as de:
                print(f"Error syncing dividends for symbol {symbol}: {de}")
        except Exception as e:
            await db.rollback()
            print(f"Error fetching price for symbol {symbol}: {e}")
            continue

    return count

async def fetch_asset_price_history(db: AsyncSession, asset_id: int, symbol: str) -> int:
    """
    Helper function to initialize price history for a newly added asset.
    """
    return await update_prices_for_assets(db, asset_ids=[asset_id])
