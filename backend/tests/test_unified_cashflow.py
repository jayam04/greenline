import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, Category, CashflowTransaction, CashflowPayment, CashflowItem, User
from app.schemas.schemas import CashflowTransactionCreate, CashflowPaymentCreate, CashflowItemCreate
from app.services.cashflow_engine import seed_default_categories, build_category_lineage_map, get_cashflow_summary, migrate_legacy_payment_signs
from app.api.routers.cashflow import create_cashflow_transaction, list_cashflow_transactions
from app.api.routers.accounts import calculate_all_account_balances

@pytest.mark.anyio
async def test_unified_transactions_all_types():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # Accounts
        bank_a = Account(account_name="HDFC Bank", broker_name="HDFC", account_type="bank", currency="EUR")
        bank_b = Account(account_name="Zerodha Trading", broker_name="Zerodha", account_type="brokerage", currency="EUR")
        cash_wallet = Account(account_name="Cash Wallet", broker_name="Cash", account_type="bank", currency="EUR")
        session.add_all([bank_a, bank_b, cash_wallet])
        await session.commit()
        await session.refresh(bank_a)
        await session.refresh(bank_b)
        await session.refresh(cash_wallet)

        user = User(user_id=1, username="admin", password_hash="dummy")

        salary_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Base Salary")
        groceries_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Groceries")
        dining_cat = next(v["category"] for v in lineage_map.values() if "Food" in v["category"].name or "Dining" in v["category"].name or "Restaurant" in v["category"].name)
        trans_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Internal Account Transfer")
        stock_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Stock & ETF Purchases")
        div_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Dividends")

        # 1. Salary Deposit: Bank A (+3,000)
        tx_salary = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 1),
            title="August Salary",
            total_amount=3000.0,
            currency="EUR",
            payments=[CashflowPaymentCreate(account_id=bank_a.account_id, amount=3000.0)],
            items=[CashflowItemCreate(category_id=salary_cat.category_id, amount=3000.0, label="ESSENTIAL", description="Monthly Base Salary")]
        )
        res_sal = await create_cashflow_transaction(tx_salary, db=session, current_user=user)
        assert res_sal.transaction_kind == "INCOME"

        # 2. Simple Spend: Groceries from Bank A (-100)
        tx_groc = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 5),
            title="Supermarket Groceries",
            total_amount=100.0,
            currency="EUR",
            payments=[CashflowPaymentCreate(account_id=bank_a.account_id, amount=-100.0)],
            items=[CashflowItemCreate(category_id=groceries_cat.category_id, amount=100.0, label="ESSENTIAL", description="Weekly groceries")]
        )
        res_groc = await create_cashflow_transaction(tx_groc, db=session, current_user=user)
        assert res_groc.transaction_kind == "EXPENSE"

        # 3. Account Transfer: Bank A (-1,000) -> Bank B (+1,000)
        tx_trans = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 8),
            title="Transfer to Broker",
            total_amount=1000.0,
            currency="EUR",
            payments=[
                CashflowPaymentCreate(account_id=bank_a.account_id, amount=-1000.0),
                CashflowPaymentCreate(account_id=bank_b.account_id, amount=1000.0),
            ],
            items=[CashflowItemCreate(category_id=trans_cat.category_id, amount=1000.0, description="Funding investment account")]
        )
        res_trans = await create_cashflow_transaction(tx_trans, db=session, current_user=user)
        assert res_trans.transaction_kind == "TRANSFER"

        # 4. Investment Buy: Bank B (-800)
        tx_inv = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 10),
            title="VWCE ETF Purchase",
            total_amount=800.0,
            currency="EUR",
            payments=[CashflowPaymentCreate(account_id=bank_b.account_id, amount=-800.0)],
            items=[CashflowItemCreate(category_id=stock_cat.category_id, amount=800.0, label="INVESTMENT", description="Monthly SIP")]
        )
        res_inv = await create_cashflow_transaction(tx_inv, db=session, current_user=user)
        assert res_inv.transaction_kind == "EXPENSE"

        # 5. Dividend Yield: Bank A (+150)
        tx_div = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 12),
            title="Apple Dividend",
            total_amount=150.0,
            currency="EUR",
            payments=[CashflowPaymentCreate(account_id=bank_a.account_id, amount=150.0)],
            items=[CashflowItemCreate(category_id=div_cat.category_id, amount=150.0, label="INVESTMENT", description="Q3 Dividend")]
        )
        res_div = await create_cashflow_transaction(tx_div, db=session, current_user=user)
        assert res_div.transaction_kind == "INCOME"

        # 6. Splitwise Dinner: Cash Wallet (-500), Bank A (+200 reimbursement), Net Spend = 300
        tx_split = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 14),
            title="Dinner with Friends",
            total_amount=300.0,
            currency="EUR",
            payments=[
                CashflowPaymentCreate(account_id=cash_wallet.account_id, amount=-500.0),
                CashflowPaymentCreate(account_id=bank_a.account_id, amount=200.0),
            ],
            items=[CashflowItemCreate(category_id=dining_cat.category_id, amount=300.0, label="DISCRETIONARY", description="Dinner share")]
        )
        res_split = await create_cashflow_transaction(tx_split, db=session, current_user=user)
        assert res_split.transaction_kind == "EXPENSE"

        # Verify Account Balances:
        # Bank A: +3000 (salary) - 100 (groc) - 1000 (transfer) + 150 (div) + 200 (reimb) = 2250.0
        # Bank B: +1000 (transfer) - 800 (stock) = 200.0
        # Cash Wallet: -500 (dinner) = -500.0
        balances = await calculate_all_account_balances(session)
        assert balances[bank_a.account_id] == 2250.0
        assert balances[bank_b.account_id] == 200.0
        assert balances[cash_wallet.account_id] == -500.0

        # Verify Cashflow Summary
        summary = await get_cashflow_summary(session, master_currency="EUR")
        assert summary.total_income == 3150.0 # 3000 salary + 150 dividend
        assert summary.total_expenses == 400.0 # 100 groceries + 300 dining
        assert summary.total_invested == 800.0 # 800 stock purchase
        assert summary.net_savings == 2750.0 # 3150 - 400 = 2750

@pytest.mark.anyio
async def test_legacy_payment_signs_migration():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        bank = Account(account_name="Legacy Bank", broker_name="Bank", account_type="bank", currency="EUR")
        session.add(bank)
        await session.commit()
        await session.refresh(bank)

        groceries_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Groceries")

        # Manually create legacy row with positive payment on an expense
        legacy_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 1),
            title="Old Expense",
            total_amount=150.0,
            currency="EUR",
            transaction_kind="EXPENSE"
        )
        session.add(legacy_tx)
        await session.flush()
        pmt = CashflowPayment(cashflow_id=legacy_tx.cashflow_id, account_id=bank.account_id, amount=150.0) # Positive!
        itm = CashflowItem(cashflow_id=legacy_tx.cashflow_id, category_id=groceries_cat.category_id, amount=150.0)
        session.add_all([pmt, itm])
        await session.commit()

        # Run migration
        await migrate_legacy_payment_signs(session)

        # Verify payment amount was converted to negative outflow
        await session.refresh(pmt)
        assert pmt.amount == -150.0

        balances = await calculate_all_account_balances(session)
        assert balances[bank.account_id] == -150.0
