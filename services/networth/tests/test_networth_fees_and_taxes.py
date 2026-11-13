import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Account, Asset, Transaction, Lot, LotSale
from services.networth.app.api.routers.portfolio import get_portfolio_summary


@pytest.mark.anyio
async def test_networth_service_calculates_fees_and_taxes(db_session: AsyncSession):
    session = db_session
    # Setup test user
    user = User(
        username="networth_fees_user",
        email="networth_fees@example.com",
        password_hash="testhash"
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Setup brokerage account
    acc = Account(
        user_id=user.user_id,
        account_name="Zerodha Demat",
        broker_name="Zerodha",
        account_type="demat",
        currency="INR"
    )
    session.add(acc)
    await session.commit()
    await session.refresh(acc)

    # Setup Asset
    asset = Asset(
        symbol="INFY",
        name="Infosys Ltd",
        asset_type="stock",
        sector="Technology",
        currency="INR"
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)

    # Buy 100 shares @ 1000 INR with 300 fees and 100 taxes
    buy_tx = Transaction(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        transaction_type="buy",
        transaction_date=datetime.date(2026, 1, 15),
        quantity=100.0,
        price_per_unit=1000.0,
        fees=300.0,
        taxes=100.0,
        total_amount=100400.0
    )
    session.add(buy_tx)
    await session.commit()
    await session.refresh(buy_tx)

    # Create lot for buy
    lot = Lot(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        buy_transaction_id=buy_tx.transaction_id,
        buy_date=buy_tx.transaction_date,
        quantity_original=100.0,
        quantity_remaining=50.0,
        cost_per_unit=1004.0
    )
    session.add(lot)
    await session.commit()
    await session.refresh(lot)

    # Sell 50 shares @ 1200 INR with 200 fees and 50 taxes
    sell_tx = Transaction(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        transaction_type="sell",
        transaction_date=datetime.date(2026, 2, 15),
        quantity=50.0,
        price_per_unit=1200.0,
        fees=200.0,
        taxes=50.0,
        total_amount=59750.0
    )
    session.add(sell_tx)
    await session.commit()
    await session.refresh(sell_tx)

    # Create lot sale
    lot_sale = LotSale(
        user_id=user.user_id,
        lot_id=lot.lot_id,
        sell_transaction_id=sell_tx.transaction_id,
        quantity_sold=50.0,
        cost_basis=50200.0,
        sale_price_per_unit=1195.0,
        realized_pnl=9550.0,
        holding_period_days=31
    )
    session.add(lot_sale)
    await session.commit()

    # Call get_portfolio_summary from networth microservice
    summary = await get_portfolio_summary(account_id=acc.account_id, db=session, current_user=user)

    # Assert portfolio level fees and taxes
    assert round(summary.total_fees, 2) == 500.00, f"Expected 500.00 fees, got {summary.total_fees}"
    assert round(summary.total_taxes, 2) == 150.00, f"Expected 150.00 taxes, got {summary.total_taxes}"

    # Assert holding level fees and taxes
    assert len(summary.top_holdings) == 1
    h = summary.top_holdings[0]
    assert h.asset_id == asset.asset_id
    assert round(h.total_fees, 2) == 500.00, f"Expected holding fees 500.00, got {h.total_fees}"
    assert round(h.total_taxes, 2) == 150.00, f"Expected holding taxes 150.00, got {h.total_taxes}"
    assert round(h.fees_and_taxes, 2) == 650.00, f"Expected holding fees_and_taxes 650.00, got {h.fees_and_taxes}"
