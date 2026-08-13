from typing import List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
import yfinance as yf
import datetime
from app.db.database import get_db
from app.db.models import Benchmark, User
from app.schemas.schemas import BenchmarkResponse, BenchmarkDataPoint
from app.api.deps import get_current_user

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

@router.get("/", response_model=BenchmarkResponse)
async def get_benchmark(
    symbol: str = Query("^GSPC", description="Yahoo Finance ticker, e.g., ^GSPC for S&P 500 or ^NSEI for Nifty 50"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = "S&P 500" if symbol == "^GSPC" else ("Nifty 50" if symbol == "^NSEI" else symbol)
    
    # Try fetching from DB first
    stmt = (
        select(Benchmark)
        .where(Benchmark.benchmark_name == name)
        .order_by(asc(Benchmark.price_date))
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    if not records:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y")
            for date_idx, row in hist.iterrows():
                p_date = date_idx.date()
                c_val = float(row["Close"])
                bm = Benchmark(benchmark_name=name, price_date=p_date, close_value=c_val)
                db.add(bm)
            await db.commit()
            
            res = await db.execute(stmt)
            records = res.scalars().all()
        except Exception:
            pass
            
    data_points = [BenchmarkDataPoint(price_date=r.price_date, close_value=r.close_value) for r in records]
    return BenchmarkResponse(benchmark_name=name, data=data_points)
