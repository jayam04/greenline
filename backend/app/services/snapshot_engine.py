import datetime
import math
import bisect
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc, or_, delete
from sqlalchemy.orm import selectinload
from app.db.models import (
    NetworthSnapshot, NetworthByAssetClass, Lot, PriceHistory, 
    LotSale, Transaction, Asset, Account, CashflowTransaction, 
    CashflowPayment, CashflowItem
)
from app.services.cashflow_engine import resolve_transaction_kind, compute_transaction_cash_movement

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

    # Calculate remaining lot quantities as of snapshot_date via single batch group-by
    lot_ids = [l.lot_id for l in all_lots]
    sales_by_lot: Dict[int, float] = {}
    if lot_ids:
        sales_stmt = (
            select(LotSale.lot_id, func.sum(LotSale.quantity_sold))
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(
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

    # 2. Fetch closing price for each asset on or closest before snapshot_date via single batch subquery JOIN
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

    # 3. Sum current value and cost of open lots (normalized to EUR)
    total_current_value = 0.0
    total_cost_of_open_lots = 0.0
    allocation_by_class: Dict[str, float] = {}

    assets_stmt = select(Asset).where(Asset.asset_id.in_(asset_ids)) if asset_ids else select(Asset).where(False)
    assets_res = await db.execute(assets_stmt)
    assets_map = {a.asset_id: a for a in assets_res.scalars().all()}

    for item in open_lots_as_of_date:
        lot: Lot = item["lot"]
        rem_qty: float = item["remaining_quantity"]
        p = price_map.get(lot.asset_id, lot.cost_per_unit)
        asset = assets_map.get(lot.asset_id)
        aclass = asset.asset_type if asset else "other"

        val = rem_qty * p
        cost = rem_qty * lot.cost_per_unit

        total_current_value += val
        total_cost_of_open_lots += cost
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
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    accounts_map = {a.account_id: a for a in acc_res.scalars().all()}
    valid_acc_ids = set(accounts_map.keys())

    tx_stmt = select(Transaction).where(Transaction.transaction_date <= snapshot_date)
    tx_res = await db.execute(tx_stmt)
    all_txs: List[Transaction] = tx_res.scalars().all()

    cash_balance = 0.0
    total_invested = 0.0

    for tx in all_txs:
        cash_acc_id, delta = compute_transaction_cash_movement(tx, valid_acc_ids)
        cash_balance += delta

        ttype = (tx.transaction_type or "").lower()
        amt = float(tx.total_amount or 0.0)
        fees = float(tx.fees or 0.0)
        taxes = float(tx.taxes or 0.0)
        if ttype == "deposit":
            total_invested += (amt - fees - taxes)
        elif ttype == "withdrawal":
            total_invested -= (amt + fees + taxes)

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

    # 1. Pre-fetch all lots up to end_date
    lot_stmt = select(Lot).where(Lot.buy_date <= end_date)
    all_lots = list((await db.execute(lot_stmt)).scalars().all())

    # 2. Pre-fetch all lot sales up to end_date
    sale_stmt = (
        select(LotSale.lot_id, Transaction.transaction_date, LotSale.quantity_sold, LotSale.realized_pnl)
        .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
        .where(Transaction.transaction_date <= end_date)
    )
    all_sales = (await db.execute(sale_stmt)).all()
    sales_by_lot: Dict[int, List[Tuple[datetime.date, float]]] = {}
    realized_sales: List[Tuple[datetime.date, float]] = []
    for lid, sdate, qsold, rpnl in all_sales:
        sales_by_lot.setdefault(lid, []).append((sdate, float(qsold or 0.0)))
        realized_sales.append((sdate, float(rpnl or 0.0)))

    # 3. Pre-fetch relevant assets
    asset_ids = list(set(l.asset_id for l in all_lots))
    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        assets_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        assets_map = {a.asset_id: a for a in assets_res.scalars().all()}

    # 4. Pre-fetch prices
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

    # 5. Pre-fetch transactions cash movements
    acc_res = await db.execute(select(Account))
    valid_acc_ids = {a.account_id for a in acc_res.scalars().all()}
    tx_stmt = select(Transaction).where(Transaction.transaction_date <= end_date).order_by(asc(Transaction.transaction_date))
    all_txs = list((await db.execute(tx_stmt)).scalars().all())
    tx_events = []
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

    # 6. Pre-fetch cashflow payments
    cf_stmt = (
        select(
            CashflowTransaction.transaction_date,
            CashflowTransaction.transaction_kind,
            CashflowPayment.account_id,
            CashflowPayment.amount
        )
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
        .where(CashflowTransaction.transaction_date <= end_date)
        .order_by(asc(CashflowTransaction.transaction_date))
    )
    cf_records = (await db.execute(cf_stmt)).all()
    cf_events = []
    for tx_date, tkind, p_acc_id, pmt_amt in cf_records:
        amt = float(pmt_amt or 0.0)
        is_inc = amt > 0 and tkind == "INCOME"
        cf_events.append((tx_date, amt, is_inc))

    # 7. Fetch existing snapshots to update
    existing_snaps = {
        s.snapshot_date: s for s in (
            await db.execute(
                select(NetworthSnapshot)
                .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
                .where(
                    NetworthSnapshot.snapshot_date >= start_date,
                    NetworthSnapshot.snapshot_date <= end_date
                )
            )
        ).scalars().all()
    }

    # 8. Replay day-by-day in RAM
    curr_date = start_date
    delta_day = datetime.timedelta(days=1)
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
                    aclass = asset.asset_type if asset else "other"
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
                NetworthByAssetClass(asset_class=k, value=v)
                for k, v in allocation_by_class.items()
            ]
        else:
            snap = NetworthSnapshot(
                snapshot_date=curr_date,
                total_invested=total_invested,
                total_current_value=total_curr_val,
                cash_balance=cash_balance,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=total_unrealized_pnl,
                net_worth=net_worth
            )
            snap.asset_class_breakdowns = [
                NetworthByAssetClass(asset_class=k, value=v)
                for k, v in allocation_by_class.items()
            ]
            db.add(snap)
            existing_snaps[curr_date] = snap

        count += 1
        curr_date += delta_day

    await db.flush()
    await db.commit()
    return count


async def calculate_all_accounts_snapshots(
    db: AsyncSession,
    end_date: Optional[datetime.date] = None,
    accounts: Optional[List[Account]] = None
) -> Dict[int, Dict[datetime.date, Dict]]:
    """
    Computes daily timeline data points across all accounts in a single batch pass,
    avoiding N+1 queries per account and using bisect search for O(log N) replay.
    """
    if end_date is None:
        end_date = datetime.date.today()

    if accounts is None:
        acc_res = await db.execute(select(Account))
        all_accounts = list(acc_res.scalars().all())
    else:
        all_accounts = accounts

    if not all_accounts:
        return {}

    # 1. Fetch all lots
    lot_res = await db.execute(select(Lot))
    all_lots = list(lot_res.scalars().all())
    lots_by_account: Dict[int, List[Lot]] = {}
    lot_ids = []
    for l in all_lots:
        lots_by_account.setdefault(l.account_id, []).append(l)
        lot_ids.append(l.lot_id)

    # 2. Fetch all sales
    sales_map: Dict[int, List[Tuple[datetime.date, float, float]]] = {}
    if lot_ids:
        sale_stmt = (
            select(LotSale.lot_id, Transaction.transaction_date, LotSale.quantity_sold, LotSale.realized_pnl)
            .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)
            .where(LotSale.lot_id.in_(lot_ids))
        )
        sale_res = await db.execute(sale_stmt)
        for lid, sdate, qsold, rpnl in sale_res.all():
            sales_map.setdefault(lid, []).append((sdate, qsold, rpnl))

    # Pre-process sales for O(log S) cumulative lookup
    lot_sales_cum: Dict[int, Tuple[List[datetime.date], List[float], List[float]]] = {}
    for lid, slist in sales_map.items():
        sorted_s = sorted(slist, key=lambda x: x[0])
        s_d = [x[0] for x in sorted_s]
        c_q: List[float] = []
        c_r: List[float] = []
        cur_q = 0.0
        cur_r = 0.0
        for x in sorted_s:
            cur_q += float(x[1] or 0.0)
            cur_r += float(x[2] or 0.0)
            c_q.append(cur_q)
            c_r.append(cur_r)
        lot_sales_cum[lid] = (s_d, c_q, c_r)

    # 3. Fetch price history
    asset_ids = list(set(l.asset_id for l in all_lots))
    prices_map: Dict[int, List[Tuple[datetime.date, float]]] = {}
    if asset_ids:
        ph_stmt = (
            select(PriceHistory.asset_id, PriceHistory.price_date, PriceHistory.close_price)
            .where(PriceHistory.asset_id.in_(asset_ids))
            .order_by(asc(PriceHistory.price_date))
        )
        ph_res = await db.execute(ph_stmt)
        for aid, pdate, cprice in ph_res.all():
            prices_map.setdefault(aid, []).append((pdate, cprice))

    # Pre-process prices for O(log P) bisect lookup
    parsed_prices: Dict[int, Tuple[List[datetime.date], List[float]]] = {}
    for aid, plist in prices_map.items():
        v_list = [(d, float(p)) for d, p in plist if p is not None and not math.isnan(p) and not math.isinf(p) and p > 0]
        parsed_prices[aid] = ([x[0] for x in v_list], [x[1] for x in v_list])

    # 4. Fetch all transactions
    tx_stmt = select(Transaction).order_by(asc(Transaction.transaction_date))
    all_txs = list((await db.execute(tx_stmt)).scalars().all())

    # 5. Fetch all cashflow payments in a lightweight projection
    cf_stmt = (
        select(
            CashflowTransaction.transaction_date,
            CashflowTransaction.transaction_kind,
            CashflowPayment.account_id,
            CashflowPayment.amount
        )
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
        .order_by(asc(CashflowTransaction.transaction_date))
    )
    cf_records = (await db.execute(cf_stmt)).all()
    cf_events_by_account: Dict[int, List[Tuple[datetime.date, float, bool]]] = {}
    for tx_date, tkind, acc_id, pmt_amt in cf_records:
        signed_amt = float(pmt_amt or 0.0)
        is_income = signed_amt > 0 and tkind == "INCOME"
        cf_events_by_account.setdefault(acc_id, []).append((tx_date, signed_amt, is_income))

    # 6. Compute timeline per account
    account_timelines: Dict[int, Dict[datetime.date, Dict]] = {}

    for acc in all_accounts:
        acc_id = acc.account_id
        acc_lots = lots_by_account.get(acc_id, [])
        acc_cf_events = cf_events_by_account.get(acc_id, [])

        # Precompute cumulative transactions for this account
        acc_tx_events = []
        for tx in all_txs:
            cash_acc_id, cash_change = compute_transaction_cash_movement(tx)
            if cash_acc_id == acc_id:
                ttype = (tx.transaction_type or "").lower()
                amt = float(tx.total_amount or 0.0)
                fees = float(tx.fees or 0.0)
                taxes = float(tx.taxes or 0.0)
                inv_delta = 0.0
                if ttype == "deposit":
                    inv_delta = amt - fees - taxes
                elif ttype == "withdrawal":
                    inv_delta = -(amt + fees + taxes)
                acc_tx_events.append((tx.transaction_date, cash_change, inv_delta))

        acc_tx_events.sort(key=lambda x: x[0])
        tx_dates = [x[0] for x in acc_tx_events]
        cum_tx_cash: List[float] = []
        cum_tx_inv: List[float] = []
        c_cash = 0.0
        c_inv = 0.0
        for x in acc_tx_events:
            c_cash += x[1]
            c_inv += x[2]
            cum_tx_cash.append(c_cash)
            cum_tx_inv.append(c_inv)

        # Precompute cumulative cashflows for this account
        sorted_cf = sorted(acc_cf_events, key=lambda x: x[0])
        cf_dates = [x[0] for x in sorted_cf]
        cum_cf_cash: List[float] = []
        cum_cf_inv: List[float] = []
        c_cf_cash = 0.0
        c_cf_inv = 0.0
        for x in sorted_cf:
            c_cf_cash += x[1]
            if x[2]:
                c_cf_inv += max(0.0, x[1])
            cum_cf_cash.append(c_cf_cash)
            cum_cf_inv.append(c_cf_inv)

        # Find start_date
        all_acc_dates = tx_dates + cf_dates
        if not all_acc_dates:
            start_date = acc.created_at or datetime.date.today()
        else:
            start_date = min(all_acc_dates)

        if start_date > end_date:
            account_timelines[acc_id] = {}
            continue

        curr_date = start_date
        delta = datetime.timedelta(days=1)
        timelines_for_acc: Dict[datetime.date, Dict] = {}

        while curr_date <= end_date:
            t_idx = bisect.bisect_right(tx_dates, curr_date)
            cash_balance = cum_tx_cash[t_idx - 1] if t_idx > 0 else 0.0
            total_invested = cum_tx_inv[t_idx - 1] if t_idx > 0 else 0.0

            cf_idx = bisect.bisect_right(cf_dates, curr_date)
            if cf_idx > 0:
                cash_balance += cum_cf_cash[cf_idx - 1]
                total_invested += cum_cf_inv[cf_idx - 1]

            total_curr_val = 0.0
            total_cost_basis = 0.0
            total_rpnl = 0.0

            for lot in acc_lots:
                if lot.buy_date <= curr_date:
                    lid = lot.lot_id
                    sold_qty = 0.0
                    if lid in lot_sales_cum:
                        s_d, c_q, c_r = lot_sales_cum[lid]
                        s_idx = bisect.bisect_right(s_d, curr_date)
                        if s_idx > 0:
                            sold_qty = c_q[s_idx - 1]
                            total_rpnl += c_r[s_idx - 1]
                    rem_qty = max(0.0, lot.quantity_original - sold_qty)
                    if rem_qty > 0.00000001:
                        aid = lot.asset_id
                        price = lot.cost_per_unit
                        if aid in parsed_prices:
                            p_d, p_v = parsed_prices[aid]
                            p_idx = bisect.bisect_right(p_d, curr_date)
                            if p_idx > 0:
                                price = p_v[p_idx - 1]
                        total_curr_val += rem_qty * price
                        total_cost_basis += rem_qty * lot.cost_per_unit

            net_worth = total_curr_val + cash_balance
            total_unrealized = total_curr_val - total_cost_basis

            timelines_for_acc[curr_date] = {
                "snapshot_id": 0,
                "snapshot_date": curr_date,
                "total_invested": total_invested if total_invested > 0 else total_cost_basis,
                "total_current_value": total_curr_val,
                "cash_balance": cash_balance,
                "total_realized_pnl": total_rpnl,
                "total_unrealized_pnl": total_unrealized,
                "net_worth": net_worth,
                "asset_class_breakdowns": []
            }
            curr_date += delta

        account_timelines[acc_id] = timelines_for_acc

    return account_timelines

    return account_timelines

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
        min_tx_stmt = select(func.min(Transaction.transaction_date)).where(or_(Transaction.account_id == account_id, Transaction.funding_account_id == account_id))
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
    tx_stmt = select(Transaction).where(or_(Transaction.account_id == account_id, Transaction.funding_account_id == account_id)).order_by(asc(Transaction.transaction_date))
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

        curr_date += delta

    return snapshots_list
