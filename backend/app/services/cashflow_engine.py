import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from app.db.models import Category, CashflowTransaction, CashflowPayment, CashflowItem, Transaction, LotSale
from app.schemas.schemas import SankeyNode, SankeyLink, SankeyDataResponse, CashflowSummaryResponse

# Standard Classification Labels
LABEL_ESSENTIAL = "ESSENTIAL"
LABEL_DISCRETIONARY = "DISCRETIONARY"
LABEL_LUXURY = "LUXURY"
LABEL_INVESTMENT = "INVESTMENT"

FX_RATES_TO_EUR: Dict[str, float] = {
    "EUR": 1.0,
    "USD": 0.92,
    "INR": 0.0102,
    "GBP": 1.17,
    "CAD": 0.67,
    "AUD": 0.60,
    "JPY": 0.0059,
    "CHF": 1.06,
    "SGD": 0.68,
}

def convert_currency(amount: float, from_currency: str = "EUR", to_currency: str = "EUR") -> float:
    if not amount:
        return 0.0
    src = (from_currency or "EUR").strip().upper()
    dst = (to_currency or "EUR").strip().upper()
    if src == dst:
        return amount
    rate_from = FX_RATES_TO_EUR.get(src, 1.0)
    rate_to = FX_RATES_TO_EUR.get(dst, 1.0)
    in_eur = amount * rate_from
    return in_eur / rate_to

def convert_currency_to_eur(amount: float, from_currency: str = "EUR") -> float:
    return convert_currency(amount, from_currency, "EUR")

def compute_transaction_cash_movement(tx: Any, valid_account_ids: Optional[Set[int]] = None) -> Tuple[int, float]:
    """
    Computes (cash_account_id, signed_cash_change) for an investment transaction.
    - Cash account: funding_account_id if valid, otherwise tx.account_id.
    - Buy: Outflow -(qty * ppu + fees + taxes) or -total_amount.
    - Sell: Inflow (qty * ppu - fees - taxes) or (total_amount - fees - taxes) [unclamped].
    - Dividend: Inflow total_amount - taxes.
    - Interest: Inflow total_amount - fees - taxes.
    - Deposit: Inflow total_amount - fees - taxes.
    - Withdrawal / Fee: Outflow -(total_amount + fees + taxes).
    """
    funding_id = getattr(tx, "funding_account_id", None)
    if funding_id and (valid_account_ids is None or funding_id in valid_account_ids):
        cash_acc_id = funding_id
    else:
        cash_acc_id = tx.account_id

    ttype = (getattr(tx, "transaction_type", None) or "").lower()
    qty = float(getattr(tx, "quantity", None) or 0.0)
    ppu = float(getattr(tx, "price_per_unit", None) or 0.0)
    amt = float(getattr(tx, "total_amount", None) or 0.0)
    fees = float(getattr(tx, "fees", None) or 0.0)
    taxes = float(getattr(tx, "taxes", None) or 0.0)

    if ttype == "buy":
        trade_cash = (qty * ppu + fees + taxes) if (qty > 0 and ppu > 0) else amt
        return cash_acc_id, -trade_cash
    elif ttype == "sell":
        trade_cash = (qty * ppu - fees - taxes) if (qty > 0 and ppu > 0) else (amt - fees - taxes)
        return cash_acc_id, trade_cash
    elif ttype == "dividend":
        if not funding_id:
            return None, 0.0
        trade_cash = amt - taxes
        return cash_acc_id, trade_cash
    elif ttype == "interest":
        trade_cash = amt - fees - taxes
        return cash_acc_id, trade_cash
    elif ttype == "deposit":
        trade_cash = amt - fees - taxes
        return cash_acc_id, trade_cash
    elif ttype in ["withdrawal", "fee"]:
        trade_cash = (amt + fees + taxes) if (fees > 0 or taxes > 0) else amt
        return cash_acc_id, -trade_cash

    return cash_acc_id, 0.0

