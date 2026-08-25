import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, Category, User
from app.schemas.schemas import CashflowTransactionCreate, CashflowPaymentCreate, CashflowItemCreate
from app.services.cashflow_engine import seed_default_categories, build_category_lineage_map, get_cashflow_summary
from app.api.routers.cashflow import create_cashflow_transaction
from app.api.routers.accounts import calculate_all_account_balances

@pytest.mark.anyio
async def test_3_root_categories_structure():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # 1. Verify Root categories
        root_cats = {v["category"].name: v["category"] for v in lineage_map.values() if v["level"] == 1}
        assert "Income" in root_cats
        assert "Investments" in root_cats
        assert "Spends" in root_cats
        assert "Account Transfers" in root_cats

        assert root_cats["Income"].category_type == "INCOME"
        assert root_cats["Investments"].category_type == "INVESTMENT"
        assert root_cats["Spends"].category_type == "EXPENSE"
        assert root_cats["Account Transfers"].category_type == "TRANSFER"

        # 2. Verify "Investments & Passive" is NOT under Income
        inc_children = [v["category"].name for v in lineage_map.values() if v["category"].parent_id == root_cats["Income"].category_id]
        assert "Investments & Passive" not in inc_children
        assert "Salary" in inc_children

        # 3. Verify subcategories under root Investments
        inv_children = [v["category"].name for v in lineage_map.values() if v["category"].parent_id == root_cats["Investments"].category_id]
        assert "Dividends" in inv_children
        assert "Stock & ETF Purchases" in inv_children
        assert "Interest & Staking" in inv_children
        assert "Rental Income" in inv_children

@pytest.mark.anyio
async def test_existing_category_hierarchy_migration():
    """
    Test that an existing database with 'Investments & Passive' under 'Income'
    and 'Expenses' gets automatically migrated into the 3 decoupled root categories.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Manually create legacy tree
        income_root = Category(name="Income", category_type="INCOME", parent_id=None)
        expenses_root = Category(name="Expenses", category_type="EXPENSE", parent_id=None)
        session.add_all([income_root, expenses_root])
        await session.flush()

        inv_passive = Category(name="Investments & Passive", category_type="INVESTMENT", parent_id=income_root.category_id)
        session.add(inv_passive)
        await session.flush()

        div_cat = Category(name="Dividends", category_type="INVESTMENT", parent_id=inv_passive.category_id)
        session.add(div_cat)
        await session.commit()

        # Run seed/migration
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # Verify Expenses was renamed to Spends
        assert any(v["category"].name == "Spends" and v["level"] == 1 for v in lineage_map.values())

        # Verify root Investments exists and Dividends is now under root Investments
        inv_root = next(v["category"] for v in lineage_map.values() if v["category"].name == "Investments" and v["level"] == 1)
        assert inv_root is not None
        assert inv_root.category_type == "INVESTMENT"

        div_node = next(v["category"] for v in lineage_map.values() if v["category"].name == "Dividends")
        assert div_node.parent_id == inv_root.category_id

@pytest.mark.anyio
async def test_investments_used_in_both_income_and_spends():
    """
    Verify:
    1. An INCOME transaction using category 'Dividends' (INVESTMENT type) increases bank balance
       and is counted as income.
    2. An EXPENSE transaction using category 'Stock & ETF Purchases' (INVESTMENT type) decreases
       bank balance and is counted as invested capital.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        bank = Account(account_name="Main Bank", broker_name="HDFC", account_type="bank", currency="EUR")
        session.add(bank)
        await session.commit()
        await session.refresh(bank)

        div_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Dividends")
        stock_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Stock & ETF Purchases")

        user = User(user_id=1, username="admin", password_hash="dummy")

        # 1. Record Dividend Income: +500 EUR
        tx_div = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 10),
            title="AAPL Dividend Payout",
            total_amount=500.0,
            currency="EUR",
            transaction_kind="INCOME",
            payments=[CashflowPaymentCreate(account_id=bank.account_id, amount=500.0)],
            items=[CashflowItemCreate(category_id=div_cat.category_id, amount=500.0, label="INVESTMENT", description="Q3 Dividend")]
        )
        res_div = await create_cashflow_transaction(tx_div, db=session, current_user=user)
        assert res_div.transaction_kind == "INCOME"

        balances_1 = await calculate_all_account_balances(session)
        assert balances_1[bank.account_id] == 500.0

        # 2. Record Stock Purchase Spend/Outflow: -300 EUR
        tx_stock = CashflowTransactionCreate(
            transaction_date=datetime.date(2026, 8, 12),
            title="Bought VWCE ETF",
            total_amount=300.0,
            currency="EUR",
            transaction_kind="EXPENSE",
            payments=[CashflowPaymentCreate(account_id=bank.account_id, amount=-300.0)],
            items=[CashflowItemCreate(category_id=stock_cat.category_id, amount=300.0, label="INVESTMENT", description="Monthly SIP")]
        )
        res_stock = await create_cashflow_transaction(tx_stock, db=session, current_user=user)
        assert res_stock.transaction_kind == "EXPENSE"

        balances_2 = await calculate_all_account_balances(session)
        assert balances_2[bank.account_id] == 200.0  # 500 - 300 = 200

        # 3. Verify Cashflow Summary
        summary = await get_cashflow_summary(session, master_currency="EUR")
        assert summary.total_income == 500.0
        assert summary.total_invested == 300.0
        assert summary.total_expenses == 0.0
        assert summary.net_savings == 500.0
