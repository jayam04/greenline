import datetime
import math
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from app.db.models import (
    NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory, 
    LotSale, Transaction, Asset, Account
)

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
        # Sum sales of this lot where sell_transaction.transaction_date <= snapshot_date
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
                "asset_id": lot.asset_id,
                "rem_qty": rem_qty,
                "cost_per_unit": lot.cost_per_unit,
            })
            asset_ids.add(lot.asset_id)

    # 2. Fetch latest price for each asset as of snapshot_date
    latest_prices: Dict[int, float] = {}
    for aid in asset_ids:
        p_stmt = (
            select(PriceHistory.close_price)
            .where(PriceHistory.asset_id == aid, PriceHistory.price_date <= snapshot_date)
            .order_by(desc(PriceHistory.price_date))
            .limit(1)
        )
        p_res = await db.execute(p_stmt)
        price = p_res.scalar_one_or_none()
        if price is None or (isinstance(price, float) and (math.isnan(price) or math.isinf(price) or price <= 0)):
            # Fallback to lot cost_per_unit if no market price found on/before snapshot_date
            lot_cost = next((item["cost_per_unit"] for item in open_lots_as_of_date if item["asset_id"] == aid), 0.0)
            price = lot_cost
        latest_prices[aid] = price

    # Fetch asset objects for classification
    asset_map: Dict[int, Asset] = {}
    if asset_ids:
        a_stmt = select(Asset).where(Asset.asset_id.in_(list(asset_ids)))
        a_res = await db.execute(a_stmt)
        for asset in a_res.scalars().all():
            asset_map[asset.asset_id] = asset

    # 3. Calculate portfolio asset values
    total_current_value = 0.0
    total_cost_of_open_lots = 0.0
    allocation_by_class: Dict[str, float] = {}

    for item in open_lots_as_of_date:
        aid = item["asset_id"]
        rem_qty = item["rem_qty"]
        cost_per_unit = item["cost_per_unit"]
        price = latest_prices.get(aid, cost_per_unit)

        lot_val = rem_qty * price
        total_current_value += lot_val
        total_cost_of_open_lots += rem_qty * cost_per_unit

        asset = asset_map.get(aid)
        aclass = asset.asset_type.lower() if asset else "other"
        allocation_by_class[aclass] = allocation_by_class.get(aclass, 0.0) + lot_val

    total_unrealized_pnl = total_current_value - total_cost_of_open_lots

    # 4. Total Realized PnL as of snapshot_date (join with Transaction for transaction_date <= snapshot_date)
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
        ttype = tx.transaction_type.lower()
        if ttype == "deposit":
            cash_balance += tx.total_amount
            total_invested += tx.total_amount
        elif ttype == "withdrawal":
            cash_balance -= tx.total_amount
            total_invested -= tx.total_amount
        elif ttype == "buy":
            cash_balance -= (tx.total_amount + tx.fees + tx.taxes)
        elif ttype == "sell":
            cash_balance += (tx.total_amount - tx.fees - tx.taxes)
        elif ttype == "dividend":
            cash_balance += tx.total_amount

    if cash_balance > 0:
        allocation_by_class["cash"] = cash_balance

    net_worth = total_current_value + max(0.0, cash_balance)

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

async def recalculate_past_snapshots(
    db: AsyncSession, 
    start_date: datetime.date, 
    end_date: Optional[datetime.date] = None
) -> int:
    """
    Recalculates all daily snapshots from start_date to end_date (inclusive).
    Defaults end_date to today. Returns total count of snapshots calculated.
    """
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
    Computes daily timeline data points for a specific account.
    """
    if end_date is None:
        end_date = datetime.date.today()

    # Find earliest transaction date for this account
    if start_date is None:
        min_tx_stmt = select(func.min(Transaction.transaction_date)).where(Transaction.account_id == account_id)
        min_tx_res = await db.execute(min_tx_stmt)
        start_date = min_tx_res.scalar_one_or_none()
        if start_date is None:
            return []

    # Fetch all lots for this account
    lot_stmt = select(Lot).where(Lot.account_id == account_id)
    lot_res = await db.execute(lot_stmt)
    account_lots: List[Lot] = lot_res.scalars().all()
    lot_ids = [l.lot_id for l in account_lots]

    # Fetch all lot sales for this account's lots
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

    # Fetch all transactions for this account
    tx_stmt = select(Transaction).where(Transaction.account_id == account_id).order_by(asc(Transaction.transaction_date))
    tx_res = await db.execute(tx_stmt)
    all_txs: List[Transaction] = tx_res.scalars().all()

    # Fetch all price histories for assets in this account
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

    # Iterate day by day from start_date to end_date
    snapshots_list = []
    curr_date = start_date
    delta = datetime.timedelta(days=1)

    while curr_date <= end_date:
        # 1. Open lots as of curr_date
        total_curr_val = 0.0
        total_cost_basis = 0.0

        for lot in account_lots:
            if lot.buy_date <= curr_date:
                # Sum sales of this lot on or before curr_date
                sold_qty = sum(q for sdate, q, _ in sales_map.get(lot.lot_id, []) if sdate <= curr_date)
                rem_qty = max(0.0, lot.quantity_original - sold_qty)
                if rem_qty > 0.00000001:
                    p_list = [p for pdate, p in prices_map.get(lot.asset_id, []) if pdate <= curr_date and p is not None and not math.isnan(p) and p > 0]
                    price = p_list[-1] if p_list else lot.cost_per_unit
                    if price is None or (isinstance(price, float) and (math.isnan(price) or math.isinf(price) or price <= 0)):
                        price = lot.cost_per_unit
                    total_curr_val += rem_qty * price
                    total_cost_basis += rem_qty * lot.cost_per_unit

        # 2. Realized PnL as of curr_date
        total_rpnl = sum(
            sum(rpnl for sdate, _, rpnl in sales_list if sdate <= curr_date)
            for sales_list in sales_map.values()
        )

        # 3. Cash balance and total invested as of curr_date
        cash_balance = 0.0
        total_invested = 0.0

        for tx in all_txs:
            if tx.transaction_date <= curr_date:
                ttype = tx.transaction_type.lower()
                if ttype == "deposit":
                    cash_balance += tx.total_amount
                    total_invested += tx.total_amount
                elif ttype == "withdrawal":
                    cash_balance -= tx.total_amount
                    total_invested -= tx.total_amount
                elif ttype == "buy":
                    cash_balance -= (tx.total_amount + tx.fees + tx.taxes)
                elif ttype == "sell":
                    cash_balance += (tx.total_amount - tx.fees - tx.taxes)
                elif ttype == "dividend":
                    cash_balance += tx.total_amount

        net_worth = total_curr_val + max(0.0, cash_balance)
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

