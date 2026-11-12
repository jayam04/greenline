import datetime
import math
import bisect
from typing import Dict, List, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc, or_, delete
from sqlalchemy.orm import selectinload

try:
    from ..db.models import (
        NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory,
        LotSale, Transaction, Asset, Account, CashflowTransaction,
        CashflowPayment, CashflowItem
    )
    from .cashflow_engine import resolve_transaction_kind, compute_transaction_cash_movement, convert_currency, FX_RATES_TO_EUR
except (ImportError, ValueError):
    from app.db.models import (
        NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory,
        LotSale, Transaction, Asset, Account, CashflowTransaction,
        CashflowPayment, CashflowItem
    )
    from app.services.cashflow_engine import resolve_transaction_kind, compute_transaction_cash_movement, convert_currency, FX_RATES_TO_EUR


def to_eur(amount: float, curr: str) -> float:
    rate = FX_RATES_TO_EUR.get((curr or "EUR").strip().upper(), 1.0)
    return amount * rate


def get_next_sunday(d: datetime.date) -> datetime.date:
    """Computes the closest calendar Sunday on or after date d."""
    days_to_sunday = (6 - d.weekday()) % 7
    return d + datetime.timedelta(days=days_to_sunday)


async def generate_daily_snapshot(
    db: AsyncSession, 
    snapshot_date: Optional[datetime.date] = None, 
    user_id: int = 0
) -> NetworthSnapshot:
    """Generates snapshot as of snapshot_date for user_id."""
    if snapshot_date is None:
        snapshot_date = datetime.date.today()

    lot_stmt = select(Lot).where(Lot.user_id == user_id, Lot.buy_date <= snapshot_date)
    all_lots: List[Lot] = list((await db.execute(lot_stmt)).scalars().all())

    lot_ids = [l.lot_id for l in all_lots]
    sales_by_lot: Dict[int, float] = {}
    if lot_ids:
        sales_stmt = (
            select(LotSale.lot_id, func.sum(LotSale.quantity_sold))
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(
                LotSale.user_id == user_id,
                LotSale.lot_id.in_(lot_ids),
                Transaction.transaction_date <= snapshot_date
            )
            .group_by(LotSale.lot_id)
        )
        sales_res = await db.execute(sales_stmt)
        sales_by_lot = {lid: (qty or 0.0) for lid, qty in sales_res.all()}

    open_lots_as_of_date: List[Dict] = []
    asset_ids = set()

    for lot in all_lots:
        sold_qty = sales_by_lot.get(lot.lot_id, 0.0)
        rem_qty = max(0.0, lot.quantity_original - sold_qty)
        if rem_qty > 0.00000001:
            open_lots_as_of_date.append({
                "lot": lot,
                "remaining_quantity": rem_qty
            })
            asset_ids.add(lot.asset_id)

    price_map: Dict[int, float] = {}
    if asset_ids:
        latest_date_subq = (
            select(PriceHistory.asset_id, func.max(PriceHistory.price_date).label("max_date"))
            .where(
                PriceHistory.asset_id.in_(asset_ids),
                PriceHistory.price_date <= snapshot_date
            )
            .group_by(PriceHistory.asset_id)
            .subquery()
        )
        ph_stmt = (
            select(PriceHistory.asset_id, PriceHistory.close_price)
            .join(
                latest_date_subq,
                (PriceHistory.asset_id == latest_date_subq.c.asset_id) &
                (PriceHistory.price_date == latest_date_subq.c.max_date)
            )
        )
        ph_res = await db.execute(ph_stmt)
        for aid, close_px in ph_res.all():
            if close_px is not None and not math.isnan(close_px) and not math.isinf(close_px) and close_px > 0:
                price_map[aid] = float(close_px)

    total_current_value = 0.0
    total_cost_of_open_lots = 0.0
    allocation_by_class: Dict[str, float] = {}

    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        assets_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        assets_map = {a.asset_id: a for a in assets_res.scalars().all()}

    for item in open_lots_as_of_date:
        lot = item["lot"]
        rem_qty = item["remaining_quantity"]
        price = price_map.get(lot.asset_id, float(lot.cost_per_unit or 0.0))
        val = rem_qty * price
        cost = rem_qty * float(lot.cost_per_unit or 0.0)
        total_current_value += val
        total_cost_of_open_lots += cost

        asset = assets_map.get(lot.asset_id)
        aclass = asset.asset_type if asset else "stock"
        allocation_by_class[aclass] = allocation_by_class.get(aclass, 0.0) + val

    total_unrealized_pnl = total_current_value - total_cost_of_open_lots

    # Realized PnL
    rpnl_stmt = (
        select(func.sum(LotSale.realized_pnl))
        .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
        .where(
            LotSale.user_id == user_id,
            Transaction.transaction_date <= snapshot_date
        )
    )
    total_realized_pnl = float((await db.execute(rpnl_stmt)).scalar_one_or_none() or 0.0)

    # Cash balance & invested
    acc_res = await db.execute(select(Account).where(Account.user_id == user_id))
    valid_acc_ids = {a.account_id for a in acc_res.scalars().all()}
    tx_stmt = select(Transaction).where(Transaction.user_id == user_id, Transaction.transaction_date <= snapshot_date)
    all_txs = list((await db.execute(tx_stmt)).scalars().all())

    cash_balance = 0.0
    total_invested = 0.0
    for tx in all_txs:
        _, delta = compute_transaction_cash_movement(tx, valid_acc_ids)
        cash_balance += delta
        ttype = (tx.transaction_type or "").lower()
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)
        if ttype == "deposit":
            total_invested += (amt - fees - taxes)
        elif ttype == "withdrawal":
            total_invested -= (amt + fees + taxes)

    # Cashflow payments
    cf_stmt = (
        select(CashflowPayment.amount, CashflowTransaction.transaction_kind)
        .join(CashflowTransaction, CashflowPayment.cashflow_id == CashflowTransaction.cashflow_id)
        .where(CashflowPayment.user_id == user_id, CashflowTransaction.transaction_date <= snapshot_date)
    )
    for amt, tkind in (await db.execute(cf_stmt)).all():
        signed_amt = float(amt or 0.0)
        cash_balance += signed_amt
        if signed_amt > 0 and tkind == "INCOME":
            total_invested += signed_amt

    if cash_balance > 0:
        allocation_by_class["cash"] = cash_balance

    net_worth = total_current_value + cash_balance

    # Upsert
    snap_stmt = (
        select(NetworthSnapshot)
        .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
        .where(
            NetworthSnapshot.user_id == user_id,
            NetworthSnapshot.snapshot_date == snapshot_date
        )
    )
    snap = (await db.execute(snap_stmt)).scalar_one_or_none()
    if snap:
        snap.total_invested = total_invested
        snap.total_current_value = total_current_value
        snap.cash_balance = cash_balance
        snap.total_realized_pnl = total_realized_pnl
        snap.total_unrealized_pnl = total_unrealized_pnl
        snap.net_worth = net_worth
        snap.asset_class_breakdowns = [
            NetworthByAssetClass(user_id=user_id, asset_class=k, value=v)
            for k, v in allocation_by_class.items()
        ]
    else:
        snap = NetworthSnapshot(
            user_id=user_id,
            snapshot_date=snapshot_date,
            total_invested=total_invested,
            total_current_value=total_current_value,
            cash_balance=cash_balance,
            total_realized_pnl=total_realized_pnl,
            total_unrealized_pnl=total_unrealized_pnl,
            net_worth=net_worth
        )
        snap.asset_class_breakdowns = [
            NetworthByAssetClass(user_id=user_id, asset_class=k, value=v)
            for k, v in allocation_by_class.items()
        ]
        db.add(snap)

    await db.commit()
    await db.refresh(snap)
    return snap


