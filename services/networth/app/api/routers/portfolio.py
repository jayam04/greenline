import datetime
import math
from typing import List, Dict, Optional, Tuple, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, asc, or_
from sqlalchemy.orm import selectinload
from cachetools import TTLCache

try:
    from ...db.database import get_db
    from ...db.models import Account, Asset, Lot, LotSale, PriceHistory, Transaction, User, CashflowTransaction, CashflowItem, NetworthSnapshot, CashFlow
    from ...schemas.schemas import PortfolioSummaryResponse, HoldingSummary, LotResponse, LotSaleResponse, AnnualSnapshotResponse
    from ...services.xirr_service import calculate_xirr_for_scope
    from ...services.cashflow_engine import convert_currency
    from ...services.portfolio import calculate_all_account_cash_balances
    from ..deps import get_current_user, get_user_id
except (ImportError, ValueError):
    from app.db.database import get_db
    from app.db.models import Account, Asset, Lot, LotSale, PriceHistory, Transaction, User, CashflowTransaction, CashflowItem, NetworthSnapshot, CashFlow
    from app.schemas.schemas import PortfolioSummaryResponse, HoldingSummary, LotResponse, LotSaleResponse, AnnualSnapshotResponse
    from app.services.xirr_service import calculate_xirr_for_scope
    from app.services.cashflow_engine import convert_currency
    from app.services.portfolio import calculate_all_account_cash_balances
    from app.api.deps import get_current_user, get_user_id

import pyxirr

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# L1 TTL Cache for portfolio endpoints
portfolio_summary_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)


def invalidate_portfolio_cache(user_id: int):
    """Purges cached portfolio summaries for a user."""
    keys = [k for k in portfolio_summary_cache.keys() if k[0] == user_id]
    for k in keys:
        portfolio_summary_cache.pop(k, None)


