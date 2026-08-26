import asyncio
import datetime
import random
from sqlalchemy import select, delete, func
from app.db.database import engine, Base, AsyncSessionLocal
from app.db.models import (
    User, Account, Asset, Transaction, PriceHistory, 
    Benchmark, Category, CashflowTransaction, CashflowPayment, 
    CashflowItem, AppSetting, Dividend, CorporateAction
)
from app.services.auth_service import get_password_hash
from app.services.cashflow_engine import seed_default_categories
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import recalculate_past_snapshots

async def seed_all():
    print("[Seed] Starting complete demo database population...")

    # 1. Initialize schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE assets ADD COLUMN industry VARCHAR"))
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        # Clear existing data to ensure clean idempotency
        for model in [
            CashflowItem, CashflowPayment, CashflowTransaction,
            PriceHistory, Transaction, Dividend, CorporateAction,
            Benchmark, Asset, Account, AppSetting
        ]:
            await session.execute(delete(model))
        await session.commit()

        # 2. Seed Admin User
        user_res = await session.execute(select(User).where(User.username == "admin"))
        admin_user = user_res.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123")
            )
            session.add(admin_user)
        else:
            admin_user.password_hash = get_password_hash("admin123")
        await session.commit()
        print("[Seed] Admin user verified (admin / admin123).")

        # 3. Seed Default Category Hierarchy
        await seed_default_categories(session)
        print("[Seed] Category hierarchy verified.")

        # 4. Seed Settings
        settings_to_seed = {
            "master_currency": "EUR",
            "fiscal_year_start": "01-01",
            "link_brokerage_with_bank": "false",
        }
        for k, v in settings_to_seed.items():
            session.add(AppSetting(key=k, value=v))
        await session.commit()
        print("[Seed] App settings configured.")

        # 5. Seed Accounts
        accounts_data = [
            {"account_id": 1, "name": "Zerodha (Primary)", "broker": "Zerodha Broking", "type": "demat", "curr": "INR", "date": datetime.date(2025, 8, 1)},
            {"account_id": 2, "name": "Jhaveri Securities", "broker": "Jhaveri Securities", "type": "demat", "curr": "INR", "date": datetime.date(2025, 8, 1)},
            {"account_id": 3, "name": "Interactive Brokers", "broker": "Interactive Brokers LLC", "type": "demat", "curr": "USD", "date": datetime.date(2025, 8, 1)},
            {"account_id": 4, "name": "Jupiter", "broker": "Federal Bank", "type": "bank", "curr": "INR", "date": datetime.date(2026, 1, 1)},
            {"account_id": 5, "name": "Kotak811", "broker": "Kotak Mahindra Bank", "type": "bank", "curr": "INR", "date": datetime.date(2026, 1, 1)},
            {"account_id": 6, "name": "Wise (Euro)", "broker": "Wise Europe", "type": "bank", "curr": "EUR", "date": datetime.date(2026, 1, 1)},
            {"account_id": 7, "name": "Wise (Dollars)", "broker": "Wise US Inc", "type": "bank", "curr": "USD", "date": datetime.date(2026, 1, 1)},
            {"account_id": 8, "name": "Cash Wallet (Rupee)", "broker": "Physical Cash", "type": "bank", "curr": "INR", "date": datetime.date(2026, 1, 1)},
            {"account_id": 9, "name": "Cash Wallet (Euro)", "broker": "Physical Cash", "type": "bank", "curr": "EUR", "date": datetime.date(2026, 1, 1)},
            {"account_id": 10, "name": "Bank of India", "broker": "Bank of India", "type": "bank", "curr": "INR", "date": datetime.date(2026, 1, 1)},
        ]

        accounts_map = {}
        for a in accounts_data:
            acc = Account(
                account_id=a["account_id"],
                account_name=a["name"],
                broker_name=a["broker"],
                account_type=a["type"],
                currency=a["curr"],
                created_at=a["date"]
            )
            session.add(acc)
            accounts_map[a["name"]] = acc
        await session.commit()
        print(f"[Seed] Created {len(accounts_data)} accounts.")

        # 6. Seed Assets
        assets_data = [
            {"asset_id": 1, "symbol": "AAPL", "name": "Apple Inc.", "type": "stock", "exchange": "NASDAQ", "curr": "USD", "sector": "Technology", "ind": "Consumer Electronics", "base_p": 210.0},
            {"asset_id": 2, "symbol": "NVDA", "name": "NVIDIA Corporation", "type": "stock", "exchange": "NASDAQ", "curr": "USD", "sector": "Technology", "ind": "Semiconductors", "base_p": 115.0},
            {"asset_id": 3, "symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock", "exchange": "NASDAQ", "curr": "USD", "sector": "Technology", "ind": "Software Infrastructure", "base_p": 420.0},
            {"asset_id": 4, "symbol": "VOO", "name": "Vanguard S&P 500 ETF", "type": "etf", "exchange": "NYSE", "curr": "USD", "sector": "Financial Services", "ind": "Broad Market ETF", "base_p": 500.0},
            {"asset_id": 5, "symbol": "RELIANCE.BSE", "name": "Reliance Industries Ltd", "type": "stock", "exchange": "BSE", "curr": "INR", "sector": "Energy", "ind": "Oil & Gas Refining", "base_p": 2850.0},
            {"asset_id": 6, "symbol": "INFY.BSE", "name": "Infosys Ltd", "type": "stock", "exchange": "BSE", "curr": "INR", "sector": "Technology", "ind": "IT Services", "base_p": 1780.0},
            {"asset_id": 7, "symbol": "TCS.BSE", "name": "Tata Consultancy Services", "type": "stock", "exchange": "BSE", "curr": "INR", "sector": "Technology", "ind": "IT Services", "base_p": 4150.0},
            {"asset_id": 8, "symbol": "HDFCBANK.BSE", "name": "HDFC Bank Ltd", "type": "stock", "exchange": "BSE", "curr": "INR", "sector": "Financial Services", "ind": "Private Banks", "base_p": 1620.0},
            {"asset_id": 9, "symbol": "VWCE.DE", "name": "Vanguard FTSE All-World UCITS ETF", "type": "etf", "exchange": "XETRA", "curr": "EUR", "sector": "Financial Services", "ind": "Global Equity ETF", "base_p": 122.0},
        ]

        assets_map = {}
        for ast in assets_data:
            asset = Asset(
                asset_id=ast["asset_id"],
                symbol=ast["symbol"],
                name=ast["name"],
                asset_type=ast["type"],
                exchange=ast["exchange"],
                currency=ast["curr"],
                sector=ast["sector"],
                industry=ast["ind"]
            )
            session.add(asset)
            assets_map[ast["symbol"]] = (asset, ast["base_p"])
        await session.commit()
        print(f"[Seed] Created {len(assets_data)} assets.")

        # 7. Seed Continuous Price Histories (2025-08-01 to 2026-08-18)
        start_date = datetime.date(2025, 8, 1)
        today = datetime.date(2026, 8, 18)
        delta_day = datetime.timedelta(days=1)

        rng = random.Random(42)
        price_history_objects = []
        asset_last_prices = {}

        for sym, (asset_obj, base_p) in assets_map.items():
            curr_p = base_p
            curr_d = start_date
            while curr_d <= today:
                # Random walk with slight upward drift
                daily_pct = rng.normalvariate(0.0006, 0.012)
                curr_p = max(1.0, round(curr_p * (1.0 + daily_pct), 2))
                price_history_objects.append(PriceHistory(
                    asset_id=asset_obj.asset_id,
                    price_date=curr_d,
                    close_price=curr_p,
                    source="seeded_demo"
                ))
                curr_d += delta_day
            asset_last_prices[sym] = curr_p

        session.add_all(price_history_objects)
        await session.commit()
        print(f"[Seed] Generated {len(price_history_objects)} price history records across all assets.")

        # 8. Seed Benchmarks (^GSPC, ^NSEI, BTC-USD)
        bm_configs = [
            {"name": "^GSPC", "base": 5450.0, "drift": 0.0004, "vol": 0.009},
            {"name": "^NSEI", "base": 24200.0, "drift": 0.0005, "vol": 0.008},
            {"name": "BTC-USD", "base": 61000.0, "drift": 0.0012, "vol": 0.025},
        ]
        bm_objects = []
        for bmc in bm_configs:
            val = bmc["base"]
            curr_d = start_date
            while curr_d <= today:
                pct = rng.normalvariate(bmc["drift"], bmc["vol"])
                val = max(100.0, round(val * (1.0 + pct), 2))
                bm_objects.append(Benchmark(
                    benchmark_name=bmc["name"],
                    price_date=curr_d,
                    close_value=val
                ))
                curr_d += delta_day

        session.add_all(bm_objects)
        await session.commit()
        print(f"[Seed] Generated {len(bm_objects)} benchmark points.")

        # 9. Seed Investment Trades (Deposits, Buys, Sells)
        trades_data = [
            # Zerodha Primary (INR)
            {"acc": "Zerodha (Primary)", "type": "deposit", "date": datetime.date(2025, 8, 14), "sym": None, "qty": None, "price": None, "tot": 100000.0, "fees": 0, "taxes": 0, "notes": "Initial investment fund deposit"},
            {"acc": "Zerodha (Primary)", "type": "buy", "date": datetime.date(2025, 8, 15), "sym": "RELIANCE.BSE", "qty": 15.0, "price": 2840.0, "tot": 42600.0, "fees": 20.0, "taxes": 15.0, "notes": "Bought Reliance shares"},
            {"acc": "Zerodha (Primary)", "type": "buy", "date": datetime.date(2025, 8, 20), "sym": "INFY.BSE", "qty": 25.0, "price": 1760.0, "tot": 44000.0, "fees": 20.0, "taxes": 15.0, "notes": "Bought Infosys shares"},
            {"acc": "Zerodha (Primary)", "type": "deposit", "date": datetime.date(2025, 12, 1), "sym": None, "qty": None, "price": None, "tot": 75000.0, "fees": 0, "taxes": 0, "notes": "SIP allocation deposit"},
            {"acc": "Zerodha (Primary)", "type": "buy", "date": datetime.date(2025, 12, 5), "sym": "HDFCBANK.BSE", "qty": 30.0, "price": 1605.0, "tot": 48150.0, "fees": 20.0, "taxes": 18.0, "notes": "Bought HDFC Bank"},
            {"acc": "Zerodha (Primary)", "type": "buy", "date": datetime.date(2026, 2, 10), "sym": "TCS.BSE", "qty": 8.0, "price": 4120.0, "tot": 32960.0, "fees": 20.0, "taxes": 12.0, "notes": "Bought TCS"},

            # Jhaveri Securities (INR)
            {"acc": "Jhaveri Securities", "type": "deposit", "date": datetime.date(2025, 9, 1), "sym": None, "qty": None, "price": None, "tot": 60000.0, "fees": 0, "taxes": 0, "notes": "Fund deposit"},
            {"acc": "Jhaveri Securities", "type": "buy", "date": datetime.date(2025, 9, 2), "sym": "INFY.BSE", "qty": 20.0, "price": 1750.0, "tot": 35000.0, "fees": 15.0, "taxes": 10.0, "notes": "Long-term holding"},
            {"acc": "Jhaveri Securities", "type": "sell", "date": datetime.date(2026, 4, 15), "sym": "INFY.BSE", "qty": 5.0, "price": 1890.0, "tot": 9450.0, "fees": 15.0, "taxes": 10.0, "notes": "Profit booking on INFY"},

            # Interactive Brokers (USD)
            {"acc": "Interactive Brokers", "type": "deposit", "date": datetime.date(2025, 8, 10), "sym": None, "qty": None, "price": None, "tot": 5000.0, "fees": 0, "taxes": 0, "notes": "Wire transfer deposit"},
            {"acc": "Interactive Brokers", "type": "buy", "date": datetime.date(2025, 8, 12), "sym": "AAPL", "qty": 10.0, "price": 212.0, "tot": 2120.0, "fees": 1.0, "taxes": 0, "notes": "Bought AAPL"},
            {"acc": "Interactive Brokers", "type": "buy", "date": datetime.date(2025, 8, 12), "sym": "NVDA", "qty": 12.0, "price": 116.0, "tot": 1392.0, "fees": 1.0, "taxes": 0, "notes": "Bought NVDA"},
            {"acc": "Interactive Brokers", "type": "buy", "date": datetime.date(2025, 10, 5), "sym": "VOO", "qty": 2.0, "price": 498.0, "tot": 996.0, "fees": 1.0, "taxes": 0, "notes": "S&P Index buy"},
            {"acc": "Interactive Brokers", "type": "sell", "date": datetime.date(2026, 3, 20), "sym": "NVDA", "qty": 4.0, "price": 138.0, "tot": 552.0, "fees": 1.0, "taxes": 0, "notes": "Trimmed Nvidia position at profit"},
            {"acc": "Interactive Brokers", "type": "buy", "date": datetime.date(2026, 5, 10), "sym": "MSFT", "qty": 2.0, "price": 425.0, "tot": 850.0, "fees": 1.0, "taxes": 0, "notes": "Bought MSFT"},
        ]

        for tr in trades_data:
            acc_obj = accounts_map[tr["acc"]]
            ast_tuple = assets_map.get(tr["sym"]) if tr["sym"] else None
            ast_id = ast_tuple[0].asset_id if ast_tuple else None

            session.add(Transaction(
                account_id=acc_obj.account_id,
                asset_id=ast_id,
                transaction_type=tr["type"],
                transaction_date=tr["date"],
                quantity=tr["qty"],
                price_per_unit=tr["price"],
                total_amount=tr["tot"],
                fees=tr["fees"],
                taxes=tr["taxes"],
                notes=tr["notes"]
            ))
        await session.commit()
        print(f"[Seed] Created {len(trades_data)} investment transactions.")

        # 10. Seed Categories & Cashflow Records (Income, Expenses, Transfers)
        # Fetch category map
        all_cats = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.name.lower(): c.category_id for c in all_cats}

        # Helper to find or fallback category
        def get_cat_id(name: str, fallback_type: str = "EXPENSE"):
            if name.lower() in cat_map:
                return cat_map[name.lower()]
            for c in all_cats:
                if c.category_type == fallback_type:
                    return c.category_id
            return all_cats[0].category_id

        salary_cat = get_cat_id("Salary", "INCOME")
        consulting_cat = get_cat_id("Consulting", "INCOME")
        rent_cat = get_cat_id("Rent", "EXPENSE")
        groceries_cat = get_cat_id("Groceries", "EXPENSE")
        dining_cat = get_cat_id("Dining Out", "EXPENSE")
        utilities_cat = get_cat_id("Electricity", "EXPENSE")
        internet_cat = get_cat_id("Internet", "EXPENSE")
        flights_cat = get_cat_id("Flights", "EXPENSE")
        hotels_cat = get_cat_id("Hotels & Stays", "EXPENSE")
        software_cat = get_cat_id("Software & Subscriptions", "EXPENSE")
        gym_cat = get_cat_id("Gym & Fitness", "EXPENSE")
        transfer_cat = get_cat_id("Account Transfers", "TRANSFER")

        # Cashflow Transactions across 2026
        cashflow_events = [
            # Incomes into Jupiter (INR)
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 1, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 2, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 3, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 4, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 5, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 6, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 7, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},
            {"title": "Monthly Salary - Tech Corp", "date": datetime.date(2026, 8, 1), "curr": "INR", "tot": 180000.0, "acc": "Jupiter", "cat": salary_cat, "label": "INCOME"},

            # Incomes into Wise (Euro)
            {"title": "Client Retainer Consulting", "date": datetime.date(2026, 2, 15), "curr": "EUR", "tot": 2400.0, "acc": "Wise (Euro)", "cat": consulting_cat, "label": "INCOME"},
            {"title": "Client Retainer Consulting", "date": datetime.date(2026, 5, 15), "curr": "EUR", "tot": 2800.0, "acc": "Wise (Euro)", "cat": consulting_cat, "label": "INCOME"},

            # Expenses from Jupiter (INR)
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 1, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 2, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 3, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 4, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 5, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 6, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 7, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},
            {"title": "Apartment Monthly Rent", "date": datetime.date(2026, 8, 5), "curr": "INR", "tot": 35000.0, "acc": "Jupiter", "cat": rent_cat, "label": "ESSENTIAL"},

            {"title": "Organic Groceries & Supermarket", "date": datetime.date(2026, 6, 10), "curr": "INR", "tot": 8450.0, "acc": "Jupiter", "cat": groceries_cat, "label": "ESSENTIAL"},
            {"title": "Electricity & Power Bill", "date": datetime.date(2026, 6, 14), "curr": "INR", "tot": 3200.0, "acc": "Jupiter", "cat": utilities_cat, "label": "ESSENTIAL"},
            {"title": "Fiber Gigabit Internet", "date": datetime.date(2026, 6, 18), "curr": "INR", "tot": 1499.0, "acc": "Jupiter", "cat": internet_cat, "label": "ESSENTIAL"},
            {"title": "Gym & Personal Training Membership", "date": datetime.date(2026, 7, 2), "curr": "INR", "tot": 4500.0, "acc": "Jupiter", "cat": gym_cat, "label": "DISCRETIONARY"},

            # Expenses from Kotak811 / Wise
            {"title": "Weekend Dining & Cocktails", "date": datetime.date(2026, 7, 12), "curr": "INR", "tot": 5800.0, "acc": "Kotak811", "cat": dining_cat, "label": "DISCRETIONARY"},
            {"title": "Flight Tickets to Berlin Tech Summit", "date": datetime.date(2026, 7, 20), "curr": "EUR", "tot": 640.0, "acc": "Wise (Euro)", "cat": flights_cat, "label": "DISCRETIONARY"},
            {"title": "Hotel Stay & Lodging", "date": datetime.date(2026, 7, 24), "curr": "EUR", "tot": 480.0, "acc": "Wise (Euro)", "cat": hotels_cat, "label": "DISCRETIONARY"},
            {"title": "Cloud Server & AI Subscriptions", "date": datetime.date(2026, 8, 2), "curr": "EUR", "tot": 95.0, "acc": "Wise (Euro)", "cat": software_cat, "label": "ESSENTIAL"},
            {"title": "Dinner & Entertainment Split", "date": datetime.date(2026, 8, 10), "curr": "INR", "tot": 3200.0, "acc": "Jupiter", "cat": dining_cat, "label": "DISCRETIONARY"},
        ]

        for cf in cashflow_events:
            ctx = CashflowTransaction(
                transaction_date=cf["date"],
                title=cf["title"],
                total_amount=cf["tot"],
                currency=cf["curr"],
                notes="Demo cashflow transaction"
            )
            session.add(ctx)
            await session.flush()

            acc_obj = accounts_map[cf["acc"]]
            session.add(CashflowPayment(
                cashflow_id=ctx.cashflow_id,
                account_id=acc_obj.account_id,
                amount=cf["tot"]
            ))

            session.add(CashflowItem(
                cashflow_id=ctx.cashflow_id,
                category_id=cf["cat"],
                amount=cf["tot"],
                label=cf["label"],
                description=cf["title"]
            ))

        # Transfer 1: Jupiter (INR) -> Zerodha (Primary) investment transfer ₹50,000
        ctx_trans1 = CashflowTransaction(
            transaction_date=datetime.date(2026, 5, 20),
            title="Internal Transfer: Bank to Zerodha",
            total_amount=50000.0,
            currency="INR",
            notes="Funding investment account"
        )
        session.add(ctx_trans1)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=ctx_trans1.cashflow_id, account_id=accounts_map["Jupiter"].account_id, amount=-50000.0))
        session.add(CashflowPayment(cashflow_id=ctx_trans1.cashflow_id, account_id=accounts_map["Zerodha (Primary)"].account_id, amount=50000.0))
        session.add(CashflowItem(cashflow_id=ctx_trans1.cashflow_id, category_id=transfer_cat, amount=50000.0, label="INVESTMENT", description="Transfer to Zerodha"))

        # Transfer 2: Wise (Euro) -> Wise (Dollars) FX Transfer €500 -> $540
        ctx_trans2 = CashflowTransaction(
            transaction_date=datetime.date(2026, 6, 15),
            title="FX Conversion: Wise EUR to USD",
            total_amount=500.0,
            currency="EUR",
            notes="FX transfer"
        )
        session.add(ctx_trans2)
        await session.flush()
        session.add(CashflowPayment(cashflow_id=ctx_trans2.cashflow_id, account_id=accounts_map["Wise (Euro)"].account_id, amount=-500.0))
        session.add(CashflowPayment(cashflow_id=ctx_trans2.cashflow_id, account_id=accounts_map["Wise (Dollars)"].account_id, amount=540.0))
        session.add(CashflowItem(cashflow_id=ctx_trans2.cashflow_id, category_id=transfer_cat, amount=500.0, label="TRANSFER", description="Wise EUR to USD"))

        await session.commit()
        print(f"[Seed] Created {len(cashflow_events) + 2} cashflow transactions with payments and items.")

        # 11. Recalculate FIFO Lots and Net Worth Snapshots
        print("[Seed] Recalculating FIFO lots...")
        await recalculate_all_lots(session)

        print("[Seed] Recalculating daily net worth snapshots from 2025-08-01 to present...")
        min_tx = await session.execute(select(func.min(Transaction.transaction_date)))
        earliest_date = min_tx.scalar_one_or_none() or datetime.date(2025, 8, 1)
        count = await recalculate_past_snapshots(session, start_date=earliest_date)
        print(f"[Seed] Generated {count} historical daily net worth snapshots.")

    print("[Seed] Demo database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_all())
