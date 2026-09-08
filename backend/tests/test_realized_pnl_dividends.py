import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import Account, Asset, Transaction, PriceHistory, User
from app.services.fifo_engine import recalculate_all_lots

@pytest.mark.anyio
async def test_realized_pnl_includes_net_dividends():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="pnl_div_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank_acc = Account(account_name="Main Bank", account_type="bank", currency="USD")
        session.add(bank_acc)
        await session.commit()
        await session.refresh(bank_acc)
        bank_id = bank_acc.account_id

        demat_acc = Account(account_name="Main Demat", account_type="demat", currency="USD")
        session.add(demat_acc)
        await session.commit()
        await session.refresh(demat_acc)
        demat_id = demat_acc.account_id

        # Deposit initial $10,000 into bank
        session.add(Transaction(
            account_id=bank_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2024, 1, 1),
            total_amount=10000.0
        ))

        asset = Asset(symbol="IBM", name="IBM Corp", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        asset_id = asset.asset_id

        # 1. Buy 100 shares @ $100 = $10,000 from bank
        buy_tx = Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2024, 1, 15),
            quantity=100.0,
            price_per_unit=100.0,
            total_amount=10000.0
        )
        session.add(buy_tx)

        # 2. Sell 40 shares @ $120 = $4,800 to bank (Capital gain = 40 * (120 - 100) = $800)
        sell_tx = Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2024, 6, 1),
            quantity=40.0,
            price_per_unit=120.0,
            total_amount=4800.0
        )
        session.add(sell_tx)

        # 3. Dividend received: $200 gross, $30 tax = $170 net dividend
        # Notice: funding_account_id=None initially (unlinked)
        div_tx = Transaction(
            account_id=demat_id,
            funding_account_id=None,
            asset_id=asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2024, 7, 1),
            quantity=60.0,
            price_per_unit=3.3333,
            total_amount=200.0,
            taxes=30.0,
            source="yfinance_auto"
        )
        session.add(div_tx)
        await session.commit()
        await session.refresh(div_tx)
        div_id = div_tx.transaction_id

        # 4. Current price: $110 per share for remaining 60 shares (Current Value = $6,600, Cost = $6,000, Unrealized = $600)
        session.add(PriceHistory(
            asset_id=asset_id,
            price_date=datetime.date(2024, 8, 1),
            close_price=110.0,
            source="manual"
        ))
        await session.commit()
        await recalculate_all_lots(session)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Check Portfolio Summary
            res = await ac.get("/api/v1/portfolio/summary?target_currency=USD")
            assert res.status_code == 200
            data = res.json()

            # Capital Gains Realized = $800
            # Net Dividends = $200 - $30 = $170
            # Total Realized P&L = $800 + $170 = $970
            assert data["total_realized_pnl"] == 970.0

            # Holdings check
            holding = data["top_holdings"][0]
            assert holding["symbol"] == "IBM"
            assert holding["realized_pnl"] == 970.0
            assert holding["dividend_income"] == 170.0
            assert holding["unrealized_pnl"] == 600.0
            assert holding["net_pnl"] == 1570.0 # 970 realized + 600 unrealized

            # Cash balance check: Since dividend is unlinked, bank cash balance must only reflect $10,000 - $10,000 + $4,800 = $4,800
            accounts_res = await ac.get("/api/v1/accounts/")
            accs = accounts_res.json()
            bank_item = next(a for a in accs if a["account_id"] == bank_id)
            assert bank_item["cash_balance"] == 4800.0

            # Now resolve dividend by linking to bank_acc
            await ac.post("/api/v1/discrepancies/resolve", json={
                "resolutions": [
                    {
                        "transaction_id": div_id,
                        "funding_account_id": bank_id
                    }
                ]
            })

            # Bank cash balance should now be $4,800 + $170 = $4,970
            accounts_res2 = await ac.get("/api/v1/accounts/")
            accs2 = accounts_res2.json()
            bank_item2 = next(a for a in accs2 if a["account_id"] == bank_id)
            assert bank_item2["cash_balance"] == 4970.0

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_realized_pnl_multi_lot_fifo_dividends_and_custom_valuations():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="multi_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        bank = Account(account_name="Trading Bank", account_type="bank", currency="USD")
        demat = Account(account_name="Trading Demat", account_type="demat", currency="USD")
        session.add_all([bank, demat])
        await session.commit()
        await session.refresh(bank)
        await session.refresh(demat)
        bank_id = bank.account_id
        demat_id = demat.account_id

        asset = Asset(symbol="GOOGL", name="Alphabet Inc", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # Deposit $20,000
        session.add(Transaction(
            account_id=bank_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2026, 1, 1),
            total_amount=20000.0
        ))

        # Lot 1: Buy 50 shares @ $100
        session.add(Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 1, 10),
            quantity=50.0,
            price_per_unit=100.0,
            total_amount=5000.0
        ))

        # Lot 2: Buy 50 shares @ $120
        session.add(Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 2, 10),
            quantity=50.0,
            price_per_unit=120.0,
            total_amount=6000.0
        ))

        # Dividend 1: $150 gross, $25 tax = $125 net
        session.add(Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2026, 3, 1),
            quantity=100.0,
            price_per_unit=1.5,
            total_amount=150.0,
            taxes=25.0
        ))

        # Sell 60 shares @ $150 = $9,000 proceeds
        session.add(Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2026, 4, 1),
            quantity=60.0,
            price_per_unit=150.0,
            total_amount=9000.0
        ))

        # Dividend 2: $80 gross, $10 tax = $70 net
        session.add(Transaction(
            account_id=demat_id,
            funding_account_id=bank_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2026, 5, 1),
            quantity=40.0,
            price_per_unit=2.0,
            total_amount=80.0,
            taxes=10.0
        ))

        # Custom Valuation: manual price $160 on 2026-06-01
        session.add(PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2026, 6, 1),
            close_price=160.0,
            source="manual"
        ))

        await session.commit()
        await recalculate_all_lots(session)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Check Portfolio Summary
            res = await ac.get("/api/v1/portfolio/summary?target_currency=USD")
            assert res.status_code == 200
            data = res.json()

            # Realized Capital Gains = (50 * 50) + (10 * 30) = $2,800
            # Net Dividends = $125 + $70 = $195
            # Total Realized P&L = $2,800 + $195 = $2,995
            assert data["total_realized_pnl"] == 2995.0
            # Open lots remaining: 40 shares @ $120 cost = $4,800
            # Current valuation: 40 shares @ $160 = $6,400
            # Unrealized = $6,400 - $4,800 = $1,600
            assert data["total_unrealized_pnl"] == 1600.0
            assert data["total_current_value"] == 6400.0

            holding = data["top_holdings"][0]
            assert holding["symbol"] == "GOOGL"
            assert holding["capital_gains_realized"] == 2800.0
            assert holding["dividend_income"] == 195.0
            assert holding["realized_pnl"] == 2995.0
            assert holding["unrealized_pnl"] == 1600.0
            assert holding["net_pnl"] == 4595.0

            # 2. Check Accounts
            res_acc = await ac.get("/api/v1/accounts/")
            assert res_acc.status_code == 200
            accs = res_acc.json()

            bank_row = next(a for a in accs if a["account_id"] == bank_id)
            # Cash = 20000 - 5000 - 6000 + 125 + 9000 + 70 = 18195.0
            assert bank_row["cash_balance"] == 18195.0
            assert bank_row["securities_value"] == 0.0
            assert bank_row["current_balance"] == 18195.0

            demat_row = next(a for a in accs if a["account_id"] == demat_id)
            assert demat_row["cash_balance"] == 0.0
            assert demat_row["securities_value"] == 6400.0
            assert demat_row["current_balance"] == 6400.0

            # Total Net Worth = 18195 + 6400 = 24595.0
            assert data["total_net_worth"] == 24595.0
    finally:
        app.dependency_overrides.clear()