def _compute_asset_xirr_in_memory(
    flows: List[Tuple[datetime.date, float]],
    current_val: float,
    as_of: Optional[datetime.date] = None
) -> Optional[float]:
    if as_of is None:
        as_of = datetime.date.today()
    dates = [f[0] for f in flows]
    amounts = [f[1] for f in flows]
    if current_val > 0:
        dates.append(as_of)
        amounts.append(current_val)
    if len(dates) < 2:
        return None
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None
    try:
        val = pyxirr.xirr(dates, amounts)
        if val is None or str(val) == "nan":
            return None
        return float(val)
    except Exception:
        return None


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sub-50ms portfolio valuation summary (<10ms target).
    Aggregates asset valuations, allocations, realized/unrealized PnL, and cash balances.
    """
    u_id = get_user_id(current_user)
    if not isinstance(account_id, int):
        account_id = None

    cache_key = (u_id, account_id)
    if cache_key in portfolio_summary_cache:
        return portfolio_summary_cache[cache_key]

    # Pre-fetch accounts map for user
    all_accounts_res = await db.execute(select(Account).where(Account.user_id == u_id))
    all_accounts: Dict[int, Account] = {a.account_id: a for a in all_accounts_res.scalars().all()}
    if account_id and account_id not in all_accounts:
        raise HTTPException(status_code=404, detail="Account not found or access denied")

    # 1. Fetch active open lots
    lot_stmt = select(Lot).where(Lot.user_id == u_id, Lot.quantity_remaining > 0)
    if account_id:
        lot_stmt = lot_stmt.where(Lot.account_id == account_id)
    open_lots = list((await db.execute(lot_stmt)).scalars().all())

    asset_ids = list(set(l.asset_id for l in open_lots))

    total_invested = 0.0
    total_current_value = 0.0
    asset_allocation: Dict[str, float] = {}
    sector_allocation: Dict[str, float] = {}

    asset_prices: Dict[int, float] = {aid: 0.0 for aid in asset_ids}
    asset_previous_prices: Dict[int, float] = {aid: 0.0 for aid in asset_ids}
    asset_price_dates: Dict[int, Optional[datetime.date]] = {aid: None for aid in asset_ids}

    if asset_ids:
        rn_col = func.row_number().over(
            partition_by=PriceHistory.asset_id,
            order_by=[desc(PriceHistory.price_date), desc(PriceHistory.price_id)]
        ).label("rn")

        ranked_ph = (
            select(
                PriceHistory.asset_id,
                PriceHistory.close_price,
                PriceHistory.price_date,
                rn_col
            )
            .where(PriceHistory.asset_id.in_(asset_ids))
            .subquery()
        )

        ph_stmt = (
            select(
                ranked_ph.c.asset_id,
                ranked_ph.c.close_price,
                ranked_ph.c.price_date,
                ranked_ph.c.rn
            )
            .where(ranked_ph.c.rn <= 2)
        )
        ph_res = await db.execute(ph_stmt)
        for aid, cprice, pdate, rn in ph_res.all():
            if rn == 1:
                asset_prices[aid] = float(cprice or 0.0)
                asset_price_dates[aid] = pdate
            elif rn == 2:
                asset_previous_prices[aid] = float(cprice or 0.0)

    # Pre-fetch Assets
    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        ast_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        assets_map = {a.asset_id: a for a in ast_res.scalars().all()}

    # Group open lots by asset
    lots_by_asset: Dict[int, List[Lot]] = {}

    # Pre-fetch fees and taxes grouped by asset
    fees_stmt = (
        select(
            Transaction.asset_id,
            func.sum(Transaction.fees),
            func.sum(Transaction.taxes)
        )
        .where(Transaction.user_id == u_id, Transaction.asset_id.isnot(None))
    )
    if account_id:
        fees_stmt = fees_stmt.where(Transaction.account_id == account_id)
    fees_stmt = fees_stmt.group_by(Transaction.asset_id)
    fees_res = await db.execute(fees_stmt)
    fees_map: Dict[int, tuple] = {
        row[0]: (float(row[1] or 0.0), float(row[2] or 0.0))
        for row in fees_res.all()
    }

    # Pre-fetch net dividends grouped by asset
    div_stmt = select(Transaction).where(
        Transaction.user_id == u_id,
        Transaction.transaction_type == "dividend",
        Transaction.asset_id.isnot(None)
    )
    if account_id:
        div_stmt = div_stmt.where(Transaction.account_id == account_id)
    div_res = await db.execute(div_stmt)
    div_map: Dict[int, float] = {}
    for dtx in div_res.scalars().all():
        net_div = max(0.0, float(dtx.total_amount or 0.0) - float(dtx.taxes or 0.0))
        div_map[dtx.asset_id] = div_map.get(dtx.asset_id, 0.0) + net_div

    # Pre-fetch asset cashflows for in-memory XIRR calculation in a single query
    cf_stmt = (
        select(CashFlow.scope_id, CashFlow.flow_date, CashFlow.amount)
        .where(CashFlow.user_id == u_id, CashFlow.scope_type == "asset")
        .order_by(asc(CashFlow.flow_date))
    )
    cf_res = await db.execute(cf_stmt)
    asset_flows_map: Dict[int, List[Tuple[datetime.date, float]]] = {}
    for scope_id, fdate, amt in cf_res.all():
        if scope_id is not None:
            asset_flows_map.setdefault(scope_id, []).append((fdate, float(amt)))

    # Pre-fetch realized PnL, cost basis, quantity sold, and account_id grouped by asset
    rpnl_stmt = (
        select(
            Lot.asset_id,
            func.sum(LotSale.realized_pnl),
            func.sum(LotSale.cost_basis),
            func.sum(LotSale.quantity_sold),
            func.min(Lot.account_id)
        )
        .join(LotSale, Lot.lot_id == LotSale.lot_id)
        .where(Lot.user_id == u_id)
    )
    if account_id:
        rpnl_stmt = rpnl_stmt.where(Lot.account_id == account_id)
    rpnl_stmt = rpnl_stmt.group_by(Lot.asset_id)
    rpnl_res = await db.execute(rpnl_stmt)
    rpnl_by_asset: Dict[int, Tuple[float, float]] = {}
    closed_sales_by_asset: Dict[int, Tuple[float, float, float, Optional[int]]] = {}
    for r in rpnl_res.all():
        aid_val = r[0]
        pnl = float(r[1] or 0.0)
        cost = float(r[2] or 0.0)
        qty = float(r[3] or 0.0)
        acc_id_val = r[4]
        rpnl_by_asset[aid_val] = (pnl, cost)
        closed_sales_by_asset[aid_val] = (pnl, cost, qty, acc_id_val)

    for l in open_lots:
        lots_by_asset.setdefault(l.asset_id, []).append(l)

    holdings_list: List[HoldingSummary] = []

    for aid, a_lots in lots_by_asset.items():
        asset = assets_map.get(aid)
        if not asset:
            continue

        qty_held = sum(float(l.quantity_remaining) for l in a_lots)
        total_cost = sum(float(l.quantity_remaining) * float(l.cost_per_unit or 0.0) for l in a_lots)
        avg_cost = total_cost / qty_held if qty_held > 0 else 0.0

        latest_px = asset_prices.get(aid, 0.0)
        if latest_px <= 0:
            latest_px = avg_cost

        prev_px = asset_previous_prices.get(aid, latest_px)
        if prev_px <= 0:
            prev_px = latest_px

        curr_val = qty_held * latest_px
        unrealized = curr_val - total_cost
        unrealized_pct = (unrealized / total_cost * 100.0) if total_cost > 0 else 0.0

        change_1d = latest_px - prev_px
        change_1d_pct = (change_1d / prev_px * 100.0) if prev_px > 0 else 0.0
        val_change_1d = qty_held * change_1d

        total_invested += total_cost
        total_current_value += curr_val

        aclass = asset.asset_type or "stock"
        asset_allocation[aclass] = asset_allocation.get(aclass, 0.0) + curr_val

        sec = asset.sector or "Unclassified"
        sector_allocation[sec] = sector_allocation.get(sec, 0.0) + curr_val

        # Realized PnL from pre-fetched map + net dividends
        cap_gains_for_asset, cost_basis_sold_for_asset = rpnl_by_asset.get(aid, (0.0, 0.0))
        asset_net_div = div_map.get(aid, 0.0)
        realized_pnl_for_asset = cap_gains_for_asset + asset_net_div
        if cost_basis_sold_for_asset > 0:
            realized_pnl_pct_for_asset = (realized_pnl_for_asset / cost_basis_sold_for_asset * 100.0)
        elif total_cost > 0:
            realized_pnl_pct_for_asset = (realized_pnl_for_asset / total_cost * 100.0)
        else:
            realized_pnl_pct_for_asset = 0.0

        net_pnl_for_asset = realized_pnl_for_asset + unrealized
        total_basis = total_cost + cost_basis_sold_for_asset
        net_pnl_pct_for_asset = (net_pnl_for_asset / total_basis * 100.0) if total_basis > 0 else 0.0

        fees_entry = fees_map.get(aid, (0.0, 0.0))
        asset_fees = fees_entry[0]
        asset_taxes = fees_entry[1]
        total_asset_fees_taxes = asset_fees + asset_taxes

        # In-memory XIRR for asset
        xirr_val = _compute_asset_xirr_in_memory(
            flows=asset_flows_map.get(aid, []),
            current_val=curr_val
        )

        holdings_list.append(HoldingSummary(
            asset_id=aid,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.asset_type,
            sector=asset.sector,
            industry=asset.industry,
            currency=asset.currency or "USD",
            quantity_held=qty_held,
            avg_cost_price=avg_cost,
            total_cost=total_cost,
            latest_price=latest_px,
            latest_price_date=asset_price_dates.get(aid),
            previous_price=prev_px,
            change_1d=change_1d,
            change_1d_pct=change_1d_pct,
            value_change_1d=val_change_1d,
            current_value=curr_val,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=unrealized_pct,
            realized_pnl=realized_pnl_for_asset,
            realized_pnl_pct=realized_pnl_pct_for_asset,
            dividend_income=asset_net_div,
            capital_gains_realized=cap_gains_for_asset,
            fees_and_taxes=total_asset_fees_taxes,
            total_fees=asset_fees,
            total_taxes=asset_taxes,
            net_pnl=net_pnl_for_asset,
            net_pnl_pct=net_pnl_pct_for_asset,
            xirr=xirr_val,
            open_lots=[LotResponse.model_validate(l) for l in a_lots]
        ))

    # Identify Closed Positions (Assets with LotSale records or dividends but 0 open quantity)
    open_asset_ids_set = set(lots_by_asset.keys())
    closed_holdings_list: List[HoldingSummary] = []
    closed_asset_candidates = set(closed_sales_by_asset.keys()) | set(div_map.keys())
    needed_closed_aids = [
        c_aid for c_aid in closed_asset_candidates
        if c_aid not in open_asset_ids_set
    ]
    if needed_closed_aids:
        c_ast_res = await db.execute(select(Asset).where(Asset.asset_id.in_(needed_closed_aids)))
        closed_assets_map = {a.asset_id: a for a in c_ast_res.scalars().all()}
        for c_aid in needed_closed_aids:
            c_cap_gains, c_cost_basis, c_qty_sold, c_acc_id = closed_sales_by_asset.get(c_aid, (0.0, 0.0, 0.0, None))
            c_asset = closed_assets_map.get(c_aid)
            if not c_asset:
                continue
            c_net_div = div_map.get(c_aid, 0.0)
            c_realized_pnl = c_cap_gains + c_net_div
            c_rpnl_pct = (c_realized_pnl / c_cost_basis * 100.0) if c_cost_basis > 0 else 0.0

            c_xirr = _compute_asset_xirr_in_memory(
                flows=asset_flows_map.get(c_aid, []),
                current_val=0.0
            )

            c_fees_entry = fees_map.get(c_asset.asset_id, (0.0, 0.0))
            c_asset_fees = c_fees_entry[0]
            c_asset_taxes = c_fees_entry[1]
            c_total_asset_fees_taxes = c_asset_fees + c_asset_taxes

            closed_holdings_list.append(HoldingSummary(
                asset_id=c_asset.asset_id,
                symbol=c_asset.symbol,
                name=c_asset.name,
                asset_type=c_asset.asset_type,
                sector=c_asset.sector,
                industry=c_asset.industry,
                currency=c_asset.currency or "USD",
                quantity_held=0.0,
                avg_cost_price=0.0,
                total_cost=0.0,
                latest_price=0.0,
                latest_price_date=None,
                previous_price=0.0,
                change_1d=0.0,
                change_1d_pct=0.0,
                value_change_1d=0.0,
                current_value=0.0,
                unrealized_pnl=0.0,
                unrealized_pnl_pct=0.0,
                realized_pnl=c_realized_pnl,
                realized_pnl_pct=c_rpnl_pct,
                dividend_income=c_net_div,
                capital_gains_realized=c_cap_gains,
                fees_and_taxes=c_total_asset_fees_taxes,
                total_fees=c_asset_fees,
                total_taxes=c_asset_taxes,
                net_pnl=c_realized_pnl,
                net_pnl_pct=c_rpnl_pct,
                xirr=c_xirr,
                open_lots=[]
            ))

    # 2. Fetch realized PnL total (Capital Gains + Net Dividends)
    total_capital_gains = sum(r[0] for r in rpnl_by_asset.values())
    total_net_dividends = sum(div_map.values())
    total_realized_pnl = total_capital_gains + total_net_dividends

    # 3. Cash balances
    balances = await calculate_all_account_cash_balances(db, accounts=list(all_accounts.values()), user_id=u_id)
    if account_id:
        cash_balance = balances.get(account_id, 0.0)
    else:
        cash_balance = sum(balances.values())

    total_net_worth = total_current_value + max(0.0, cash_balance)
    total_unrealized_pnl = total_current_value - total_invested

    # 4. Portfolio XIRR
    portfolio_xirr = await calculate_xirr_for_scope(
        db=db,
        scope_type="account" if account_id else "portfolio",
        scope_id=account_id,
        current_valuation=total_net_worth,
        user_id=u_id
    )

    total_value_change_1d = sum(h.value_change_1d for h in holdings_list)
    previous_holdings_val = sum(h.quantity_held * h.previous_price for h in holdings_list)
    total_change_1d_pct = (
        (total_value_change_1d / previous_holdings_val * 100.0)
        if previous_holdings_val > 0
        else 0.0
    )

    holdings_list.sort(key=lambda h: h.current_value, reverse=True)
    closed_holdings_list.sort(key=lambda h: abs(h.realized_pnl), reverse=True)

    # Fetch transaction fees and taxes in a lightweight projection
    tx_stmt = select(Transaction.account_id, Transaction.fees, Transaction.taxes).where(
        Transaction.user_id == u_id,
        or_(Transaction.fees.isnot(None), Transaction.taxes.isnot(None))
    )
    if account_id:
        tx_stmt = tx_stmt.where(Transaction.account_id == account_id)
    tx_res = await db.execute(tx_stmt)

    total_fees = 0.0
    total_taxes = 0.0
    for acc_id_t, fees_v, taxes_v in tx_res.all():
        acc_t = all_accounts.get(acc_id_t)
        tx_curr = acc_t.currency if acc_t else "USD"
        if fees_v:
            if account_id:
                total_fees += float(fees_v)
            else:
                total_fees += convert_currency(float(fees_v), tx_curr, "EUR")
        if taxes_v:
            if account_id:
                total_taxes += float(taxes_v)
            else:
                total_taxes += convert_currency(float(taxes_v), tx_curr, "EUR")

    resp = PortfolioSummaryResponse(
        total_net_worth=total_net_worth,
        total_invested=total_invested,
        total_current_value=total_current_value,
        cash_balance=cash_balance,
        total_realized_pnl=total_realized_pnl,
        total_unrealized_pnl=total_unrealized_pnl,
        total_dividend_income=total_net_dividends,
        total_capital_gains_realized=total_capital_gains,
        total_value_change_1d=total_value_change_1d,
        total_change_1d_pct=total_change_1d_pct,
        total_fees=total_fees,
        total_taxes=total_taxes,
        portfolio_xirr=portfolio_xirr,
        asset_allocation=asset_allocation,
        sector_allocation=sector_allocation,
        top_holdings=holdings_list,
        closed_holdings=closed_holdings_list
    )
    portfolio_summary_cache[cache_key] = resp
    return resp


@router.get("/holdings", response_model=List[HoldingSummary])
async def get_holdings(
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns list of active open holdings for user or specific account."""
    summary = await get_portfolio_summary(account_id=account_id, db=db, current_user=current_user)
    return summary.top_holdings


