import datetime
import math
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload
from app.db.models import (
    NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory, 
    LotSale, Transaction, Asset, Account, CashflowTransaction, 
    CashflowPayment, CashflowItem
)
from app.services.cashflow_engine import resolve_transaction_kind

FX_RATES_TO_EUR = {
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

def to_eur(amount: float, curr: str) -> float:
    rate = FX_RATES_TO_EUR.get((curr or "EUR").upper(), 1.0)
    return amount * rate

async def generate_daily_snapshot(db: AsyncSession, snapshot_date: datetime.date = None) -> NetworthSnapshot:
    if snapshot_date is None:
        snapshot_date = datetime.date.today()

    # 1. Fetch all lots bought on or before snapshot_date
    lot_stmt = select(Lot).where(Lot.buy_date <= snapshot_date)
    lot_res = await db.execute(lot_stmt)
    all_lots: List[Lot] = lot_res.scalars().all()

    # Calculate remaining lot quantities as of snapshot_date
    open_lots_as_of_date: List[Dict] = []
    asset_ids = set()

    for lot in all_lots:
        sale_stmt = (
            select(func.sum(LotSale.quantity_sold))
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(
                LotSale.lot_id == lot.lot_id,
                Transaction.transaction_date <= snapshot_date
            )
        )
        sale_res = await db.execute(sale_stmt)
        sold_qty = sale_res.scalar_one_or_none() or 0.0
        rem_qty = max(0.0, lot.quantity_original - sold_qty)

        if rem_qty > 0.00000001:
            open_lots_as_of_date.append({
                "lot": lot,
                "remaining_quantity": rem_qty
            })
            asset_ids.add(lot.asset_id)

    # 2. Fetch closing price for each asset on or closest before snapshot_date
    price_map: Dict[int, float] = {}
    for aid in asset_ids:
        ph_stmt = (
            select(PriceHistory.close_price)
            .where(
                PriceHistory.asset_id == aid,
                PriceHistory.price_date <= snapshot_date
            )
            .order_by(desc(PriceHistory.price_date))
            .limit(1)
        )
        ph_res = await db.execute(ph_stmt)
        price = ph_res.scalar_one_or_none()
        if price is not None and not math.isnan(price) and not math.isinf(price) and price > 0:
            price_map[aid] = price
        else:
            lot_cost = next((item["lot"].cost_per_unit for item in open_lots_as_of_date if item["lot"].asset_id == aid), 0.0)
            price_map[aid] = lot_cost

    # 3. Sum current value and cost of open lots
    total_current_value = 0.0
    total_cost_of_open_lots = 0.0
    allocation_by_class: Dict[str, float] = {}

    for item in open_lots_as_of_date:
        lot: Lot = item["lot"]
        rem_qty: float = item["remaining_quantity"]
        p = price_map.get(lot.asset_id, lot.cost_per_unit)
        val = rem_qty * p
        cost = rem_qty * lot.cost_per_unit

        total_current_value += val
        total_cost_of_open_lots += cost

        asset_stmt = select(Asset).where(Asset.asset_id == lot.asset_id)
        asset_res = await db.execute(asset_stmt)
        asset = asset_res.scalar_one_or_none()
        aclass = asset.asset_type if asset else "other"
        allocation_by_class[aclass] = allocation_by_class.get(aclass, 0.0) + val

    total_unrealized_pnl = total_current_value - total_cost_of_open_lots

    # 4. Total Realized PnL as of snapshot_date
    realized_stmt = (
        select(func.sum(LotSale.realized_pnl))
        .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
        .where(Transaction.transaction_date <= snapshot_date)
    )
    realized_res = await db.execute(realized_stmt)
    total_realized_pnl = realized_res.scalar_one_or_none() or 0.0

    # 5. Cash balance and total invested as of snapshot_date
    tx_stmt = select(Transaction).where(Transaction.transaction_date <= snapshot_date)
    tx_res = await db.execute(tx_stmt)
    all_txs: List[Transaction] = tx_res.scalars().all()

    cash_balance = 0.0
    total_invested = 0.0

    for tx in all_txs:
        ttype = (tx.transaction_type or "").lower()
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)
        if ttype == "deposit":
            cash_balance += amt
            total_invested += amt
        elif ttype == "withdrawal":
            cash_balance -= amt
            total_invested -= amt
        elif ttype == "buy":
            cash_balance -= (amt + fees + taxes)
        elif ttype == "sell":
            cash_balance += (amt - fees - taxes)
        elif ttype in ["dividend", "interest"]:
            cash_balance += (amt - fees - taxes)

    # Add cashflow payments as of snapshot_date
    cf_stmt = select(CashflowTransaction, CashflowPayment)\
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)\
        .options(selectinload(CashflowTransaction.items).selectinload(CashflowItem.category))\
        .where(CashflowTransaction.transaction_date <= snapshot_date)
    cf_res = await db.execute(cf_stmt)
    for ctx, pmt in cf_res.all():
        tkind = resolve_transaction_kind(ctx)
        amt = float(pmt.amount or 0.0)
        cash_balance += amt
        if amt > 0 and tkind == "INCOME":
            total_invested += amt

    if cash_balance > 0:
        allocation_by_class["cash"] = cash_balance

    net_worth = total_current_value + cash_balance

    # Check existing snapshot for date to overwrite or insert
    snap_stmt = select(NetworthSnapshot).where(NetworthSnapshot.snapshot_date == snapshot_date)
    snap_res = await db.execute(snap_stmt)
    snapshot = snap_res.scalar_one_or_none()

    if snapshot is None:
        snapshot = NetworthSnapshot(
            snapshot_date=snapshot_date,
            total_invested=total_invested,
            total_current_value=total_current_value,
            cash_balance=cash_balance,
            total_realized_pnl=total_realized_pnl,
            total_unrealized_pnl=total_unrealized_pnl,
            net_worth=net_worth
        )
        db.add(snapshot)
        await db.flush()
    else:
        snapshot.total_invested = total_invested
        snapshot.total_current_value = total_current_value
        snapshot.cash_balance = cash_balance
        snapshot.total_realized_pnl = total_realized_pnl
        snapshot.total_unrealized_pnl = total_unrealized_pnl
        snapshot.net_worth = net_worth
        
        # Clear existing breakdowns
        del_stmt = select(NetworthByAssetClass).where(NetworthByAssetClass.snapshot_id == snapshot.snapshot_id)
        del_res = await db.execute(del_stmt)
        for old_b in del_res.scalars().all():
            await db.delete(old_b)

    for aclass, val in allocation_by_class.items():
        db.add(NetworthByAssetClass(
            snapshot_id=snapshot.snapshot_id,
            asset_class=aclass,
            value=val
        ))

    await db.commit()
    await db.refresh(snapshot)
    return snapshot

