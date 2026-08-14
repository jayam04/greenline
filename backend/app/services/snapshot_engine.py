import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
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
        if price is None:
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
