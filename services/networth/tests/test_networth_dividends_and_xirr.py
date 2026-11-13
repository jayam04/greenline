import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Account, Asset, Transaction, Lot, CashFlow
from services.networth.app.api.routers.portfolio import get_portfolio_summary


@pytest.mark.anyio
async def test_networth_service_calculates_dividends_and_holding_xirr(db_session: AsyncSession):
    session = db_session
    user = User(
        username="networth_div_user",
        email="networth_div@example.com",
        password_hash="testhash"
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    acc = Account(
        user_id=user.user_id,
        account_name="Interactive Brokers",
        broker_name="IBKR",
        account_type="demat",
        currency="USD"
    )
    session.add(acc)
    await session.commit()
    await session.refresh(acc)

    asset = Asset(
        symbol="MSFT",
        name="Microsoft Corp",
        asset_type="stock",
        sector="Technology",
        currency="USD"
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)

    # Buy 100 shares @ $300 on 2025-01-01
    buy_date = datetime.date(2025, 1, 1)
    buy_tx = Transaction(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        transaction_type="buy",
        transaction_date=buy_date,
        quantity=100.0,
        price_per_unit=300.0,
        fees=10.0,
        taxes=0.0,
        total_amount=30010.0
    )
    session.add(buy_tx)
    await session.commit()
    await session.refresh(buy_tx)

    lot = Lot(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        buy_transaction_id=buy_tx.transaction_id,
        buy_date=buy_date,
        quantity_original=100.0,
        quantity_remaining=100.0,
        cost_per_unit=300.10
    )
    session.add(lot)

    # Cashflow for buy: -$30,010
    cf_buy = CashFlow(
        user_id=user.user_id,
        scope_type="asset",
        scope_id=asset.asset_id,
        flow_date=buy_date,
        amount=-30010.0,
        flow_type="buy"
    )
    session.add(cf_buy)

    # Dividend on 2025-06-01: $500 total, $50 taxes -> $450 net
    div_date = datetime.date(2025, 6, 1)
    div_tx = Transaction(
        user_id=user.user_id,
        account_id=acc.account_id,
        asset_id=asset.asset_id,
        transaction_type="dividend",
        transaction_date=div_date,
        quantity=100.0,
        price_per_unit=5.0,
        fees=0.0,
        taxes=50.0,
        total_amount=500.0
    )
    session.add(div_tx)

    # Cashflow for dividend: +$450
    cf_div = CashFlow(
        user_id=user.user_id,
        scope_type="asset",
        scope_id=asset.asset_id,
        flow_date=div_date,
        amount=450.0,
        flow_type="dividend"
    )
    session.add(cf_div)
    await session.commit()

    # Call get_portfolio_summary
    summary = await get_portfolio_summary(account_id=acc.account_id, db=session, current_user=user)

    # Assert dividend is included in portfolio summary
    assert round(summary.total_dividend_income, 2) == 450.00, f"Expected 450.00 dividend income, got {summary.total_dividend_income}"
    assert round(summary.total_realized_pnl, 2) == 450.00, f"Expected 450.00 realized PnL from dividends, got {summary.total_realized_pnl}"

    # Assert holding level fields
    assert len(summary.top_holdings) == 1
    h = summary.top_holdings[0]
    assert h.asset_id == asset.asset_id
    assert round(h.dividend_income, 2) == 450.00, f"Expected holding dividend income 450.00, got {h.dividend_income}"
    assert round(h.realized_pnl, 2) == 450.00, f"Expected holding realized PnL 450.00, got {h.realized_pnl}"
    assert h.xirr is not None, "Expected holding XIRR to be populated, got None"
    assert isinstance(h.xirr, float), f"Expected float XIRR, got {type(h.xirr)}"
