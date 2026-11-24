from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
import yfinance as yf
from app.db.database import get_db
from app.db.models import Benchmark, User
from app.schemas.schemas import BenchmarkResponse, BenchmarkDataPoint
from app.api.deps import get_current_user

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

@router.get("", response_model=BenchmarkResponse)
@router.get("/", response_model=BenchmarkResponse)
async def get_benchmark(
    symbol: str = Query("^GSPC", description="Yahoo Finance ticker, e.g., ^GSPC for S&P 500, BTC-USD for Bitcoin, or ^NSEI for Nifty 50"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    clean_sym = symbol.strip().upper()
    actual_ticker = clean_sym
    
    if clean_sym in ["^GSPC", "SP500", "S&P 500"]:
        name = "S&P 500"
        actual_ticker = "^GSPC"
    elif clean_sym in ["BTC", "BTC-USD", "BITCOIN"]:
        name = "Bitcoin"
        actual_ticker = "BTC-USD"
    elif clean_sym in ["^NSEI", "NIFTY", "NIFTY 50"]:
        name = "Nifty 50"
        actual_ticker = "^NSEI"
    else:
        name = clean_sym
        actual_ticker = clean_sym
    
    # Try fetching from DB first
    stmt = (
        select(Benchmark)
        .where(Benchmark.benchmark_name == name)
        .order_by(asc(Benchmark.price_date))
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    if not records or len(records) < 5:
        try:
            ticker = yf.Ticker(actual_ticker)
            hist = ticker.history(period="2y")
            for date_idx, row in hist.iterrows():
                p_date = date_idx.date()
                c_val = float(row["Close"])
                
                # Check if existing record exists
                exist_stmt = select(Benchmark).where(
                    Benchmark.benchmark_name == name,
                    Benchmark.price_date == p_date
                )
                exist_res = await db.execute(exist_stmt)
                if not exist_res.scalar_one_or_none():
                    bm = Benchmark(benchmark_name=name, price_date=p_date, close_value=c_val)
                    db.add(bm)
            await db.commit()
            
            res = await db.execute(stmt)
            records = res.scalars().all()
        except Exception as e:
            print(f"[Benchmark] Error fetching {actual_ticker}: {e}")
            
    data_points = [BenchmarkDataPoint(price_date=r.price_date, close_value=r.close_value) for r in records]
    return BenchmarkResponse(benchmark_name=name, data=data_points)
