import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import Account, Asset, Lot, LotSale, PriceHistory, User
from app.schemas.schemas import TransactionCreate
from app.api.routers.transactions import create_transaction
from app.api.routers.portfolio import get_portfolio_summary

@pytest.mark.anyio
async def test_fees_taxes_included_in_stock_pnl():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # 1. Setup account and asset
        zerodha = Account(account_name="Zerodha Demat", broker_name="Zerodha", account_type="demat", currency="INR")
        session.add(zerodha)
        await session.commit()
        await session.refresh(zerodha)
        acc_id = zerodha.account_id

        tcs = Asset(symbol="TCS", name="Tata Consultancy Services", asset_type="stock", exchange="NSE", currency="INR")
        session.add(tcs)
        await session.commit()
        await session.refresh(tcs)
        asset_id = tcs.asset_id

        user = User(user_id=1, username="admin", password_hash="dummy")

        # 2. Buy 100 shares of TCS @ 3,000 INR with 300 INR fees and 100 INR taxes
        # Gross = 300,000. Total Cost Basis = 300,400. Cost/unit = 3,004.00
        buy_tx = TransactionCreate(
            account_id=acc_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 7, 1),
            quantity=100.0,
            price_per_unit=3000.0,
            total_amount=300000.0,
            fees=300.0,
            taxes=100.0,
            notes="Buy TCS with brokerage & STT"
        )
        await create_transaction(buy_tx, db=session, current_user=user)

        # Verify Lot cost_per_unit includes fees and taxes
        lot_res = await session.execute(select(Lot).where(Lot.asset_id == asset_id))
        lot = lot_res.scalar_one()
        assert lot.quantity_original == 100.0
        assert lot.quantity_remaining == 100.0
        assert round(lot.cost_per_unit, 2) == 3004.00

        # Set market price to 3,500 INR
        ph = PriceHistory(asset_id=asset_id, price_date=datetime.date(2026, 7, 2), close_price=3500.0)
        session.add(ph)
        await session.commit()

        # Check Portfolio Summary before selling:
        # Current Value = 100 * 3,500 = 350,000
        # Total Cost = 300,400
        # Unrealized PnL = 350,000 - 300,400 = +49,600
        summary = await get_portfolio_summary(account_id=acc_id, db=session, current_user=user)
        holding = next(h for h in summary.top_holdings if h.asset_id == asset_id)
        assert round(holding.total_cost, 2) == 300400.00
        assert round(holding.current_value, 2) == 350000.00
        assert round(holding.unrealized_pnl, 2) == 49600.00
        assert round(holding.realized_pnl, 2) == 0.00

        # 3. Sell 50 shares of TCS @ 3,600 INR with 200 INR fees and 50 INR taxes
        # Gross = 180,000. Net Proceeds = 179,750 (3,595.00/sh)
        # Cost Basis of 50 shares = 50 * 3,004.00 = 150,200
        # Realized PnL = 179,750 - 150,200 = +29,550
        sell_tx = TransactionCreate(
            account_id=acc_id,
            asset_id=asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=50.0,
            price_per_unit=3600.0,
            total_amount=180000.0,
            fees=200.0,
            taxes=50.0,
            notes="Partial sell of 50 shares"
        )
        await create_transaction(sell_tx, db=session, current_user=user)

        # Check LotSale record
        sale_res = await session.execute(select(LotSale).where(LotSale.lot_id == lot.lot_id))
        lot_sale = sale_res.scalar_one()
        assert lot_sale.quantity_sold == 50.0
        assert round(lot_sale.cost_basis, 2) == 150200.00
        assert round(lot_sale.sale_price_per_unit, 2) == 3595.00
        assert round(lot_sale.realized_pnl, 2) == 29550.00

        # Check Summary after partial sell:
        # Latest price is 3,600 INR (from the 2026-08-01 sell tx):
        # Remaining 50 shares at 3,600 INR:
        # Current Value = 50 * 3,600 = 180,000
        # Total Cost = 50 * 3,004.00 = 150,200
        # Unrealized PnL = 180,000 - 150,200 = +29,800
        # Realized PnL = +29,550
        # Total Fees = 300 + 200 = 500
        # Total Taxes = 100 + 50 = 150
        summary_after = await get_portfolio_summary(account_id=acc_id, db=session, current_user=user)
        holding_after = next(h for h in summary_after.top_holdings if h.asset_id == asset_id)
        assert holding_after.quantity_held == 50.0
        assert round(holding_after.total_cost, 2) == 150200.00
        assert round(holding_after.current_value, 2) == 180000.00
        assert round(holding_after.unrealized_pnl, 2) == 29800.00
        assert round(holding_after.realized_pnl, 2) == 29550.00
        assert round(holding_after.fees_and_taxes, 2) == 650.00
        assert round(holding_after.net_pnl, 2) == 59350.00
        assert round(summary_after.total_fees, 2) == 500.00
        assert round(summary_after.total_taxes, 2) == 150.00
