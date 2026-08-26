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
