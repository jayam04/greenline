import pytest
import datetime
from unittest.mock import patch
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Asset, PriceHistory
from app.services.price_engine import update_prices_for_assets

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_update_prices_for_assets_threadpool():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        ast = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock")
        session.add(ast)
        await session.commit()
        await session.refresh(ast)

        # Mock DataFrame returned by yfinance history
        dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
        mock_df = pd.DataFrame(
            {"Close": [185.5, 187.0]},
            index=dates
        )

        with patch("app.services.price_engine._fetch_history_sync", return_value=mock_df) as mock_hist:
            count = await update_prices_for_assets(session, asset_ids=[ast.asset_id])
            assert count == 2
            mock_hist.assert_called_once_with("AAPL", None)

            # Verify prices in DB
            stmt = select(PriceHistory).where(PriceHistory.asset_id == ast.asset_id).order_by(PriceHistory.price_date)
            res = await session.execute(stmt)
            prices = res.scalars().all()
            assert len(prices) == 2
            assert prices[0].price_date == datetime.date(2025, 1, 2)
            assert prices[0].close_price == 185.5
            assert prices[1].price_date == datetime.date(2025, 1, 3)
            assert prices[1].close_price == 187.0

@pytest.mark.anyio
async def test_update_prices_for_assets_error_handling():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        ast = Asset(symbol="INVALID", name="Invalid Ticker", asset_type="stock")
        session.add(ast)
        await session.commit()
        await session.refresh(ast)

        with patch("app.services.price_engine._fetch_history_sync", side_effect=Exception("Failed to download")):
            count = await update_prices_for_assets(session, asset_ids=[ast.asset_id])
            assert count == 0
