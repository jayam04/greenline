import datetime
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.models import (
    NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory, 
    LotSale, Transaction, Asset, Account
)

async def generate_daily_snapshot(db: AsyncSession, snapshot_date: datetime.date = None) -> NetworthSnapshot:
    if snapshot_date is None:
        snapshot_date = datetime.date.today()

    # 1. Fetch all open lots (quantity_remaining > 0)
    lot_stmt = select(Lot).where(Lot.quantity_remaining > 0)
    lot_res = await db.execute(lot_stmt)
    open_lots: List[Lot] = lot_res.scalars().all()

    # 2. Fetch latest prices for assets
    asset_ids = list({lot.asset_id for lot in open_lots})
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
            # Fallback to cost_per_unit if no market price found
            p_stmt_cost = select(Lot.cost_per_unit).where(Lot.asset_id == aid).limit(1)
            p_res_cost = await db.execute(p_stmt_cost)
            price = p_res_cost.scalar_one_or_none() or 0.0
        latest_prices[aid] = price

    # Fetch assets to get asset_type for classification
    asset_map: Dict[int, Asset] = {}
    if asset_ids:
        a_stmt = select(Asset).where(Asset.asset_id.in_(asset_ids))
        a_res = await db.execute(a_stmt)
        for asset in a_res.scalars().all():
            asset_map[asset.asset_id] = asset

    # 3. Calculate portfolio values
    total_current_value = 0.0
    total_cost_of_open_lots = 0.0
    allocation_by_class: Dict[str, float] = {}

    for lot in open_lots:
        price = latest_prices.get(lot.asset_id, lot.cost_per_unit)
        lot_val = lot.quantity_remaining * price
        total_current_value += lot_val
        total_cost_of_open_lots += lot.quantity_remaining * lot.cost_per_unit
        
        asset = asset_map.get(lot.asset_id)
        aclass = asset.asset_type.lower() if asset else "other"
        allocation_by_class[aclass] = allocation_by_class.get(aclass, 0.0) + lot_val

    total_unrealized_pnl = total_current_value - total_cost_of_open_lots

    # 4. Total Realized PnL
    realized_stmt = select(func.sum(LotSale.realized_pnl))
    realized_res = await db.execute(realized_stmt)
    total_realized_pnl = realized_res.scalar_one_or_none() or 0.0

    # 5. Cash balance calculation from cash transactions
    # Deposits + Sells + Dividends - Buys - Withdrawals - Fees - Taxes
    tx_stmt = select(Transaction)
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

    # Check existing snapshot for today to overwrite or insert
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