async def recalculate_past_snapshots(db: AsyncSession, start_date: datetime.date, end_date: datetime.date = None) -> int:
    if end_date is None:
        end_date = datetime.date.today()

    if start_date > end_date:
        start_date = end_date

    count = 0
    curr_date = start_date
    delta = datetime.timedelta(days=1)

    while curr_date <= end_date:
        await generate_daily_snapshot(db, curr_date)
        count += 1
        curr_date += delta

    return count

async def calculate_account_snapshots(
    db: AsyncSession,
    account_id: int,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None
) -> List[Dict]:
    """
    Computes daily timeline data points for a specific account, combining both
    investment transactions and cashflow income/expense/transfer payments.
    """
    if end_date is None:
        end_date = datetime.date.today()

    # 1. Find earliest date for this account across Transaction and CashflowPayment
    if start_date is None:
        min_tx_stmt = select(func.min(Transaction.transaction_date)).where(Transaction.account_id == account_id)
        min_tx_res = await db.execute(min_tx_stmt)
        min_tx = min_tx_res.scalar_one_or_none()

        min_cf_stmt = select(func.min(CashflowTransaction.transaction_date))\
            .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)\
            .where(CashflowPayment.account_id == account_id)
        min_cf_res = await db.execute(min_cf_stmt)
        min_cf = min_cf_res.scalar_one_or_none()

        valid_dates = [d for d in [min_tx, min_cf] if d is not None]
        if not valid_dates:
            # Check account created_at or default to today
            acc_stmt = select(Account.created_at).where(Account.account_id == account_id)
            acc_res = await db.execute(acc_stmt)
            acc_created = acc_res.scalar_one_or_none()
            if acc_created:
                start_date = acc_created
            else:
                return []
        else:
            start_date = min(valid_dates)

    # 2. Fetch all lots for this account
    lot_stmt = select(Lot).where(Lot.account_id == account_id)
    lot_res = await db.execute(lot_stmt)
    account_lots: List[Lot] = lot_res.scalars().all()
    lot_ids = [l.lot_id for l in account_lots]

    # Fetch lot sales
    sales_map: Dict[int, List[Tuple[datetime.date, float, float]]] = {}
    if lot_ids:
        sale_stmt = (
            select(LotSale.lot_id, Transaction.transaction_date, LotSale.quantity_sold, LotSale.realized_pnl)
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(LotSale.lot_id.in_(lot_ids))
        )
        sale_res = await db.execute(sale_stmt)
        for lid, sdate, qsold, rpnl in sale_res.all():
            if lid not in sales_map:
                sales_map[lid] = []
            sales_map[lid].append((sdate, qsold, rpnl))

    # 3. Fetch all price histories for assets in this account
    asset_ids = list(set(l.asset_id for l in account_lots))
    prices_map: Dict[int, List[Tuple[datetime.date, float]]] = {}
    if asset_ids:
        ph_stmt = select(PriceHistory.asset_id, PriceHistory.price_date, PriceHistory.close_price)\
            .where(PriceHistory.asset_id.in_(asset_ids))\
            .order_by(asc(PriceHistory.price_date))
        ph_res = await db.execute(ph_stmt)
        for aid, pdate, cprice in ph_res.all():
            if aid not in prices_map:
                prices_map[aid] = []
            prices_map[aid].append((pdate, cprice))

    # 4. Fetch all investment transactions for this account
    tx_stmt = select(Transaction).where(Transaction.account_id == account_id).order_by(asc(Transaction.transaction_date))
    tx_res = await db.execute(tx_stmt)
    all_txs: List[Transaction] = tx_res.scalars().all()

    # 5. Fetch all cashflow payments for this account
    cf_stmt = select(CashflowTransaction, CashflowPayment)\
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)\
        .options(selectinload(CashflowTransaction.items).selectinload(CashflowItem.category))\
        .where(CashflowPayment.account_id == account_id)\
        .order_by(asc(CashflowTransaction.transaction_date))
    cf_res = await db.execute(cf_stmt)
    cf_records = cf_res.all()

    cf_events = []
    for ctx, pmt in cf_records:
        tkind = resolve_transaction_kind(ctx)
        signed_amt = float(pmt.amount or 0.0)
        is_income = signed_amt > 0 and tkind == "INCOME"
        cf_events.append((ctx.transaction_date, signed_amt, is_income))

    # 6. Iterate day by day from start_date to end_date
    snapshots_list = []
    curr_date = start_date
    delta = datetime.timedelta(days=1)

    while curr_date <= end_date:
        # A. Open lots valuation as of curr_date
        total_curr_val = 0.0
        total_cost_basis = 0.0

        for lot in account_lots:
            if lot.buy_date <= curr_date:
                sold_qty = sum(q for sdate, q, _ in sales_map.get(lot.lot_id, []) if sdate <= curr_date)
                rem_qty = max(0.0, lot.quantity_original - sold_qty)
                if rem_qty > 0.00000001:
                    p_list = [p for pdate, p in prices_map.get(lot.asset_id, []) if pdate <= curr_date and p is not None and not math.isnan(p) and p > 0]
                    price = p_list[-1] if p_list else lot.cost_per_unit
                    if price is None or (isinstance(price, float) and (math.isnan(price) or math.isinf(price) or price <= 0)):
                        price = lot.cost_per_unit
                    total_curr_val += rem_qty * price
                    total_cost_basis += rem_qty * lot.cost_per_unit

        # B. Realized PnL as of curr_date
        total_rpnl = sum(
            sum(rpnl for sdate, _, rpnl in sales_list if sdate <= curr_date)
            for sales_list in sales_map.values()
        )

        # C. Cumulative Cash balance & Total invested as of curr_date
        cash_balance = 0.0
        total_invested = 0.0

        for tx in all_txs:
            if tx.transaction_date <= curr_date:
                ttype = (tx.transaction_type or "").lower()
                amt = float(tx.total_amount or 0.0)
                fees = float(tx.fees or 0.0)
                taxes = float(tx.taxes or 0.0)
                if ttype == "deposit":
                    cash_balance += amt
                    total_invested += amt
                elif ttype == "withdrawal":
                    cash_balance -= amt
                    total_invested -= amt
                elif ttype == "buy":
                    cash_balance -= (amt + fees + taxes)
                elif ttype == "sell":
                    cash_balance += (amt - fees - taxes)
                elif ttype in ["dividend", "interest"]:
                    cash_balance += (amt - fees - taxes)

        for cf_date, signed_amt, is_inc in cf_events:
            if cf_date <= curr_date:
                cash_balance += signed_amt
                if is_inc:
                    total_invested += max(0.0, signed_amt)

        net_worth = total_curr_val + cash_balance
        total_unrealized = total_curr_val - total_cost_basis

        snapshots_list.append({
            "snapshot_id": 0,
            "snapshot_date": curr_date,
            "total_invested": total_invested if total_invested > 0 else total_cost_basis,
            "total_current_value": total_curr_val,
            "cash_balance": cash_balance,
            "total_realized_pnl": total_rpnl,
            "total_unrealized_pnl": total_unrealized,
            "net_worth": net_worth,
            "asset_class_breakdowns": []
        })

        curr_date += delta

    return snapshots_list