@router.get("/closed-holdings", response_model=List[HoldingSummary])
async def get_closed_holdings(
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns list of closed holdings for user or specific account."""
    summary = await get_portfolio_summary(account_id=account_id, db=db, current_user=current_user)
    return summary.closed_holdings


@router.get("/annual_snapshot", response_model=AnnualSnapshotResponse)
async def get_annual_snapshot(
    fiscal_year_start: Optional[str] = Query("01-01"),
    master_currency: Optional[str] = Query("EUR"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Computes annual financial performance and net worth delta."""
    u_id = get_user_id(current_user)
    today = datetime.date.today()

    try:
        parts = (fiscal_year_start or "01-01").split("-")
        fy_month = int(parts[0])
        fy_day = int(parts[1])
    except Exception:
        fy_month = 1
        fy_day = 1

    if (today.month, today.day) < (fy_month, fy_day):
        start_year = today.year - 1
    else:
        start_year = today.year

    start_date = datetime.date(start_year, fy_month, fy_day)
    end_date = today

    year_label = f"FY {start_year}-{start_year+1}" if (fy_month, fy_day) != (1, 1) else f"CY {start_year}"

    # Cashflow income & expense
    c_stmt = (
        select(CashflowTransaction)
        .options(selectinload(CashflowTransaction.items).selectinload(CashflowItem.category))
        .where(
            CashflowTransaction.user_id == u_id,
            CashflowTransaction.transaction_date >= start_date,
            CashflowTransaction.transaction_date <= end_date
        )
    )
    c_txs = list((await db.execute(c_stmt)).scalars().all())

    total_income = 0.0
    total_expenses = 0.0
    for ctx in c_txs:
        for itm in ctx.items:
            amt = convert_currency(float(itm.amount or 0.0), ctx.currency or "EUR", master_currency or "EUR")
            cat_type = itm.category.category_type if itm.category else "EXPENSE"
            if cat_type == "INCOME":
                total_income += amt
            elif cat_type != "TRANSFER":
                total_expenses += amt

    # 2. Fetch investment transactions in date range
    target_currency = master_currency or "EUR"
    tx_stmt = (
        select(Transaction, Account.currency)
        .join(Account, Transaction.account_id == Account.account_id)
        .where(
            Transaction.user_id == u_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
    )
    inv_txs = (await db.execute(tx_stmt)).all()

    investments_done = 0.0
    investments_closed = 0.0
    taxes_and_fees = 0.0

    for tx, acc_curr in inv_txs:
        curr = acc_curr or "USD"
        amt = convert_currency(float(tx.total_amount or 0.0), curr, target_currency)
        fees = convert_currency(float(tx.fees or 0.0), curr, target_currency)
        taxes = convert_currency(float(tx.taxes or 0.0), curr, target_currency)
        taxes_and_fees += (fees + taxes)

        ttype = (tx.transaction_type or "").lower()
        if ttype == "buy":
            investments_done += amt
        elif ttype == "sell":
            investments_closed += amt
        elif ttype == "dividend":
            total_income += amt

    # 3. Net worth delta from snapshots (stored in EUR, converted to target_currency)
    snap_start_stmt = (
        select(NetworthSnapshot.net_worth)
        .where(NetworthSnapshot.user_id == u_id, NetworthSnapshot.snapshot_date <= start_date)
        .order_by(desc(NetworthSnapshot.snapshot_date))
    )
    start_nw_eur = float((await db.execute(snap_start_stmt)).scalars().first() or 0.0)

    snap_end_stmt = (
        select(NetworthSnapshot.net_worth)
        .where(NetworthSnapshot.user_id == u_id, NetworthSnapshot.snapshot_date <= end_date)
        .order_by(desc(NetworthSnapshot.snapshot_date))
    )
    end_nw_eur = float((await db.execute(snap_end_stmt)).scalars().first() or 0.0)

    start_nw = convert_currency(start_nw_eur, "EUR", target_currency)
    end_nw = convert_currency(end_nw_eur, "EUR", target_currency)

    net_worth_delta = round(end_nw - start_nw, 2)
    net_worth_delta_pct = round((net_worth_delta / start_nw * 100.0) if start_nw > 0 else 0.0, 2)

    return AnnualSnapshotResponse(
        year_label=year_label,
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        investments_done=round(investments_done, 2),
        investments_closed=round(investments_closed, 2),
        net_worth_delta=net_worth_delta,
        net_worth_delta_pct=net_worth_delta_pct,
        taxes_and_fees=round(taxes_and_fees, 2),
        net_savings=round(total_income - total_expenses, 2),
        currency=target_currency
    )