def resolve_transaction_kind(tx: Any) -> str:
    """
    Canonical derivation of transaction kind (TRANSFER, INCOME, EXPENSE).
    Priority:
    1. Explicit tx.transaction_kind == 'TRANSFER' or any item has category_type == 'TRANSFER' -> 'TRANSFER'
    2. Explicit tx.transaction_kind == 'INCOME' or any item has category_type == 'INCOME' -> 'INCOME'
    3. Explicit tx.transaction_kind if set -> tx.transaction_kind
    4. Fallback -> 'EXPENSE'
    """
    items = getattr(tx, "items", []) or []

    is_trans = getattr(tx, "transaction_kind", None) == "TRANSFER" or any(
        (i.category and i.category.category_type == "TRANSFER") if hasattr(i, "category") else (getattr(i, "category_type", None) == "TRANSFER")
        for i in items
    )
    if is_trans:
        return "TRANSFER"

    is_inc = getattr(tx, "transaction_kind", None) == "INCOME" or any(
        (i.category and i.category.category_type == "INCOME") if hasattr(i, "category") else (getattr(i, "category_type", None) == "INCOME")
        for i in items
    )
    if is_inc:
        return "INCOME"

    return getattr(tx, "transaction_kind", None) or "EXPENSE"

DEFAULT_CATEGORY_COLORS = {
    "INCOME": "#10B981",       # Emerald green
    "EXPENSE": "#EF4444",      # Rose red
    "INVESTMENT": "#3B82F6",   # Blue
    "TRANSFER": "#6B7280",     # Slate gray
    LABEL_ESSENTIAL: "#10B981",
    LABEL_DISCRETIONARY: "#F59E0B",
    LABEL_LUXURY: "#EC4899",
    LABEL_INVESTMENT: "#3B82F6",
}