async def recalculate_past_snapshots(
    db: AsyncSession, 
    start_date: datetime.date, 
    end_date: Optional[datetime.date] = None, 
    user_id: int = 0
) -> int:
    """
    Weekly end-of-Sunday snapshot engine:
    Materializes snapshots strictly on calendar Sundays (curr_date.weekday() == 6),
    delivering 85.7% payload reduction and 7x speedup compared to daily stepping.
    """
    # 1. Determine end_date: if None, find latest activity/price date
    if end_date is None:
        latest_date_candidates = []
        max_tx = (await db.execute(
            select(func.max(Transaction.transaction_date)).where(Transaction.user_id == user_id)
        )).scalar_one_or_none()
        if max_tx:
            latest_date_candidates.append(max_tx)

        max_cf = (await db.execute(
            select(func.max(CashflowTransaction.transaction_date)).where(CashflowTransaction.user_id == user_id)
        )).scalar_one_or_none()
        if max_cf:
            latest_date_candidates.append(max_cf)

        max_ph = (await db.execute(
            select(func.max(PriceHistory.price_date))
            .join(Lot, PriceHistory.asset_id == Lot.asset_id)
            .where(Lot.user_id == user_id)
        )).scalar_one_or_none()
        if max_ph:
            latest_date_candidates.append(max_ph)

        if latest_date_candidates:
            max_user_date = max(latest_date_candidates)
            end_date = get_next_sunday(max_user_date)
        else:
            end_date = get_next_sunday(start_date)

    if start_date > end_date:
        start_date = end_date

    # 2. Pre-fetch all lots up to end_date for user
    lot_stmt = select(Lot).where(Lot.user_id == user_id, Lot.buy_date <= end_date)
    all_lots = list((await db.execute(lot_stmt)).scalars().all())

    # 3. Pre-fetch all lot sales up to end_date for user
    sale_stmt = (
        select(LotSale.lot_id, Transaction.transaction_date, LotSale.quantity_sold, LotSale.realized_pnl)
        .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
        .where(
            LotSale.user_id == user_id,
            Transaction.user_id == user_id,
            Transaction.transaction_date <= end_date
        )
    )
    all_sales = (await db.execute(sale_stmt)).all()
    sales_by_lot: Dict[int, List[Tuple[datetime.date, float]]] = {}
    realized_sales: List[Tuple[datetime.date, float]] = []
    for lid, sdate, qsold, rpnl in all_sales:
        sales_by_lot.setdefault(lid, []).append((sdate, float(qsold or 0.0)))
        realized_sales.append((sdate, float(rpnl or 0.0)))

    # 4. Pre-fetch relevant assets
    asset_ids = list(set(l.asset_id for l in all_lots))
    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        assets_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        assets_map = {a.asset_id: a for a in assets_res.scalars().all()}

    # 5. Pre-fetch prices
    prices_by_asset: Dict[int, List[Tuple[datetime.date, float]]] = {}
    if asset_ids:
        ph_stmt = (
            select(PriceHistory.asset_id, PriceHistory.price_date, PriceHistory.close_price)
            .where(
                PriceHistory.asset_id.in_(asset_ids),
                PriceHistory.price_date <= end_date
            )
            .order_by(asc(PriceHistory.price_date))
        )
        for aid, pdate, cprice in (await db.execute(ph_stmt)).all():
            if cprice is not None and not math.isnan(cprice) and not math.isinf(cprice) and cprice > 0:
                prices_by_asset.setdefault(aid, []).append((pdate, float(cprice)))

    # 6. Pre-fetch transactions cash movements
    acc_res = await db.execute(select(Account).where(Account.user_id == user_id))
    valid_acc_ids = {a.account_id for a in acc_res.scalars().all()}
    tx_stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.transaction_date <= end_date)
        .order_by(asc(Transaction.transaction_date))
    )
    all_txs = list((await db.execute(tx_stmt)).scalars().all())
    tx_events: List[Tuple[datetime.date, float, float]] = []
    for tx in all_txs:
        _, delta = compute_transaction_cash_movement(tx, valid_acc_ids)
        ttype = (tx.transaction_type or "").lower()
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)
        inv_delta = 0.0
        if ttype == "deposit":
            inv_delta = amt - fees - taxes
        elif ttype == "withdrawal":
            inv_delta = -(amt + fees + taxes)
        tx_events.append((tx.transaction_date, delta, inv_delta))

    # 7. Pre-fetch cashflow payments
    cf_stmt = (
        select(CashflowPayment.amount, CashflowTransaction.transaction_date, CashflowTransaction.transaction_kind)
        .join(CashflowTransaction, CashflowPayment.cashflow_id == CashflowTransaction.cashflow_id)
        .where(CashflowPayment.user_id == user_id, CashflowTransaction.transaction_date <= end_date)
        .order_by(asc(CashflowTransaction.transaction_date))
    )
    cf_events: List[Tuple[datetime.date, float, bool]] = []
    for amt, cdate, tkind in (await db.execute(cf_stmt)).all():
        signed_amt = float(amt or 0.0)
        is_income = signed_amt > 0 and tkind == "INCOME"
        cf_events.append((cdate, signed_amt, is_income))

    # 8. Fetch existing snapshots to update in-place
    existing_snaps: Dict[datetime.date, NetworthSnapshot] = {
        s.snapshot_date: s
        for s in (
            await db.execute(
                select(NetworthSnapshot)
                .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
                .where(
                    NetworthSnapshot.user_id == user_id,
                    NetworthSnapshot.snapshot_date >= start_date,
                    NetworthSnapshot.snapshot_date <= end_date
                )
            )
        ).scalars().all()
    }

    # 9. Step strictly on calendar Sundays (curr_date.weekday() == 6)
    curr_date = get_next_sunday(start_date)
    count = 0

    while curr_date <= end_date:
        total_curr_val = 0.0
        total_cost_of_open_lots = 0.0
        allocation_by_class: Dict[str, float] = {}

        for lot in all_lots:
            if lot.buy_date <= curr_date:
                sold_qty = sum(q for sdate, q in sales_by_lot.get(lot.lot_id, []) if sdate <= curr_date)
                rem_qty = max(0.0, lot.quantity_original - sold_qty)
                if rem_qty > 0.00000001:
                    p_list = [p for pdate, p in prices_by_asset.get(lot.asset_id, []) if pdate <= curr_date]
                    price = p_list[-1] if p_list else lot.cost_per_unit
                    if price is None or (isinstance(price, float) and (math.isnan(price) or math.isinf(price) or price <= 0)):
                        price = lot.cost_per_unit

                    val = rem_qty * price
                    cost = rem_qty * lot.cost_per_unit
                    total_curr_val += val
                    total_cost_of_open_lots += cost

                    asset = assets_map.get(lot.asset_id)
                    aclass = asset.asset_type if asset else "stock"
                    allocation_by_class[aclass] = allocation_by_class.get(aclass, 0.0) + val

        total_unrealized_pnl = total_curr_val - total_cost_of_open_lots
        total_realized_pnl = sum(rpnl for sdate, rpnl in realized_sales if sdate <= curr_date)

        cash_balance = sum(dc for dt, dc, _ in tx_events if dt <= curr_date)
        total_invested = sum(di for dt, _, di in tx_events if dt <= curr_date)

        for cdate, amt, is_inc in cf_events:
            if cdate <= curr_date:
                cash_balance += amt
                if is_inc:
                    total_invested += amt

        if cash_balance > 0:
            allocation_by_class["cash"] = cash_balance

        net_worth = total_curr_val + cash_balance

        if curr_date in existing_snaps:
            snap = existing_snaps[curr_date]
            snap.total_invested = total_invested
            snap.total_current_value = total_curr_val
            snap.cash_balance = cash_balance
            snap.total_realized_pnl = total_realized_pnl
            snap.total_unrealized_pnl = total_unrealized_pnl
            snap.net_worth = net_worth
            snap.asset_class_breakdowns = [
                NetworthByAssetClass(user_id=user_id, asset_class=k, value=v)
                for k, v in allocation_by_class.items()
            ]
        else:
            snap = NetworthSnapshot(
                user_id=user_id,
                snapshot_date=curr_date,
                total_invested=total_invested,
                total_current_value=total_curr_val,
                cash_balance=cash_balance,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=total_unrealized_pnl,
                net_worth=net_worth
            )
            snap.asset_class_breakdowns = [
                NetworthByAssetClass(user_id=user_id, asset_class=k, value=v)
                for k, v in allocation_by_class.items()
            ]
            db.add(snap)
            existing_snaps[curr_date] = snap

        count += 1
        curr_date += datetime.timedelta(days=7)

    await db.flush()
    await db.commit()
    return count


