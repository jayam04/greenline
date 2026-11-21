import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, PriceHistory, Lot, LotSale, NetworthSnapshot, User
from app.services.fifo_engine import process_transaction_event
from services.networth.app.services.snapshot_engine import generate_daily_snapshot as nw_generate_snapshot, recalculate_past_snapshots as nw_recalculate_snapshots

@pytest.mark.anyio
async def test_snapshot_currency_normalization_to_eur():
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # Create user 99 if not present
        u_res = await session.get(User, 99)
        if not u_res:
            test_user = User(user_id=99, username="test_inr_user", password_hash="hash")
            session.add(test_user)
            await session.commit()

        # Create user accounts: Zerodha (INR) and Bank of Ireland (EUR)
        # FX_RATES_TO_EUR: INR = 0.0102, EUR = 1.0
        zerodha = Account(account_name="Zerodha", account_type="demat", currency="INR", user_id=99)
        boi = Account(account_name="BOI", account_type="bank", currency="EUR", user_id=99)
        session.add_all([zerodha, boi])
        await session.commit()
        await session.refresh(zerodha)
        await session.refresh(boi)

        # Deposit 100,000 INR into Zerodha and 500 EUR into BOI
        dep_inr = Transaction(
            user_id=99,
            account_id=zerodha.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2026, 1, 1),
            total_amount=100000.0
        )
        dep_eur = Transaction(
            user_id=99,
            account_id=boi.account_id,
            transaction_type="deposit",
            transaction_date=datetime.date(2026, 1, 1),
            total_amount=500.0
        )
        session.add_all([dep_inr, dep_eur])
        await session.commit()
        await session.refresh(dep_inr)
        await session.refresh(dep_eur)
        await process_transaction_event(session, dep_inr)
        await process_transaction_event(session, dep_eur)

        # Buy Indian stock: 100 shares @ 500 INR = 50,000 INR outlay
        asset = Asset(symbol="TCS.BO", name="Tata Consultancy", asset_type="stock", currency="INR")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        ph = PriceHistory(
            asset_id=asset.asset_id,
            price_date=datetime.date(2026, 1, 4),
            close_price=500.0
        )
        session.add(ph)
        await session.commit()

        buy_tx = Transaction(
            user_id=99,
            account_id=zerodha.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 1, 4),
            quantity=100.0,
            price_per_unit=500.0,
            total_amount=50000.0
        )
        session.add(buy_tx)
        await session.commit()
        await session.refresh(buy_tx)
        await process_transaction_event(session, buy_tx)

        # Recalculate past snapshots for user 99 from 2026-01-01 to 2026-01-11
        # Sunday: 2026-01-04 is Sunday!
        await nw_recalculate_snapshots(session, start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 1, 11), user_id=99)

        # As of 2026-01-04 (Sunday):
        # Zerodha Cash: 100,000 - 50,000 = 50,000 INR -> 50,000 * 0.0102 = 510 EUR
        # BOI Cash: 500 EUR -> 500 EUR
        # Total Cash in EUR: 510 + 500 = 1,010 EUR (NOT 50,500!)
        # Stock Value: 100 * 500 = 50,000 INR -> 50,000 * 0.0102 = 510 EUR (NOT 50,000!)
        # Total Net Worth in EUR: 1,010 + 510 = 1,520 EUR (NOT 100,500!)
        snap_sunday = await nw_generate_snapshot(session, snapshot_date=datetime.date(2026, 1, 4), user_id=99)
        assert round(snap_sunday.cash_balance, 2) == 1010.0, f"Expected 1010.0 EUR cash, got {snap_sunday.cash_balance}"
        assert round(snap_sunday.total_current_value, 2) == 510.0, f"Expected 510.0 EUR stock value, got {snap_sunday.total_current_value}"
        assert round(snap_sunday.net_worth, 2) == 1520.0, f"Expected 1520.0 EUR net worth, got {snap_sunday.net_worth}"

        # Test annual snapshot from networth microservice
        from services.networth.app.api.routers.portfolio import get_annual_snapshot
        current_test_user = User(user_id=99, username="test_inr_user", password_hash="hash")
        annual = await get_annual_snapshot(
            fiscal_year_start="01-01",
            master_currency="EUR",
            db=session,
            current_user=current_test_user
        )
        assert annual.currency == "EUR"
        assert annual.investments_done == 510.0  # 50,000 INR * 0.0102 = 510 EUR
        # Delta is realistic in EUR (not 100,000s)
        assert annual.net_worth_delta < 5000.0
