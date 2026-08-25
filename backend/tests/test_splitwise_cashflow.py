import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, CashflowTransaction, CashflowPayment, CashflowItem, User
from app.schemas.schemas import CashflowTransactionCreate, CashflowPaymentCreate, CashflowItemCreate
from app.services.cashflow_engine import seed_default_categories, build_category_lineage_map, get_cashflow_summary
from app.api.routers.cashflow import create_cashflow_transaction
from app.api.routers.accounts import calculate_all_account_balances

@pytest.mark.anyio
async def test_splitwise_dinner_expense_and_balances():
    """
    Test scenario:
    - Initial Bank balance = 2000 INR
    - Dinner bill = 1000 INR (Food & Dining)
    - Friend reimbursement / split = -500 INR (Food & Dining)
    - Net payment from Bank = 500 INR
    - Verify:
      1. Transaction is created and classified as EXPENSE with total 500.
      2. Bank balance reduces by exactly 500 (becomes 1500).
      3. Summary total_expenses reflects net 500.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # Create Bank Account
        bank = Account(account_name="Main Bank", broker_name="HDFC", account_type="bank", currency="INR")
        session.add(bank)
        await session.commit()
        await session.refresh(bank)

        # Initial deposit/income of 2000 INR
        salary_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Base Salary")
        init_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 1),
            title="Initial Balance",
            total_amount=2000.0,
            currency="INR"
        )
        session.add(init_tx)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=init_tx.cashflow_id, account_id=bank.account_id, amount=2000.0))
        session.add(CashflowItem(cashflow_id=init_tx.cashflow_id, category_id=salary_cat.category_id, amount=2000.0, label="ESSENTIAL"))
        await session.commit()

        balances = await calculate_all_account_balances(session)
        assert balances[bank.account_id] == 2000.0

        # Find Food & Dining category
        dining_cat = next(v["category"] for v in lineage_map.values() if "Food" in v["category"].name or "Dining" in v["category"].name or "Restaurant" in v["category"].name)

        # Create Splitwise dinner expense:
        # Item 1: Dinner = +1000
        # Item 2: Splitwise Friend share = -500
        # Payment: 500 from Bank
        tx_in = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 15),
            title="Dinner with Friends",
            total_amount=500.0,
            currency="INR",
            transaction_kind="EXPENSE",
            payments=[CashflowPaymentCreate(account_id=bank.account_id, amount=-500.0)],
            items=[
                CashflowItemCreate(category_id=dining_cat.category_id, amount=1000.0, label="DISCRETIONARY", description="Dinner bill"),
                CashflowItemCreate(category_id=dining_cat.category_id, amount=-500.0, label="DISCRETIONARY", description="Friend reimbursement")
            ]
        )

        user = User(user_id=1, username="admin", password_hash="dummy")
        res = await create_cashflow_transaction(tx_in, db=session, current_user=user)

        assert res.total_amount == 500.0
        assert res.transaction_kind == "EXPENSE"
        assert len(res.items) == 2
        assert res.items[0].amount == 1000.0
        assert res.items[1].amount == -500.0

        # Verify Account Balance after split expense
        balances_after = await calculate_all_account_balances(session)
        assert balances_after[bank.account_id] == 1500.0

        # Verify Cashflow Summary
        summary = await get_cashflow_summary(session, master_currency="INR")
        assert summary.total_income == 2000.0
        assert summary.total_expenses == 500.0
        assert summary.net_savings == 1500.0

@pytest.mark.anyio
async def test_splitwise_multi_account_settlement():
    """
    Test scenario:
    - Paid 1000 INR from Cash Wallet.
    - Friend sent 500 INR to UPI/Bank.
    - Net payment = 500 INR.
    - Verify Cash Wallet decreases by 1000 and UPI/Bank increases by 500.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        wallet = Account(account_name="Cash Wallet", broker_name="Cash", account_type="bank", currency="INR")
        upi = Account(account_name="UPI Bank", broker_name="SBI", account_type="bank", currency="INR")
        session.add_all([wallet, upi])
        await session.commit()
        await session.refresh(wallet)
        await session.refresh(upi)

        dining_cat = next(v["category"] for v in lineage_map.values() if "Food" in v["category"].name or "Dining" in v["category"].name or "Restaurant" in v["category"].name)

        tx_in = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 20),
            title="Team Lunch Split",
            total_amount=500.0,
            currency="INR",
            transaction_kind="EXPENSE",
            payments=[
                CashflowPaymentCreate(account_id=wallet.account_id, amount=-1000.0),
                CashflowPaymentCreate(account_id=upi.account_id, amount=500.0),
            ],
            items=[
                CashflowItemCreate(category_id=dining_cat.category_id, amount=1000.0, label="DISCRETIONARY", description="Lunch bill"),
                CashflowItemCreate(category_id=dining_cat.category_id, amount=-500.0, label="DISCRETIONARY", description="Colleague UPI payment"),
            ]
        )

        user = User(user_id=1, username="admin", password_hash="dummy")
        res = await create_cashflow_transaction(tx_in, db=session, current_user=user)

        assert res.total_amount == 500.0
        assert res.transaction_kind == "EXPENSE"

        balances = await calculate_all_account_balances(session)
        assert balances[wallet.account_id] == -1000.0
        assert balances[upi.account_id] == 500.0
