import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Account, Asset, Transaction, CashflowTransaction, CashflowPayment, CashflowItem
from app.services.cashflow_engine import (
    seed_default_categories,
    build_category_lineage_map,
    generate_sankey_data,
    get_cashflow_summary
)

@pytest.mark.anyio
async def test_sankey_multi_layer_and_investment_accounting():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Seed categories
        await seed_default_categories(session)
        lineage_map = await build_category_lineage_map(session)

        # 1. Setup Accounts
        bank_acc = Account(account_name="Checking Bank", broker_name="Chase", account_type="bank", currency="EUR")
        demat_acc = Account(account_name="Trading Brokerage", broker_name="IBKR", account_type="demat", currency="EUR")
        session.add_all([bank_acc, demat_acc])
        await session.commit()
        await session.refresh(bank_acc)
        await session.refresh(demat_acc)

        # 2. Setup Asset
        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        # 3. Add Day-to-Day Cashflow
        salary_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Base Salary")
        groceries_cat = next(v["category"] for v in lineage_map.values() if v["category"].name == "Groceries")

        # Salary Income: 5000 EUR
        salary_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 1),
            title="August Salary",
            total_amount=5000.0,
            currency="EUR"
        )
        session.add(salary_tx)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=salary_tx.cashflow_id, account_id=bank_acc.account_id, amount=5000.0))
        session.add(CashflowItem(cashflow_id=salary_tx.cashflow_id, category_id=salary_cat.category_id, amount=5000.0))

        # Grocery Expense: 400 EUR
        grocery_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 8, 5),
            title="Supermarket",
            total_amount=400.0,
            currency="EUR"
        )
        session.add(grocery_tx)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=grocery_tx.cashflow_id, account_id=bank_acc.account_id, amount=-400.0))
        session.add(CashflowItem(cashflow_id=grocery_tx.cashflow_id, category_id=groceries_cat.category_id, amount=400.0, label="ESSENTIAL"))

        # 4. Add Investment Transactions in Transaction table:
        # Buy: 10 AAPL @ 150 EUR = 1500 EUR + 10 EUR fee + 5 EUR tax
        buy_tx = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=bank_acc.account_id,
            asset_id=asset.asset_id,
            transaction_type="buy",
            transaction_date=datetime.date(2026, 8, 10),
            quantity=10.0,
            price_per_unit=150.0,
            total_amount=1500.0,
            fees=10.0,
            taxes=5.0
        )
        # Dividend: 100 EUR net from AAPL (120 gross - 20 tax)
        div_tx = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=bank_acc.account_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2026, 8, 15),
            quantity=10.0,
            price_per_unit=12.0,
            total_amount=120.0,
            fees=0.0,
            taxes=20.0
        )
        # Sell: 2 AAPL @ 200 EUR = 400 EUR gross - 5 fee - 10 tax
        sell_tx = Transaction(
            account_id=demat_acc.account_id,
            funding_account_id=bank_acc.account_id,
            asset_id=asset.asset_id,
            transaction_type="sell",
            transaction_date=datetime.date(2026, 8, 20),
            quantity=2.0,
            price_per_unit=200.0,
            total_amount=400.0,
            fees=5.0,
            taxes=10.0
        )
        session.add_all([buy_tx, div_tx, sell_tx])
        await session.commit()

        # 5. Verify Cashflow Summary Numbers:
        # Total Income = 5000 (salary) + 120 (dividend gross) + 400 (sell gross) = 5520 EUR
        # Total Invested = 1500 (buy stock)
        # Total Expenses = 400 (groceries) + 15 (buy fee+tax) + 20 (div tax) + 15 (sell fee+tax) = 450 EUR
        summary = await get_cashflow_summary(session, master_currency="EUR")
        assert summary.total_income == 5520.0
        assert summary.total_invested == 1500.0
        assert summary.net_savings == 5520.0 - 450.0  # 5070.0 EUR

        # 6. Verify Sankey Depth 1: 3 Layers (in -> sustained -> out)
        sankey_d1 = await generate_sankey_data(session, depth=1, master_currency="EUR")
        levels_d1 = set(n.level for n in sankey_d1.nodes)
        assert levels_d1 == {1, 2, 3}  # Exactly 3 columns
        assert any(n.name == "Total Inflow Pool" and n.level == 2 for n in sankey_d1.nodes)
        # All links go level 1 -> 2 and 2 -> 3
        node_map_d1 = {n.id: n for n in sankey_d1.nodes}
        for l in sankey_d1.links:
            src_lvl = node_map_d1[l.source].level
            tgt_lvl = node_map_d1[l.target].level
            assert (src_lvl == 1 and tgt_lvl == 2) or (src_lvl == 2 and tgt_lvl == 3)

        # 7. Verify Sankey Depth 2: 5 Layers (insub1 -> in -> sustained -> out -> outsub1)
        sankey_d2 = await generate_sankey_data(session, depth=2, master_currency="EUR")
        levels_d2 = set(n.level for n in sankey_d2.nodes)
        assert levels_d2 == {1, 2, 3, 4, 5}  # Exactly 5 columns
        assert any(n.name == "Total Inflow Pool" and n.level == 3 for n in sankey_d2.nodes)
        # Both Salary (insub1) and Income (in) must be present (parent NOT replaced)
        assert any(n.name == "Salary" and n.level == 1 for n in sankey_d2.nodes)
        assert any(n.name == "Income" and n.level == 2 for n in sankey_d2.nodes)
        # Both Essential (out) and Food & Dining (outsub1) must be present
        assert any(n.name == "Essential" and n.level == 4 for n in sankey_d2.nodes)
        assert any(n.name == "Food & Dining" and n.level == 5 for n in sankey_d2.nodes)
        # Stock & ETF Purchases must be present in outsub1 under Investments
        assert any("Stock" in n.name and n.level == 5 for n in sankey_d2.nodes)

        # 8. Verify Sankey Depth 3: 7 Layers (insub2 -> insub1 -> in -> sustained -> out -> outsub1 -> outsub2)
        sankey_d3 = await generate_sankey_data(session, depth=3, master_currency="EUR")
        levels_d3 = set(n.level for n in sankey_d3.nodes)
        assert levels_d3 == {1, 2, 3, 4, 5, 6, 7}  # Exactly 7 columns
        assert any(n.name == "Total Inflow Pool" and n.level == 4 for n in sankey_d3.nodes)
        # Insub2: Base Salary (level 1) -> Insub1: Salary (level 2) -> In: Income (level 3)
        assert any(n.name == "Base Salary" and n.level == 1 for n in sankey_d3.nodes)
        assert any(n.name == "Salary" and n.level == 2 for n in sankey_d3.nodes)
        assert any(n.name == "Income" and n.level == 3 for n in sankey_d3.nodes)
        # Out: Essential (level 5) -> Outsub1: Food & Dining (level 6) -> Outsub2: Groceries (level 7)
        assert any(n.name == "Essential" and n.level == 5 for n in sankey_d3.nodes)
        assert any(n.name == "Food & Dining" and n.level == 6 for n in sankey_d3.nodes)
        assert any(n.name == "Groceries" and n.level == 7 for n in sankey_d3.nodes)
