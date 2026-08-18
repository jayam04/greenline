import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import selectinload

from app.db.models import Category, CashflowTransaction, CashflowPayment, CashflowItem, Account, Transaction, LotSale
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

def convert_currency_to_eur(amount: float, from_currency: str = "EUR") -> float:
    if not amount:
        return 0.0
    curr = (from_currency or "EUR").strip().upper()
    rate = FX_RATES_TO_EUR.get(curr, 1.0)
    return amount * rate

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
                "name": "Investments & Passive",
                "default_label": LABEL_INVESTMENT,
                "icon": "DollarSign",
                "color": "#6EE7B7",
                "children": [
                    {"name": "Dividends", "default_label": LABEL_INVESTMENT},
                    {"name": "Interest & Staking", "default_label": LABEL_INVESTMENT},
                    {"name": "Realized Capital Gains", "default_label": LABEL_INVESTMENT},
                    {"name": "Rental Income", "default_label": LABEL_INVESTMENT},
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
                ]
            }
        ]
    },
    # 2. Expenses Tree
    {
        "name": "Expenses",
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
    # 3. Investments & Savings Tree
    {
        "name": "Investments & Savings",
        "category_type": "INVESTMENT",
        "default_label": LABEL_INVESTMENT,
        "icon": "PiggyBank",
        "color": "#3B82F6",
        "children": [
            {"name": "Stock & ETF Purchases", "default_label": LABEL_INVESTMENT},
            {"name": "Crypto Allocation", "default_label": LABEL_INVESTMENT},
            {"name": "Emergency Fund Reserve", "default_label": LABEL_INVESTMENT},
            {"name": "Pension & Retirement (NPS / 401k)", "default_label": LABEL_INVESTMENT},
        ]
    }
]

async def seed_default_categories(db: AsyncSession):
    """
    Seeds the standard 5-level category hierarchy if the categories table is empty.
    """
    stmt = select(func.count(Category.category_id))
    res = await db.execute(stmt)
    count = res.scalar() or 0
    if count > 0:
        return

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

    for root_node in DEFAULT_CATEGORIES_TREE:
        await _insert_node(root_node, None, root_node["category_type"], root_node["default_label"])

    await db.commit()
    print("[Seed] Successfully seeded default 5-level category hierarchy.")

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
        while curr:
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