async def calculate_account_snapshots(
    db: AsyncSession,
    account_id: int,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None
) -> List[Dict]:
    """
    Computes weekly Sunday timeline data points for a specific account.
    Steps strictly on calendar Sundays (weekday == 6).
    """
    # 1. Fetch account
    acc_res = await db.execute(select(Account).where(Account.account_id == account_id))
    acc = acc_res.scalar_one_or_none()
    if not acc:
        return []

    # 2. Determine start_date if omitted
    min_tx_stmt = select(func.min(Transaction.transaction_date)).where(
        or_(Transaction.account_id == account_id, Transaction.funding_account_id == account_id)
    )
    min_tx = (await db.execute(min_tx_stmt)).scalar_one_or_none()

    min_cf_stmt = (
        select(func.min(CashflowTransaction.transaction_date))
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
        .where(CashflowPayment.account_id == account_id)
    )
    min_cf = (await db.execute(min_cf_stmt)).scalar_one_or_none()

    valid_dates = [d for d in [min_tx, min_cf] if d is not None]
    if start_date is None:
        if not valid_dates:
            acc_created = acc.created_at
            if acc_created:
                start_date = acc_created
            else:
                return []
        else:
            start_date = min(valid_dates)

    # 3. Determine end_date if omitted
    if end_date is None:
        max_tx = (await db.execute(
            select(func.max(Transaction.transaction_date)).where(
                or_(Transaction.account_id == account_id, Transaction.funding_account_id == account_id)
            )
        )).scalar_one_or_none()

        max_cf = (await db.execute(
            select(func.max(CashflowTransaction.transaction_date))
            .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
            .where(CashflowPayment.account_id == account_id)
        )).scalar_one_or_none()

        max_dates = [d for d in [max_tx, max_cf] if d is not None]
        if max_dates:
            end_date = get_next_sunday(max(max_dates))
        else:
            end_date = get_next_sunday(start_date)

    if start_date > end_date:
        return []

    # 4. Fetch lots for this account
    lot_stmt = select(Lot).where(Lot.account_id == account_id)
    account_lots: List[Lot] = list((await db.execute(lot_stmt)).scalars().all())
    lot_ids = [l.lot_id for l in account_lots]

    # Fetch lot sales
    sales_map: Dict[int, List[Tuple[datetime.date, float, float]]] = {}
    if lot_ids:
        sale_stmt = (
            select(LotSale.lot_id, Transaction.transaction_date, LotSale.quantity_sold, LotSale.realized_pnl)
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(LotSale.lot_id.in_(lot_ids))
        )
        for lid, sdate, qsold, rpnl in (await db.execute(sale_stmt)).all():
            sales_map.setdefault(lid, []).append((sdate, float(qsold or 0.0), float(rpnl or 0.0)))

    # Fetch price histories for assets in this account
    asset_ids = list(set(l.asset_id for l in account_lots))
    prices_map: Dict[int, List[Tuple[datetime.date, float]]] = {}
    if asset_ids:
        ph_stmt = (
            select(PriceHistory.asset_id, PriceHistory.price_date, PriceHistory.close_price)
            .where(PriceHistory.asset_id.in_(asset_ids))
            .order_by(asc(PriceHistory.price_date))
        )
        for aid, pdate, cprice in (await db.execute(ph_stmt)).all():
            if cprice is not None and not math.isnan(cprice) and not math.isinf(cprice) and cprice > 0:
                prices_map.setdefault(aid, []).append((pdate, float(cprice)))

    # Fetch transactions
    tx_stmt = (
        select(Transaction)
        .where(or_(Transaction.account_id == account_id, Transaction.funding_account_id == account_id))
        .order_by(asc(Transaction.transaction_date))
    )
    all_txs: List[Transaction] = list((await db.execute(tx_stmt)).scalars().all())

    # Fetch cashflow payments
    cf_stmt = (
        select(CashflowTransaction, CashflowPayment)
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
        .where(CashflowPayment.account_id == account_id)
        .order_by(asc(CashflowTransaction.transaction_date))
    )
    cf_records = (await db.execute(cf_stmt)).all()
    cf_events = []
    for ctx, pmt in cf_records:
        tkind = resolve_transaction_kind(ctx)
        signed_amt = float(pmt.amount or 0.0)
        is_income = signed_amt > 0 and tkind == "INCOME"
        cf_events.append((ctx.transaction_date, signed_amt, is_income))

    # 5. Iterate strictly on calendar Sundays
    snapshots_list = []
    curr_date = get_next_sunday(start_date)

    while curr_date <= end_date:
        total_curr_val = 0.0
        total_cost_basis = 0.0

        for lot in account_lots:
            if lot.buy_date <= curr_date:
                sold_qty = sum(q for sdate, q, _ in sales_map.get(lot.lot_id, []) if sdate <= curr_date)
                rem_qty = max(0.0, lot.quantity_original - sold_qty)
                if rem_qty > 0.00000001:
                    p_list = [p for pdate, p in prices_map.get(lot.asset_id, []) if pdate <= curr_date]
                    price = p_list[-1] if p_list else lot.cost_per_unit
                    if price is None or (isinstance(price, float) and (math.isnan(price) or math.isinf(price) or price <= 0)):
                        price = lot.cost_per_unit
                    total_curr_val += rem_qty * price
                    total_cost_basis += rem_qty * lot.cost_per_unit

        total_rpnl = sum(
            sum(rpnl for sdate, _, rpnl in sales_list if sdate <= curr_date)
            for sales_list in sales_map.values()
        )

        cash_balance = 0.0
        total_invested = 0.0

        for tx in all_txs:
            if tx.transaction_date <= curr_date:
                cash_acc_id, cash_change = compute_transaction_cash_movement(tx)
                if cash_acc_id == account_id:
                    cash_balance += cash_change
                    ttype = (tx.transaction_type or "").lower()
                    amt = float(tx.total_amount or 0.0)
                    fees = float(tx.fees or 0.0)
                    taxes = float(tx.taxes or 0.0)
                    if ttype == "deposit":
                        total_invested += (amt - fees - taxes)
                    elif ttype == "withdrawal":
                        total_invested -= (amt + fees + taxes)

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

        curr_date += datetime.timedelta(days=7)

    return snapshots_list
