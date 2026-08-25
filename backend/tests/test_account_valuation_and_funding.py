import datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, Account, Asset, PriceHistory, CashflowTransaction, CashflowPayment
from app.schemas.schemas import TransactionCreate
from app.api.routers.transactions import create_transaction
from app.api.routers.accounts import calculate_all_account_balances, calculate_all_account_cash_balances, list_accounts

@pytest.mark.anyio
async def test_precize_wallet_zero_and_demat_valuation():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        user = User(username="admin", password_hash="hash")
        session.add(user)

        # 1. Accounts: Bank of India (5), Precize Wallet (3), Jhaveri Securities (4)
        boi = Account(account_id=5, account_name="Bank of India", account_type="bank", currency="INR", created_at=datetime.date(2025, 9, 1))
        precize = Account(account_id=3, account_name="Precize Wallet", account_type="bank", currency="INR", created_at=datetime.date(2025, 9, 1))
        jhaveri = Account(account_id=4, account_name="Jhaveri Securities", account_type="demat", currency="INR", created_at=datetime.date(2025, 9, 1))
        session.add_all([boi, precize, jhaveri])

        # 2. Asset: GROWW.BO
        groww = Asset(asset_id=4, symbol="GROWW.BO", name="Billionbrains Garage Ventures Limited", asset_type="stock", currency="INR")
        session.add(groww)
        await session.commit()

        # 3. Transfer from BOI to Precize Wallet (+30,847.64 on Precize, -30,847.64 on BOI)
        ctx = CashflowTransaction(
            cashflow_id=1,
            transaction_date=datetime.date(2025, 9, 19),
            title="Fund Precize Wallet",
            total_amount=30847.64,
            transaction_kind="TRANSFER",
            currency="INR",
            created_at=datetime.date(2025, 9, 19)
        )
        session.add(ctx)
        p1 = CashflowPayment(cashflow_id=1, account_id=5, amount=-30847.64)
        p2 = CashflowPayment(cashflow_id=1, account_id=3, amount=30847.64)
        session.add_all([p1, p2])
        await session.commit()

        # 4. Buy 186 shares of GROWW.BO in Jhaveri Securities funded by Precize Wallet
        # Gross = 186 * 162 = 30,132.00
        # Fees = 602.64, Taxes = 113.00
        # Total Outlay = 30,847.64
        buy_tx = TransactionCreate(
            account_id=4,
            funding_account_id=3,
            asset_id=4,
            transaction_type="buy",
            transaction_date=datetime.date(2025, 9, 19),
            quantity=186.0,
            price_per_unit=162.0,
            total_amount=30847.64,
            fees=602.64,
            taxes=113.00,
            notes="Unlisted shares purchase"
        )
        await create_transaction(buy_tx, db=session, current_user=user)

        # 5. Add Latest Price for GROWW.BO = 202.80 INR
        ph = PriceHistory(asset_id=4, price_date=datetime.date(2026, 8, 25), close_price=202.80)
        session.add(ph)
        await session.commit()

        # 6. Check Account Balances
        cash_bals = await calculate_all_account_cash_balances(session)
        balances = await calculate_all_account_balances(session)
        
        # Precize Wallet (Account 3):
        # Cash Inflow: +30,847.64
        # Cash Outflow: -30,847.64
        # Net Balance = 0.00 INR (NOT -715.xx!)
        assert cash_bals[3] == 0.0
        assert balances[3] == 0.0

        # Jhaveri Securities (Account 4):
        # Uninvested Cash = 0.00
        # Securities Value = 186 * 202.80 = 37,720.80 INR
        # Total Account Value = 37,720.80 INR (NOT 0!)
        assert cash_bals[4] == 0.0
        assert round(balances[4], 2) == 37720.80

        # 7. Check list_accounts endpoint response
        accounts_resp = await list_accounts(db=session, current_user=user)
        precize_resp = next(a for a in accounts_resp if a.account_id == 3)
        jhaveri_resp = next(a for a in accounts_resp if a.account_id == 4)

        assert precize_resp.current_balance == 0.0
        assert precize_resp.cash_balance == 0.0
        assert precize_resp.securities_value == 0.0

        assert round(jhaveri_resp.current_balance, 2) == 37720.80
        assert jhaveri_resp.cash_balance == 0.0
        assert round(jhaveri_resp.securities_value, 2) == 37720.80
