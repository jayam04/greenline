import datetime
from typing import List, Optional
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Asset, PriceHistory

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
        symbol = asset.symbol.strip()
        if not symbol:
            continue
            
        try:
            ticker = yf.Ticker(symbol)
            if start_date:
                start_str = start_date.strftime("%Y-%m-%d")
                hist = ticker.history(start=start_str)
            else:
                hist = ticker.history(period="1y")

            if hist.empty:
                continue

            for date_idx, row in hist.iterrows():
                p_date = date_idx.date()
                c_price = float(row["Close"])

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
        except Exception as e:
            print(f"Error fetching price for symbol {symbol}: {e}")
            continue

    return count