async def generate_sankey_data(
    db: AsyncSession,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    depth: int = 2,
    include_investments: bool = True
) -> SankeyDataResponse:
    """
    Generates Sankey Nodes and Links structured for depth 1 to 5:
    - Left: Income Sources (at chosen depth)
    - Center: Total Cash Inflow Pool
    - Flow to Label Nodes (ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT)
    - Right: Category breakdown down to specified depth (1 to 5)
    """
    depth = max(1, min(5, depth))
    lineage_map = await build_category_lineage_map(db)

    # 1. Fetch cashflow transactions in date range
    stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
    )
    if start_date:
        stmt = stmt.where(CashflowTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(CashflowTransaction.transaction_date <= end_date)

    res = await db.execute(stmt)
    transactions = res.scalars().all()

    income_flows: Dict[str, float] = {}
    expense_flows_by_label: Dict[str, Dict[str, float]] = {
        LABEL_ESSENTIAL: {},
        LABEL_DISCRETIONARY: {},
        LABEL_LUXURY: {},
        LABEL_INVESTMENT: {}
    }
    
    total_income = 0.0
    total_expenses = 0.0
    total_investments = 0.0

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
            amt = convert_currency_to_eur(raw_amt, tx.currency or "EUR")

            # Determine category name at requested depth
            target_idx = min(depth - 1, len(ancestors) - 1)
            target_name = ancestors[target_idx].name

            if cat_type == "INCOME":
                total_income += amt
                # For income, represent source at depth
                src_name = target_name
                income_flows[src_name] = income_flows.get(src_name, 0.0) + amt
            elif cat_type == "INVESTMENT":
                total_investments += amt
                expense_flows_by_label[LABEL_INVESTMENT][target_name] = (
                    expense_flows_by_label[LABEL_INVESTMENT].get(target_name, 0.0) + amt
                )
            else: # EXPENSE
                total_expenses += amt
                lbl = effective_label if effective_label in expense_flows_by_label else LABEL_DISCRETIONARY
                expense_flows_by_label[lbl][target_name] = (
                    expense_flows_by_label[lbl].get(target_name, 0.0) + amt
                )

    # 2. Include Investment Dividends & Sales if enabled
    if include_investments:
        # Fetch stock dividends
        div_stmt = select(func.sum(Transaction.total_amount))\
            .where(Transaction.transaction_type == "dividend")
        if start_date:
            div_stmt = div_stmt.where(Transaction.transaction_date >= start_date)
        if end_date:
            div_stmt = div_stmt.where(Transaction.transaction_date <= end_date)
        div_res = await db.execute(div_stmt)
        div_total = div_res.scalar_one_or_none() or 0.0

        if div_total > 0.01:
            total_income += div_total
            income_flows["Stock Dividends"] = income_flows.get("Stock Dividends", 0.0) + div_total

        # Fetch realized stock sales profits
        rpnl_stmt = select(func.sum(LotSale.realized_pnl))\
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
        if start_date:
            rpnl_stmt = rpnl_stmt.where(Transaction.transaction_date >= start_date)
        if end_date:
            rpnl_stmt = rpnl_stmt.where(Transaction.transaction_date <= end_date)
        rpnl_res = await db.execute(rpnl_stmt)
        rpnl_total = rpnl_res.scalar_one_or_none() or 0.0

        if rpnl_total > 0.01:
            total_income += rpnl_total
            income_flows["Realized Stock Gains"] = income_flows.get("Realized Stock Gains", 0.0) + rpnl_total

    # 3. Construct Sankey Nodes and Links
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

    # Center Hub Node
    hub_id = "node_cash_inflow"
    add_node(hub_id, "Total Inflow Pool", level=2, color="#10B981")

    # Inflow Links: [Income Source] -> [Total Inflow Pool]
    for src_name, amt in income_flows.items():
        if amt <= 0.001:
            continue
        src_id = f"inc_{src_name.lower().replace(' ', '_')}"
        add_node(src_id, src_name, level=1, color="#10B981", c_type="INCOME")
        links.append(SankeyLink(source=src_id, target=hub_id, value=round(amt, 2), color="#34D399"))

    # Outflow Nodes & Links based on Depth:
    if depth == 1:
        # High Level: Inflow Pool -> Expenses, Investments, Savings
        if total_expenses > 0:
            exp_id = "node_expenses"
            add_node(exp_id, "Total Expenses", level=3, color="#EF4444", c_type="EXPENSE")
            links.append(SankeyLink(source=hub_id, target=exp_id, value=round(total_expenses, 2), color="#F87171"))
        
        if total_investments > 0:
            inv_id = "node_investments"
            add_node(inv_id, "Investments & Savings", level=3, color="#3B82F6", c_type="INVESTMENT")
            links.append(SankeyLink(source=hub_id, target=inv_id, value=round(total_investments, 2), color="#60A5FA"))

        net_savings = total_income - (total_expenses + total_investments)
        if net_savings > 0:
            sav_id = "node_retained_cash"
            add_node(sav_id, "Retained Cash Buffer", level=3, color="#059669")
            links.append(SankeyLink(source=hub_id, target=sav_id, value=round(net_savings, 2), color="#10B981"))
    else:
        # Depth >= 2: Inflow Pool -> Label Nodes -> Category Breakdown Nodes
        for label_key, cat_map in expense_flows_by_label.items():
            label_sum = sum(cat_map.values())
            if label_sum <= 0.001:
                continue

            label_node_id = f"lbl_{label_key.lower()}"
            lbl_color = DEFAULT_CATEGORY_COLORS.get(label_key, "#64748B")
            add_node(label_node_id, label_key.replace("_", " ").title(), level=3, color=lbl_color)
            links.append(SankeyLink(source=hub_id, target=label_node_id, value=round(label_sum, 2), color=lbl_color))

            for cat_name, cat_amt in cat_map.items():
                if cat_amt <= 0.001:
                    continue
                cat_node_id = f"cat_{cat_name.lower().replace(' ', '_')}"
                add_node(cat_node_id, cat_name, level=4, color=lbl_color)
                links.append(SankeyLink(source=label_node_id, target=cat_node_id, value=round(cat_amt, 2), color=lbl_color))

        # Retained buffer link if income > outflows
        net_savings = total_income - (total_expenses + total_investments)
        if net_savings > 0.01:
            sav_id = "node_retained_cash"
            add_node(sav_id, "Retained Cash", level=3, color="#059669")
            links.append(SankeyLink(source=hub_id, target=sav_id, value=round(net_savings, 2), color="#10B981"))

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
    end_date: Optional[datetime.date] = None
) -> CashflowSummaryResponse:
    """
    Computes summary KPI metrics and label distribution for Income & Spends dashboard.
    """
    lineage_map = await build_category_lineage_map(db)

    stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
    )
    if start_date:
        stmt = stmt.where(CashflowTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(CashflowTransaction.transaction_date <= end_date)

    res = await db.execute(stmt)
    transactions = res.scalars().all()

    total_income = 0.0
    total_expenses = 0.0
    total_invested = 0.0
    breakdown_by_label: Dict[str, float] = {
        LABEL_ESSENTIAL: 0.0,
        LABEL_DISCRETIONARY: 0.0,
        LABEL_LUXURY: 0.0,
        LABEL_INVESTMENT: 0.0
    }
    cat_expense_totals: Dict[str, float] = {}

    for tx in transactions:
        for item in tx.items:
            meta = lineage_map.get(item.category_id)
            if not meta:
                continue

            cat_type = meta["category"].category_type
            effective_label = item.label or meta["effective_label"]
            raw_amt = float(item.amount or 0.0)
            amt = convert_currency_to_eur(raw_amt, tx.currency or "EUR")

            if cat_type == "INCOME":
                total_income += amt
            elif cat_type == "INVESTMENT":
                total_invested += amt
                breakdown_by_label[LABEL_INVESTMENT] += amt
            else: # EXPENSE
                total_expenses += amt
                lbl = effective_label if effective_label in breakdown_by_label else LABEL_DISCRETIONARY
                breakdown_by_label[lbl] += amt
                
                cat_name = meta["category"].name
                cat_expense_totals[cat_name] = cat_expense_totals.get(cat_name, 0.0) + amt

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
