import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, Category, CashflowTransaction, CashflowPayment, CashflowItem
from app.services.cashflow_engine import seed_default_categories, build_category_lineage_map, generate_sankey_data, get_cashflow_summary

@pytest.mark.anyio
async def test_category_seeding_and_lineage():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Seed categories
        await seed_default_categories(session)
        
        # Test lineage map
        lineage_map = await build_category_lineage_map(session)
        assert len(lineage_map) > 10

        # Check an item in the tree (e.g. Electricity under Utilities under Housing under Expenses)
        elec_cat = next((v for v in lineage_map.values() if v["category"].name == "Electricity"), None)
        assert elec_cat is not None
        assert elec_cat["level"] == 3
        assert elec_cat["effective_label"] == "ESSENTIAL"
        assert "Expenses / Utilities / Electricity" in elec_cat["full_path"] or "Utilities" in elec_cat["full_path"]

@pytest.mark.anyio
async def test_cashflow_splits_and_sankey():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Seed categories
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # Create Accounts
        bank_acc = Account(account_name="Main Bank", broker_name="Chase", account_type="bank", currency="EUR")
        wallet_acc = Account(account_name="Amazon Wallet", broker_name="Amazon", account_type="bank", currency="EUR")
        session.add_all([bank_acc, wallet_acc])
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(wallet_acc)

        # Find categories
        salary_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Base Salary")
        groceries_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Groceries")
        tech_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Electronics & Tech")

        # 1. Add Salary Income: 3000 EUR
        salary_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 1),
            title="August Salary",
            total_amount=3000.0,
            currency="EUR"
        )
        session.add(salary_tx)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=salary_tx.cashflow_id, account_id=bank_acc.account_id, amount=3000.0))
        session.add(CashflowItem(cashflow_id=salary_tx.cashflow_id, category_id=salary_cat.category_id, amount=3000.0))

        # 2. Add Split Transaction: Amazon Order ($110 Total) -> Paid $100 Bank + $10 Wallet -> $80 Speakers (Tech) + $30 Groceries
        amazon_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 15),
            title="Amazon Order - Speakers & Groceries",
            total_amount=110.0,
            currency="EUR"
        )
        session.add(amazon_tx)
        await session.flush()
        # Payment splits
        session.add(CashflowPayment(cashflow_id=amazon_tx.cashflow_id, account_id=bank_acc.account_id, amount=-100.0))
        session.add(CashflowPayment(cashflow_id=amazon_tx.cashflow_id, account_id=wallet_acc.account_id, amount=-10.0))
        # Category item splits
        session.add(CashflowItem(cashflow_id=amazon_tx.cashflow_id, category_id=tech_cat.category_id, amount=80.0, label="LUXURY", description="Speakers"))
        session.add(CashflowItem(cashflow_id=amazon_tx.cashflow_id, category_id=groceries_cat.category_id, amount=30.0, description="Snacks & Tea"))

        await session.commit()

        # 3. Test Summary
        summary = await get_cashflow_summary(session)
        assert summary.total_income == 3000.0
        assert summary.total_expenses == 110.0
        assert summary.net_savings == 2890.0
        assert summary.breakdown_by_label["LUXURY"] == 80.0
        assert summary.breakdown_by_label["ESSENTIAL"] == 30.0

        # 4. Test Sankey Generation at Depth 1, 2, 3
        sankey_d1 = await generate_sankey_data(session, depth=1)
        assert sankey_d1.total_income == 3000.0
        assert len(sankey_d1.nodes) >= 3
        assert any(n.name == "Total Expenses" for n in sankey_d1.nodes)

        sankey_d2 = await generate_sankey_data(session, depth=2)
        assert any("node_cash_inflow" == l.target for l in sankey_d2.links)
        assert any(n.name == "Luxury" for n in sankey_d2.nodes)
