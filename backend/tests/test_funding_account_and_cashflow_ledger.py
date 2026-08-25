import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, Lot, Dividend, User
from app.schemas.schemas import TransactionCreate
from app.api.routers.transactions import create_transaction, list_transactions
from app.api.routers.accounts import calculate_all_account_balances, calculate_all_account_cash_balances

@pytest.mark.anyio
async def test_funding_account_ipo_and_trades():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # 1. Create Holding Account (Zerodha Demat) and Funding Account (Axis Bank)
        zerodha = Account(account_name="Zerodha Demat", broker_name="Zerodha", account_type="demat", currency="INR")
        axis_bank = Account(account_name="Axis Bank", broker_name="Axis", account_type="bank", currency="INR")
        session.add_all([zerodha, axis_bank])
        await session.commit()
        await session.refresh(zerodha)
        await session.refresh(axis_bank)

        # 2. Create Asset (HDFC Bank)
        hdfc = Asset(symbol="HDFCBANK", name="HDFC Bank Limited", asset_type="stock", exchange="NSE", currency="INR")
        session.add(hdfc)
        await session.commit()
        await session.refresh(hdfc)

        zerodha_id = zerodha.account_id
        axis_id = axis_bank.account_id
        hdfc_id = hdfc.asset_id

        user = User(user_id=1, username="admin", password_hash="dummy")

        # 3. Buy 100 shares of HDFCBANK @ 1000 INR (1,00,000 INR total)
        # Holding Account: Zerodha Demat
        # Funding Account: Axis Bank (IPO / Bank deduction)
        tx_in = TransactionCreate(
            account_id=zerodha_id,
            funding_account_id=axis_id,
            asset_id=hdfc_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 1),
            quantity=100.0,
            price_per_unit=1000.0,
            total_amount=100000.0,
            fees=0.0,
            taxes=0.0,
            notes="IPO allotment debited from Axis Bank"
        )
        created_tx = await create_transaction(tx_in, db=session, current_user=user)

        assert created_tx.account_id == zerodha_id
        assert created_tx.funding_account_id == axis_id
        assert created_tx.funding_account_name == "Axis Bank"
        assert created_tx.account_name == "Zerodha Demat"

        # 4. Verify Account Balances:
        # - Zerodha cash balance: 0.0 (lots are in Zerodha, but cash was deducted from Axis Bank)
        # - Zerodha total balance: 100,000.0 (100 shares @ 1000.0)
        # - Axis Bank balance: -100,000.0
        cash_bals = await calculate_all_account_cash_balances(session)
        tot_bals = await calculate_all_account_balances(session)
        assert cash_bals[zerodha_id] == 0.0
        assert tot_bals[zerodha_id] == 100000.0
        assert cash_bals[axis_id] == -100000.0
        assert tot_bals[axis_id] == -100000.0

        # 5. Verify Dividend payout deposited into Axis Bank (+5,000 INR)
        div_in = TransactionCreate(
            account_id=zerodha_id,
            funding_account_id=axis_id,
            asset_id=hdfc_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2026, 8, 15),
            total_amount=5000.0,
            notes="Q1 Dividend deposited into bank"
        )
        await create_transaction(div_in, db=session, current_user=user)

        cash_bals_after = await calculate_all_account_cash_balances(session)
        assert cash_bals_after[zerodha_id] == 0.0
        assert cash_bals_after[axis_id] == -95000.0 # -100,000 + 5,000 = -95,000

        # 6. List transactions and verify response fields
        tx_list = await list_transactions(db=session, current_user=user)
        assert len(tx_list) == 2
        ipo_tx = next(t for t in tx_list if t.transaction_type == "buy")
        assert ipo_tx.account_name == "Zerodha Demat"
        assert ipo_tx.funding_account_name == "Axis Bank"