DEFAULT_CATEGORIES_TREE = [
    # 1. Income Tree
    {
        "name": "Income",
        "category_type": "INCOME",
        "default_label": LABEL_ESSENTIAL,
        "icon": "TrendingUp",
        "color": "#10B981",
        "children": [
            {
                "name": "Salary",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Briefcase",
                "color": "#059669",
                "children": [
                    {"name": "Base Salary", "default_label": LABEL_ESSENTIAL},
                    {"name": "Bonus & Commission", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Overtime", "default_label": LABEL_DISCRETIONARY},
                ]
            },
            {
                "name": "Freelance & Consulting",
                "default_label": LABEL_DISCRETIONARY,
                "icon": "Laptop",
                "color": "#34D399",
                "children": [
                    {"name": "Client Work", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Side Projects", "default_label": LABEL_DISCRETIONARY},
                ]
            },
            {
                "name": "Other Income",
                "default_label": LABEL_DISCRETIONARY,
                "icon": "Gift",
                "color": "#A7F3D0",
                "children": [
                    {"name": "Gifts & Grants", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Tax Refunds", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Cashbacks & Rewards", "default_label": LABEL_DISCRETIONARY},
                ]
            }
        ]
    },
    # 2. Investments Tree (Decoupled root category)
    {
        "name": "Investments",
        "category_type": "INVESTMENT",
        "default_label": LABEL_INVESTMENT,
        "icon": "PiggyBank",
        "color": "#3B82F6",
        "children": [
            {"name": "Stock & ETF Purchases", "default_label": LABEL_INVESTMENT},
            {"name": "Mutual Funds & SIPs", "default_label": LABEL_INVESTMENT},
            {"name": "Crypto Allocation", "default_label": LABEL_INVESTMENT},
            {"name": "Dividends", "default_label": LABEL_INVESTMENT},
            {"name": "Interest & Staking", "default_label": LABEL_INVESTMENT},
            {"name": "Realized Capital Gains", "default_label": LABEL_INVESTMENT},
            {"name": "Rental Income", "default_label": LABEL_INVESTMENT},
            {"name": "Emergency Fund Reserve", "default_label": LABEL_INVESTMENT},
            {"name": "Pension & Retirement (NPS / 401k)", "default_label": LABEL_INVESTMENT},
        ]
    },
    # 3. Spends Tree (Renamed from Expenses)
    {
        "name": "Spends",
        "category_type": "EXPENSE",
        "default_label": LABEL_DISCRETIONARY,
        "icon": "Receipt",
        "color": "#EF4444",
        "children": [
            {
                "name": "Housing",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Home",
                "color": "#DC2626",
                "children": [
                    {"name": "Rent & Mortgage", "default_label": LABEL_ESSENTIAL},
                    {"name": "Property Tax & Insurance", "default_label": LABEL_ESSENTIAL},
                    {"name": "Maintenance & Repairs", "default_label": LABEL_ESSENTIAL},
                ]
            },
            {
                "name": "Utilities",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Zap",
                "color": "#EA580C",
                "children": [
                    {"name": "Electricity", "default_label": LABEL_ESSENTIAL},
                    {"name": "Water & Gas", "default_label": LABEL_ESSENTIAL},
                    {
                        "name": "Telecommunications",
                        "default_label": LABEL_ESSENTIAL,
                        "children": [
                            {"name": "Mobile Bill", "default_label": LABEL_ESSENTIAL},
                            {"name": "Home Broadband", "default_label": LABEL_ESSENTIAL},
                        ]
                    },
                ]
            },
            {
                "name": "Food & Dining",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Utensils",
                "color": "#F59E0B",
                "children": [
                    {"name": "Groceries", "default_label": LABEL_ESSENTIAL},
                    {"name": "Restaurants & Dining Out", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Coffee & Snacks", "default_label": LABEL_LUXURY},
                ]
            },
            {
                "name": "Transportation",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Car",
                "color": "#D97706",
                "children": [
                    {"name": "Fuel & Charging", "default_label": LABEL_ESSENTIAL},
                    {"name": "Public Transit", "default_label": LABEL_ESSENTIAL},
                    {"name": "Taxis & Rideshare", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Vehicle Insurance & Service", "default_label": LABEL_ESSENTIAL},
                ]
            },
            {
                "name": "Health & Medical",
                "default_label": LABEL_ESSENTIAL,
                "icon": "HeartPulse",
                "color": "#E11D48",
                "children": [
                    {"name": "Health Insurance", "default_label": LABEL_ESSENTIAL},
                    {"name": "Doctor & Pharmacy", "default_label": LABEL_ESSENTIAL},
                    {"name": "Gym & Fitness", "default_label": LABEL_DISCRETIONARY},
                ]
            },
            {
                "name": "Shopping & Lifestyle",
                "default_label": LABEL_DISCRETIONARY,
                "icon": "ShoppingBag",
                "color": "#8B5CF6",
                "children": [
                    {"name": "Clothing & Apparel", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Electronics & Tech", "default_label": LABEL_LUXURY},
                    {"name": "Home & Furniture", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Personal Care & Beauty", "default_label": LABEL_DISCRETIONARY},
                ]
            },
            {
                "name": "Entertainment & Leisure",
                "default_label": LABEL_DISCRETIONARY,
                "icon": "Film",
                "color": "#EC4899",
                "children": [
                    {"name": "Streaming & Subscriptions", "default_label": LABEL_DISCRETIONARY},
                    {"name": "Vacation & Travel", "default_label": LABEL_LUXURY},
                    {"name": "Events & Concerts", "default_label": LABEL_LUXURY},
                    {"name": "Hobbies & Games", "default_label": LABEL_DISCRETIONARY},
                ]
            },
            {
                "name": "Financial & Taxes",
                "default_label": LABEL_ESSENTIAL,
                "icon": "Scale",
                "color": "#64748B",
                "children": [
                    {"name": "Bank & Brokerage Fees", "default_label": LABEL_ESSENTIAL},
                    {"name": "Income Taxes", "default_label": LABEL_ESSENTIAL},
                    {"name": "Loan Interest", "default_label": LABEL_ESSENTIAL},
                ]
            }
        ]
    },
    # 4. Account Transfers & FX Tree
    {
        "name": "Account Transfers",
        "category_type": "TRANSFER",
        "default_label": None,
        "icon": "ArrowLeftRight",
        "color": "#8B5CF6",
        "children": [
            {"name": "Internal Account Transfer", "category_type": "TRANSFER", "default_label": None},
            {"name": "FX Currency Conversion", "category_type": "TRANSFER", "default_label": None},
        ]
    }
]

async def seed_default_categories(db: AsyncSession):
    """
    Seeds or migrates the category hierarchy:
    1. Ensures 3 main root trees: Income, Investments, Spends.
    2. Decouples Investments & Passive from Income and reparents subcategories under root Investments.
    3. Renames Expenses to Spends.
    """
    stmt = select(func.count(Category.category_id))
    res = await db.execute(stmt)
    count = res.scalar() or 0

    async def _insert_node(node_dict: dict, parent_id: Optional[int], parent_type: str, parent_label: str):
        c_type = node_dict.get("category_type") or parent_type
        c_label = node_dict.get("default_label") or parent_label
        
        cat = Category(
            name=node_dict["name"],
            parent_id=parent_id,
            category_type=c_type,
            default_label=c_label,
            icon=node_dict.get("icon"),
            color=node_dict.get("color"),
        )
        db.add(cat)
        await db.flush()
        await db.refresh(cat)

        for child in node_dict.get("children", []):
            await _insert_node(child, cat.category_id, c_type, c_label)
        return cat

    if count == 0:
        for root_node in DEFAULT_CATEGORIES_TREE:
            await _insert_node(root_node, None, root_node["category_type"], root_node.get("default_label"))
        await db.commit()
        print("[Seed] Successfully seeded default 3-root category hierarchy.")
    else:
        # Migration: Ensure root Investments exists and reparent any nested investment subcategories
        # 1. Rename Expenses -> Spends if found
        exp_stmt = select(Category).where(Category.name == "Expenses", Category.parent_id == None)
        exp_res = await db.execute(exp_stmt)
        exp_cat = exp_res.scalar_one_or_none()
        if exp_cat:
            exp_cat.name = "Spends"

        # 2. Find or create root Investments
        inv_root_stmt = select(Category).where(Category.name.in_(["Investments", "Investments & Savings"]), Category.parent_id == None)
        inv_root_res = await db.execute(inv_root_stmt)
        inv_root = inv_root_res.scalars().first()
        if not inv_root:
            inv_root = Category(
                name="Investments",
                parent_id=None,
                category_type="INVESTMENT",
                default_label=LABEL_INVESTMENT,
                icon="PiggyBank",
                color="#3B82F6",
            )
            db.add(inv_root)
            await db.flush()
            await db.refresh(inv_root)
        else:
            inv_root.name = "Investments"
            inv_root.category_type = "INVESTMENT"
            inv_root.parent_id = None

        # 3. Check for Investments & Passive under Income and reparent its children
        inv_passive_stmt = select(Category).where(Category.name == "Investments & Passive")
        inv_passive_res = await db.execute(inv_passive_stmt)
        inv_passive = inv_passive_res.scalar_one_or_none()
        if inv_passive:
            # Reparent all children of Investments & Passive to inv_root
            await db.execute(
                update(Category)
                .where(Category.parent_id == inv_passive.category_id)
                .values(parent_id=inv_root.category_id, category_type="INVESTMENT", default_label=LABEL_INVESTMENT)
            )
            # Delete empty Investments & Passive node
            await db.execute(
                delete(Category)
                .where(Category.category_id == inv_passive.category_id)
            )

        # 4. Check if Transfer category exists, if not add it
        trans_stmt = select(Category).where(Category.name == "Account Transfers")
        trans_res = await db.execute(trans_stmt)
        if not trans_res.scalar_one_or_none():
            transfer_tree = DEFAULT_CATEGORIES_TREE[3]
            await _insert_node(transfer_tree, None, transfer_tree["category_type"], transfer_tree.get("default_label"))

        await db.commit()
        print("[Seed] Successfully migrated categories to 3-root hierarchy.")

async def migrate_legacy_payment_signs(db: AsyncSession):
    """
    Ensures all payments follow the unified signed convention:
    - Inflow / Deposit / Income: payment.amount > 0
    - Outflow / Spend / Expense: payment.amount < 0
    """
    stmt = (
        select(CashflowPayment, CashflowTransaction)
        .join(CashflowTransaction, CashflowPayment.cashflow_id == CashflowTransaction.cashflow_id)
        .options(selectinload(CashflowTransaction.items).selectinload(CashflowItem.category))
    )
    res = await db.execute(stmt)
    migrated_count = 0
    for pmt, ctx in res.all():
        is_trans = any(i.category and i.category.category_type == "TRANSFER" for i in ctx.items)
        is_inc = not is_trans and (
            any(i.category and i.category.category_type == "INCOME" for i in ctx.items) or
            ctx.transaction_kind == "INCOME"
        )
        if not is_trans and not is_inc and pmt.amount > 0:
            pmt.amount = -abs(pmt.amount)
            migrated_count += 1
    if migrated_count > 0:
        await db.commit()
        print(f"[Migration] Migrated {migrated_count} legacy expense payments to negative outflow signs.")

async def build_category_lineage_map(db: AsyncSession) -> Dict[int, Dict[str, Any]]:
    """
    Loads all categories and computes ancestors, level (1..5), full path, and effective label.
    """
    stmt = select(Category)
    res = await db.execute(stmt)
    all_cats = res.scalars().all()
    
    cat_by_id = {c.category_id: c for c in all_cats}
    lineage_map: Dict[int, Dict[str, Any]] = {}

    for cid, cat in cat_by_id.items():
        ancestors = []
        curr = cat
        visited = set()
        while curr and curr.category_id not in visited:
            visited.add(curr.category_id)
            ancestors.append(curr)
            curr = cat_by_id.get(curr.parent_id) if curr.parent_id else None

        ancestors.reverse() # root to self
        level = len(ancestors)
        full_path = " / ".join(a.name for a in ancestors)

        # Resolve effective label: first non-null default_label walking backwards from self to root
        effective_label = None
        for a in reversed(ancestors):
            if a.default_label:
                effective_label = a.default_label
                break
        
        if not effective_label:
            effective_label = LABEL_ESSENTIAL if cat.category_type == "INCOME" else LABEL_DISCRETIONARY

        lineage_map[cid] = {
            "category": cat,
            "level": level,
            "full_path": full_path,
            "effective_label": effective_label,
            "ancestors": ancestors,
            "root": ancestors[0] if ancestors else cat,
        }

    return lineage_map

async def load_unified_cashflow_flows(
    db: AsyncSession,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    master_currency: str = "EUR",
) -> List[Dict[str, Any]]:
    """
    Extracts and standardizes all financial flow events across:
    1. CashflowTransaction & CashflowItem records (day-to-day income, spends, transfers)
    2. Transaction trade records (stock buys, sells, dividends, interest, fees, taxes)
    All monetary amounts are converted to master_currency.
    """
    target_currency = (master_currency or "EUR").strip().upper()
    lineage_map = await build_category_lineage_map(db)

    flows: List[Dict[str, Any]] = []

    # 1. Day-to-day cashflow transactions
    stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
    )
    if start_date:
        stmt = stmt.where(CashflowTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(CashflowTransaction.transaction_date <= end_date)

    res = await db.execute(stmt)
    transactions = res.scalars().all()

    for tx in transactions:
        for item in tx.items:
            cat_id = item.category_id
            meta = lineage_map.get(cat_id)
            if not meta:
                continue

            ancestors = meta["ancestors"]
            cat_type = meta["category"].category_type
            effective_label = item.label or meta["effective_label"]
            raw_amt = float(item.amount or 0.0)
            amt = convert_currency(raw_amt, tx.currency or "EUR", target_currency)

            if cat_type == "TRANSFER":
                continue

            if cat_type == "INCOME" or (cat_type == "INVESTMENT" and tx.transaction_kind == "INCOME"):
                flow_type = "INCOME"
            elif cat_type == "INVESTMENT":
                flow_type = "INVESTMENT"
            else:
                flow_type = "EXPENSE"

            lineage_names = [a.name for a in ancestors]
            flows.append({
                "flow_type": flow_type,
                "effective_label": effective_label,
                "amount": amt,
                "lineage": lineage_names,
                "title": tx.title,
                "date": tx.transaction_date,
            })

    # 2. Investment transactions from Transaction table
    tx_stmt = select(Transaction).options(
        selectinload(Transaction.account),
        selectinload(Transaction.asset)
    )
    if start_date:
        tx_stmt = tx_stmt.where(Transaction.transaction_date >= start_date)
    if end_date:
        tx_stmt = tx_stmt.where(Transaction.transaction_date <= end_date)

    tx_res = await db.execute(tx_stmt)
    trades = tx_res.scalars().all()

    for t in trades:
        ttype = (t.transaction_type or "").lower()
        acc_curr = (t.account.currency if t.account else None) or "USD"
        qty = float(t.quantity or 0.0)
        ppu = float(t.price_per_unit or 0.0)
        gross_amt = (qty * ppu) if (qty > 0 and ppu > 0) else float(t.total_amount or 0.0)
        fees = float(t.fees or 0.0)
        taxes = float(t.taxes or 0.0)
        asset_label = (t.asset.symbol + (f" - {t.asset.name}" if t.asset.name else "")) if t.asset else "Securities Trade"

        if ttype == "buy":
            # Buy Principal -> Investment Outflow
            if gross_amt > 0:
                flows.append({
                    "flow_type": "INVESTMENT",
                    "effective_label": LABEL_INVESTMENT,
                    "amount": convert_currency(gross_amt, acc_curr, target_currency),
                    "lineage": ["Investments", "Stock & ETF Purchases", asset_label],
                    "title": f"Buy {t.asset.symbol if t.asset else ''}",
                    "date": t.transaction_date,
                })
            # Buy Fees -> Expense Outflow (Essential)
            if fees > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(fees, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Bank & Brokerage Fees"],
                    "title": "Brokerage Fees",
                    "date": t.transaction_date,
                })
            # Buy Taxes -> Expense Outflow (Essential)
            if taxes > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(taxes, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Taxes & Duties"],
                    "title": "Securities Taxes & Duties",
                    "date": t.transaction_date,
                })
        elif ttype == "sell":
            # Sell Gross Proceeds -> Inflow
            if gross_amt > 0:
                flows.append({
                    "flow_type": "INCOME",
                    "effective_label": LABEL_INVESTMENT,
                    "amount": convert_currency(gross_amt, acc_curr, target_currency),
                    "lineage": ["Investment Inflows", "Stock Sale Proceeds", asset_label],
                    "title": f"Sell {t.asset.symbol if t.asset else ''}",
                    "date": t.transaction_date,
                })
            if fees > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(fees, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Bank & Brokerage Fees"],
                    "title": "Brokerage Fees",
                    "date": t.transaction_date,
                })
            if taxes > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(taxes, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Taxes & Duties"],
                    "title": "Securities Taxes & Duties",
                    "date": t.transaction_date,
                })
        elif ttype == "dividend":
            # Gross Dividend -> Inflow
            if gross_amt > 0:
                flows.append({
                    "flow_type": "INCOME",
                    "effective_label": LABEL_INVESTMENT,
                    "amount": convert_currency(gross_amt, acc_curr, target_currency),
                    "lineage": ["Investment Inflows", "Dividends Received", asset_label],
                    "title": f"Dividend {t.asset.symbol if t.asset else ''}",
                    "date": t.transaction_date,
                })
            if taxes > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(taxes, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Taxes & Duties"],
                    "title": "Dividend Tax Withheld (TDS)",
                    "date": t.transaction_date,
                })
        elif ttype == "interest":
            if gross_amt > 0:
                flows.append({
                    "flow_type": "INCOME",
                    "effective_label": LABEL_INVESTMENT,
                    "amount": convert_currency(gross_amt, acc_curr, target_currency),
                    "lineage": ["Investment Inflows", "Interest Income"],
                    "title": "Interest",
                    "date": t.transaction_date,
                })
        elif ttype == "fee":
            fee_tot = gross_amt + fees + taxes
            if fee_tot > 0:
                flows.append({
                    "flow_type": "EXPENSE",
                    "effective_label": LABEL_ESSENTIAL,
                    "amount": convert_currency(fee_tot, acc_curr, target_currency),
                    "lineage": ["Spends", "Financial & Taxes", "Bank & Brokerage Fees"],
                    "title": "Account Fee",
                    "date": t.transaction_date,
                })

    return flows

async def generate_sankey_data(
    db: AsyncSession,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    depth: int = 2,
    include_investments: bool = True,
    master_currency: str = "EUR"
) -> SankeyDataResponse:
    """
    Generates Sankey Nodes and Links with true multi-layer expansion:
    - Depth 1 (3 columns): Inflow Roots (1) -> Total Inflow Pool (2) -> Outflow Roots (3)
    - Depth 2 (5 columns): Insub1 (1) -> Inflow Roots (2) -> Total Inflow Pool (3) -> Outflow Roots (4) -> Outsub1 (5)
    - Depth 3 (7 columns): Insub2 (1) -> Insub1 (2) -> Inflow Roots (3) -> Total Inflow Pool (4) -> Outflow Roots (5) -> Outsub1 (6) -> Outsub2 (7)
    - Depth 4 & 5 expand subcategories further.
    Parent layers are preserved without replacement.
    """
    depth = max(1, min(5, depth))
    target_currency = (master_currency or "EUR").strip().upper()

    flows = await load_unified_cashflow_flows(
        db, start_date=start_date, end_date=end_date, master_currency=target_currency
    )
    if not include_investments:
        flows = [f for f in flows if f["flow_type"] != "INVESTMENT" and f.get("effective_label") != LABEL_INVESTMENT]

    total_income = sum(f["amount"] for f in flows if f["flow_type"] == "INCOME")
    total_expenses = sum(f["amount"] for f in flows if f["flow_type"] == "EXPENSE")
    total_investments = sum(f["amount"] for f in flows if f["flow_type"] == "INVESTMENT")

    nodes: List[SankeyNode] = []
    links: List[SankeyLink] = []
    node_id_set: Set[str] = set()

    def add_node(nid: str, name: str, level: int, color: Optional[str] = None, c_type: Optional[str] = None):
        if nid not in node_id_set:
            node_id_set.add(nid)
            nodes.append(SankeyNode(
                id=nid,
                name=name,
                level=level,
                color=color or "#64748B",
                category_type=c_type
            ))

    link_map: Dict[Tuple[str, str], float] = {}
    link_color_map: Dict[Tuple[str, str], str] = {}

    def add_link(src: str, tgt: str, val: float, color: str):
        if val <= 0.001:
            return
        key = (src, tgt)
        link_map[key] = link_map.get(key, 0.0) + val
        link_color_map[key] = color

    # Center Hub Node
    hub_id = "node_cash_inflow"
    hub_level = depth + 1
    add_node(hub_id, "Total Inflow Pool", level=hub_level, color="#10B981")

    # Inflows Processing
    inflows = [f for f in flows if f["flow_type"] == "INCOME" and f["amount"] > 0]
    for inf in inflows:
        amt = inf["amount"]
        lineage = inf["lineage"] or ["Income"]

        max_k = min(len(lineage) - 1, depth - 1)
        prev_node_id = None
        for k in range(max_k, -1, -1):
            name = lineage[k]
            lvl = depth - k
            nid = f"in_{lvl}_{name.lower().replace(' ', '_')}"
            c_color = "#10B981" if k == 0 else ("#34D399" if k == 1 else "#6EE7B7")
            add_node(nid, name, level=lvl, color=c_color, c_type="INCOME")

            if prev_node_id:
                add_link(prev_node_id, nid, amt, "#34D399")

            prev_node_id = nid

        root_name = lineage[0]
        root_id = f"in_{depth}_{root_name.lower().replace(' ', '_')}"
        add_link(root_id, hub_id, amt, "#10B981")

    # Check for Deficit
    total_outflows = total_expenses + total_investments
    if total_outflows > total_income + 0.001:
        deficit = total_outflows - total_income
        sav_src_id = f"in_{depth}_savings_used"
        add_node(sav_src_id, "Savings / Reserves Used", level=depth, color="#F59E0B", c_type="INCOME")
        add_link(sav_src_id, hub_id, deficit, "#FBBF24")

    # Outflows Processing
    outflows = [f for f in flows if f["flow_type"] in ("EXPENSE", "INVESTMENT") and f["amount"] > 0]
    for out in outflows:
        amt = out["amount"]
        ftype = out["flow_type"]
        lbl = out.get("effective_label") or LABEL_DISCRETIONARY
        lineage = out["lineage"] or []

        if ftype == "INVESTMENT":
            root_out_name = "Investments"
            root_color = "#3B82F6"
        else:
            if lbl == LABEL_ESSENTIAL:
                root_out_name = "Essential"
                root_color = "#10B981"
            elif lbl == LABEL_LUXURY:
                root_out_name = "Luxury"
                root_color = "#EC4899"
            else:
                root_out_name = "Discretionary"
                root_color = "#F59E0B"

        root_out_id = f"out_{depth + 2}_{root_out_name.lower()}"
        add_node(root_out_id, root_out_name, level=depth + 2, color=root_color, c_type=ftype)
        add_link(hub_id, root_out_id, amt, root_color)

        sub_chain: List[str] = []
        for idx in range(1, len(lineage)):
            sub_chain.append(lineage[idx])

        prev_node_id = root_out_id
        for j in range(min(len(sub_chain), depth - 1)):
            sub_name = sub_chain[j]
            lvl = depth + 3 + j
            nid = f"out_{lvl}_{sub_name.lower().replace(' ', '_')}"
            add_node(nid, sub_name, level=lvl, color=root_color, c_type=ftype)
            add_link(prev_node_id, nid, amt, root_color)
            prev_node_id = nid

    # Check for Surplus
    if total_income > total_outflows + 0.001:
        surplus = total_income - total_outflows
        sav_id = f"out_{depth + 2}_retained_cash"
        add_node(sav_id, "Retained Cash / Added to Savings", level=depth + 2, color="#059669")
        add_link(hub_id, sav_id, surplus, "#10B981")

    # Build Links list
    for (s, t), val in link_map.items():
        links.append(SankeyLink(
            source=s,
            target=t,
            value=round(val, 2),
            color=link_color_map.get((s, t))
        ))

    return SankeyDataResponse(
        nodes=nodes,
        links=links,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        total_investments=round(total_investments, 2),
        depth=depth
    )

async def get_cashflow_summary(
    db: AsyncSession,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    include_investments: bool = True,
    master_currency: str = "EUR"
) -> CashflowSummaryResponse:
    """
    Computes summary KPI metrics and label distribution for Income & Spends dashboard.
    """
    target_currency = (master_currency or "EUR").strip().upper()

    flows = await load_unified_cashflow_flows(
        db, start_date=start_date, end_date=end_date, master_currency=target_currency
    )
    if not include_investments:
        flows = [f for f in flows if f["flow_type"] != "INVESTMENT" and f.get("effective_label") != LABEL_INVESTMENT]

    total_income = sum(f["amount"] for f in flows if f["flow_type"] == "INCOME")
    total_expenses = sum(f["amount"] for f in flows if f["flow_type"] == "EXPENSE")
    total_invested = sum(f["amount"] for f in flows if f["flow_type"] == "INVESTMENT")

    breakdown_by_label: Dict[str, float] = {
        LABEL_ESSENTIAL: 0.0,
        LABEL_DISCRETIONARY: 0.0,
        LABEL_LUXURY: 0.0,
        LABEL_INVESTMENT: 0.0
    }
    cat_expense_totals: Dict[str, float] = {}

    for f in flows:
        lbl = f.get("effective_label")
        if f["flow_type"] == "INVESTMENT":
            breakdown_by_label[LABEL_INVESTMENT] += f["amount"]
        elif f["flow_type"] == "EXPENSE":
            valid_lbl = lbl if lbl in breakdown_by_label else LABEL_DISCRETIONARY
            breakdown_by_label[valid_lbl] += f["amount"]

            lineage = f.get("lineage") or ["General"]
            cat_name = lineage[-1] if len(lineage) > 1 else lineage[0]
            cat_expense_totals[cat_name] = cat_expense_totals.get(cat_name, 0.0) + f["amount"]

    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100.0) if total_income > 0 else 0.0

    sorted_cats = sorted(
        [{"category": k, "amount": round(v, 2), "pct": round((v / total_expenses * 100.0) if total_expenses > 0 else 0.0, 1)}
         for k, v in cat_expense_totals.items()],
        key=lambda x: x["amount"],
        reverse=True
    )[:8]

    return CashflowSummaryResponse(
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        total_invested=round(total_invested, 2),
        net_savings=round(net_savings, 2),
        savings_rate_pct=round(savings_rate, 2),
        breakdown_by_label={k: round(v, 2) for k, v in breakdown_by_label.items()},
        top_expense_categories=sorted_cats
    )
