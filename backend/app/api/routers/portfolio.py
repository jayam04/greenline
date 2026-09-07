import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import Account, Asset, Lot, LotSale, PriceHistory, Transaction, User, CashflowTransaction, CashflowItem
from app.schemas.schemas import PortfolioSummaryResponse, HoldingSummary, LotResponse, LotSaleResponse, AnnualSnapshotResponse
from app.services.xirr_engine import calculate_xirr_for_scope
from app.services.cashflow_engine import convert_currency
from app.services.snapshot_engine import calculate_account_snapshots
from app.api.routers.accounts import calculate_all_account_balances, calculate_all_account_cash_balances
from app.api.deps import get_current_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not isinstance(account_id, int):
        account_id = None
    # 1. Fetch active open lots
    lot_stmt = select(Lot).where(Lot.quantity_remaining > 0)
    if account_id:
        lot_stmt = lot_stmt.where(Lot.account_id == account_id)
    lot_res = await db.execute(lot_stmt)
    open_lots = lot_res.scalars().all()
    
    # 2. Group by Asset
    asset_ids = list(set(l.asset_id for l in open_lots))
    
    total_invested = 0.0
    total_current_value = 0.0
    asset_allocation: Dict[str, float] = {}
    sector_allocation: Dict[str, float] = {}
    
    # Pre-fetch latest and previous prices for these assets in a single batch query
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
            .order_by(ranked_ph.c.asset_id, ranked_ph.c.rn)
        )
        ph_res = await db.execute(ph_stmt)

        has_previous_price: Dict[int, bool] = {aid: False for aid in asset_ids}
        for aid, close_px, pdate, rn in ph_res.all():
            if close_px is not None:
                px = float(close_px)
                if rn == 1:
                    asset_prices[aid] = px
                    asset_price_dates[aid] = pdate
                elif rn == 2:
                    asset_previous_prices[aid] = px
                    has_previous_price[aid] = True

        for aid in asset_ids:
            # Fallback semantics: if only one price exists (no rn == 2 record), fallback previous_price to latest_price
            if not has_previous_price[aid] and asset_price_dates[aid] is not None:
                asset_previous_prices[aid] = asset_prices[aid]


    # Pre-fetch assets metadata
    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        ast_stmt = select(Asset).where(Asset.asset_id.in_(asset_ids))
        ast_res = await db.execute(ast_stmt)
        assets_map = {a.asset_id: a for a in ast_res.scalars().all()}

    # Pre-fetch fees and taxes grouped by asset
    fees_stmt = (
        select(
            Transaction.asset_id,
            func.sum(Transaction.fees),
            func.sum(Transaction.taxes)
        )
        .where(Transaction.asset_id.isnot(None))
    )
    if account_id:
        fees_stmt = fees_stmt.where(Transaction.account_id == account_id)
    fees_stmt = fees_stmt.group_by(Transaction.asset_id)
    fees_res = await db.execute(fees_stmt)
    fees_map: Dict[int, tuple] = {
        row[0]: (float(row[1] or 0.0), float(row[2] or 0.0))
        for row in fees_res.all()
    }

    # Calculate Holdings
    holdings_list: List[HoldingSummary] = []
    
    for aid in asset_ids:
        asset = assets_map.get(aid)
        if not asset:
            continue
        
        a_lots = [l for l in open_lots if l.asset_id == aid]
        qty_held = sum(l.quantity_remaining for l in a_lots)
        cost_sum = sum(l.quantity_remaining * l.cost_per_unit for l in a_lots)
        avg_cost = cost_sum / qty_held if qty_held > 0 else 0.0
        
        latest_price = asset_prices.get(aid, 0.0)
        previous_price = asset_previous_prices.get(aid, latest_price)
        change_1d = latest_price - previous_price
        change_1d_pct = (change_1d / previous_price * 100.0) if previous_price > 0 else 0.0
        value_change_1d = qty_held * change_1d

        curr_val = qty_held * latest_price
        unrealized = curr_val - cost_sum
        unrealized_pct = (unrealized / cost_sum * 100.0) if cost_sum > 0 else 0.0
        
        # Realized PnL & Cost Basis for this asset
        rpnl_stmt = select(LotSale.realized_pnl, LotSale.cost_basis)\
            .join(Lot, LotSale.lot_id == Lot.lot_id)\
            .where(Lot.asset_id == aid)
        if account_id:
            rpnl_stmt = rpnl_stmt.where(Lot.account_id == account_id)
        rpnl_res = await db.execute(rpnl_stmt)
        rpnl_rows = rpnl_res.all()
        realized_pnl_for_asset = sum(r[0] for r in rpnl_rows)
        cost_basis_sold_for_asset = sum(r[1] for r in rpnl_rows)
        realized_pnl_pct_for_asset = (realized_pnl_for_asset / cost_basis_sold_for_asset * 100.0) if cost_basis_sold_for_asset > 0 else 0.0
        
        # Fetch fees and taxes for this asset from pre-fetched map
        fees_entry = fees_map.get(aid, (0.0, 0.0))
        asset_fees = fees_entry[0]
        asset_taxes = fees_entry[1]
        total_asset_fees_taxes = asset_fees + asset_taxes

        # Net PnL = Realized PnL + Unrealized PnL (fees/taxes already embedded in FIFO cost basis and sale proceeds)
        net_pnl_for_asset = realized_pnl_for_asset + unrealized
        total_basis = cost_sum + cost_basis_sold_for_asset
        net_pnl_pct_for_asset = (net_pnl_for_asset / total_basis * 100.0) if total_basis > 0 else 0.0
        
        # XIRR for asset
        xirr_val = await calculate_xirr_for_scope(
            db=db,
            scope_type="asset",
            scope_id=aid,
            current_valuation=curr_val
        )
        
        # Determine holding currency from the holding's lots/accounts
        acc_ids = list(set(l.account_id for l in a_lots))
        holding_currency = "USD"
        if acc_ids:
            acc_stmt = select(Account.currency).where(Account.account_id == acc_ids[0])
            acc_res = await db.execute(acc_stmt)
            acc_curr = acc_res.scalar_one_or_none()
            if acc_curr:
                holding_currency = acc_curr
        elif asset.currency:
            holding_currency = asset.currency

        lot_objs = [
            LotResponse(
                lot_id=l.lot_id,
                account_id=l.account_id,
                asset_id=l.asset_id,
                buy_transaction_id=l.buy_transaction_id,
                buy_date=l.buy_date,
                quantity_original=l.quantity_original,
                quantity_remaining=l.quantity_remaining,
                cost_per_unit=l.cost_per_unit,
                asset_symbol=asset.symbol
            )
            for l in a_lots
        ]
        
        holdings_list.append(HoldingSummary(
            asset_id=asset.asset_id,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.asset_type,
            sector=asset.sector,
            currency=holding_currency,
            quantity_held=qty_held,
            avg_cost_price=avg_cost,
            total_cost=cost_sum,
            latest_price=latest_price,
            latest_price_date=asset_price_dates.get(aid, None),
            previous_price=previous_price,
            change_1d=change_1d,
            change_1d_pct=change_1d_pct,
            value_change_1d=value_change_1d,
            current_value=curr_val,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=unrealized_pct,
            realized_pnl=realized_pnl_for_asset,
            realized_pnl_pct=realized_pnl_pct_for_asset,
            fees_and_taxes=total_asset_fees_taxes,
            total_fees=asset_fees,
            total_taxes=asset_taxes,
            net_pnl=net_pnl_for_asset,
            net_pnl_pct=net_pnl_pct_for_asset,
            xirr=xirr_val,
            open_lots=lot_objs
        ))
        
        total_invested += cost_sum
        total_current_value += curr_val
        
        # Allocation tracking
        asset_allocation[asset.asset_type] = asset_allocation.get(asset.asset_type, 0.0) + curr_val
        if asset.sector:
            sector_allocation[asset.sector] = sector_allocation.get(asset.sector, 0.0) + curr_val
        else:
            sector_allocation["Other"] = sector_allocation.get("Other", 0.0) + curr_val

    # 3. Fetch Closed Positions (Assets with LotSale records but 0 open quantity)
    closed_lot_stmt = (
        select(
            Lot.asset_id,
            func.sum(LotSale.realized_pnl),
            func.sum(LotSale.cost_basis),
            func.sum(LotSale.quantity_sold)
        )
        .join(LotSale, Lot.lot_id == LotSale.lot_id)
    )
    if account_id:
        closed_lot_stmt = closed_lot_stmt.where(Lot.account_id == account_id)
    closed_lot_stmt = closed_lot_stmt.group_by(Lot.asset_id)
    closed_lot_res = await db.execute(closed_lot_stmt)

    open_asset_ids_set = set(asset_ids)
    closed_holdings_list: List[HoldingSummary] = []

    for c_aid, c_rpnl, c_cost_basis, c_qty_sold in closed_lot_res.all():
        if c_aid in open_asset_ids_set:
            continue

        c_asset_res = await db.execute(select(Asset).where(Asset.asset_id == c_aid))
        c_asset = c_asset_res.scalar_one_or_none()
        if not c_asset:
            continue

        c_rpnl = c_rpnl or 0.0
        c_cost_basis = c_cost_basis or 0.0
        c_qty_sold = c_qty_sold or 0.0
        c_rpnl_pct = (c_rpnl / c_cost_basis * 100.0) if c_cost_basis > 0 else 0.0

        c_xirr = await calculate_xirr_for_scope(
            db=db,
            scope_type="asset",
            scope_id=c_aid,
            current_valuation=0.0
        )

        c_acc_stmt = select(Account.currency).join(Lot, Account.account_id == Lot.account_id).where(Lot.asset_id == c_aid)
        if account_id:
            c_acc_stmt = c_acc_stmt.where(Account.account_id == account_id)
        c_acc_res = await db.execute(c_acc_stmt)
        c_curr = c_acc_res.scalar_one_or_none() or c_asset.currency or "USD"

        # Pre-fetch latest price
        c_ph_stmt = select(PriceHistory.close_price).where(PriceHistory.asset_id == c_aid).order_by(desc(PriceHistory.price_date)).limit(1)
        c_ph_res = await db.execute(c_ph_stmt)
        c_latest_price = c_ph_res.scalar_one_or_none() or 0.0

        # Fetch fees and taxes for this closed asset from pre-fetched map
        c_fees_entry = fees_map.get(c_aid, (0.0, 0.0))
        c_asset_fees = c_fees_entry[0]
        c_asset_taxes = c_fees_entry[1]
        c_total_asset_fees_taxes = c_asset_fees + c_asset_taxes

        closed_holdings_list.append(HoldingSummary(
            asset_id=c_asset.asset_id,
            symbol=c_asset.symbol,
            name=c_asset.name,
            asset_type=c_asset.asset_type,
            sector=c_asset.sector,
            currency=c_curr,
            quantity_held=0.0,
            avg_cost_price=c_cost_basis / c_qty_sold if c_qty_sold > 0 else 0.0,
            total_cost=c_cost_basis,
            latest_price=c_latest_price,
            current_value=0.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            realized_pnl=c_rpnl,
            realized_pnl_pct=c_rpnl_pct,
            fees_and_taxes=c_total_asset_fees_taxes,
            total_fees=c_asset_fees,
            total_taxes=c_asset_taxes,
            net_pnl=c_rpnl,
            net_pnl_pct=c_rpnl_pct,
            xirr=c_xirr,
            open_lots=[]
        ))

    # 4. Fetch Realized PnL total
    tot_rpnl_stmt = select(LotSale.realized_pnl)
    if account_id:
        tot_rpnl_stmt = tot_rpnl_stmt.join(Lot, LotSale.lot_id == Lot.lot_id).where(Lot.account_id == account_id)
    tot_rpnl_res = await db.execute(tot_rpnl_stmt)
    total_realized_pnl = sum(tot_rpnl_res.scalars().all())
    
    # 5. Fetch Cash Balance using centralized funding-account & cashflow aware engine
    balances = await calculate_all_account_cash_balances(db)
    if account_id:
        cash_balance = balances.get(account_id, 0.0)
    else:
        cash_balance = sum(balances.values())
            
    total_net_worth = total_current_value + max(0.0, cash_balance)
    total_unrealized_pnl = total_current_value - total_invested
    
    # Portfolio-wide XIRR
    portfolio_xirr = await calculate_xirr_for_scope(
        db=db,
        scope_type="account" if account_id else "portfolio",
        scope_id=account_id,
        current_valuation=total_net_worth
    )
    
    # Fetch transactions for total fees and taxes
    tx_stmt = select(Transaction)
    if account_id:
        tx_stmt = tx_stmt.where(Transaction.account_id == account_id)
    tx_res = await db.execute(tx_stmt)
    all_txs = tx_res.scalars().all()
    # Fetch accounts map for currency resolution
    all_accounts_res = await db.execute(select(Account))
    all_accounts = {a.account_id: a for a in all_accounts_res.scalars().all()}

    total_fees = 0.0
    total_taxes = 0.0
    for tx in all_txs:
        acc = all_accounts.get(tx.account_id)
        tx_curr = acc.currency if acc else "USD"
        if tx.fees:
            if account_id:
                total_fees += tx.fees
            else:
                total_fees += convert_currency(tx.fees, tx_curr, "EUR")
        if tx.taxes:
            if account_id:
                total_taxes += tx.taxes
            else:
                total_taxes += convert_currency(tx.taxes, tx_curr, "EUR")

    # Sort top holdings by current value
    holdings_list.sort(key=lambda h: h.current_value, reverse=True)
    closed_holdings_list.sort(key=lambda h: abs(h.realized_pnl), reverse=True)

    total_value_change_1d = sum(h.value_change_1d for h in holdings_list)
    base_val = total_current_value - total_value_change_1d
    total_change_1d_pct = (total_value_change_1d / base_val * 100.0) if base_val > 0 else 0.0
    
    return PortfolioSummaryResponse(
        total_net_worth=total_net_worth,
        total_invested=total_invested,
        total_current_value=total_current_value,
        cash_balance=cash_balance,
        total_realized_pnl=total_realized_pnl,
        total_unrealized_pnl=total_unrealized_pnl,
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

@router.get("/holdings", response_model=List[HoldingSummary])
async def get_holdings(
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    summary = await get_portfolio_summary(account_id=account_id, db=db, current_user=current_user)
    return summary.top_holdings

@router.get("/closed-holdings", response_model=List[HoldingSummary])
async def get_closed_holdings(
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    summary = await get_portfolio_summary(account_id=account_id, db=db, current_user=current_user)
    return summary.closed_holdings

@router.get("/realized-pnl", response_model=List[LotSaleResponse])
async def get_realized_pnl(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(LotSale, Lot.buy_date, Transaction.transaction_date, Asset.symbol)\
        .join(Lot, LotSale.lot_id == Lot.lot_id)\
        .join(Transaction, LotSale.sell_transaction_id == Transaction.transaction_id)\
        .join(Asset, Lot.asset_id == Asset.asset_id)\
        .order_by(desc(Transaction.transaction_date))
        
    res = await db.execute(stmt)
    rows = res.all()
    
    out = []
    for lot_sale, buy_date, sell_date, symbol in rows:
        out.append(LotSaleResponse(
            lot_sale_id=lot_sale.lot_sale_id,
            lot_id=lot_sale.lot_id,
            sell_transaction_id=lot_sale.sell_transaction_id,
            quantity_sold=lot_sale.quantity_sold,
            sale_price_per_unit=lot_sale.sale_price_per_unit,
            cost_basis=lot_sale.cost_basis,
            realized_pnl=lot_sale.realized_pnl,
            holding_period_days=lot_sale.holding_period_days,
            buy_date=buy_date,
            sell_date=sell_date,
            asset_symbol=symbol
        ))
        
    return out

@router.get("/annual_snapshot", response_model=AnnualSnapshotResponse)
async def get_annual_snapshot(
    fiscal_year_start: Optional[str] = "01-01",
    master_currency: Optional[str] = "EUR",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not isinstance(fiscal_year_start, str):
        fiscal_year_start = "01-01"
    if not isinstance(master_currency, str):
        master_currency = "EUR"
    target_currency = (master_currency or "EUR").strip().upper()
    today = datetime.date.today()

    # Parse fiscal_year_start e.g. "01-01" or "04-01"
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

    # Year label e.g. "FY 2026-27" or "CY 2026"
    year_label = f"FY {start_year}-{start_year+1}" if (fy_month, fy_day) != (1, 1) else f"CY {start_year}"

    # 1. Fetch Income & Expenses from CashflowTransaction
    c_stmt = select(CashflowTransaction).options(
        selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
    ).where(CashflowTransaction.transaction_date >= start_date, CashflowTransaction.transaction_date <= end_date)
    c_res = await db.execute(c_stmt)
    c_txs = c_res.scalars().all()

    total_income = 0.0
    total_expenses = 0.0
    investments_done = 0.0
    investments_closed = 0.0
    taxes_and_fees = 0.0

    for ctx in c_txs:
        for itm in ctx.items:
            amt = convert_currency(float(itm.amount or 0.0), ctx.currency or "EUR", target_currency)
            cat_type = itm.category.category_type if itm.category else "EXPENSE"
            if cat_type == "INCOME":
                total_income += amt
            elif cat_type == "INVESTMENT":
                investments_done += amt
            elif cat_type == "TRANSFER":
                pass
            else: # EXPENSE
                total_expenses += amt

    # 2. Fetch Investment transactions in date range
    tx_stmt = select(Transaction, Account.currency)\
        .join(Account, Transaction.account_id == Account.account_id)\
        .where(Transaction.transaction_date >= start_date, Transaction.transaction_date <= end_date)
    tx_res = await db.execute(tx_stmt)
    inv_txs = tx_res.all()

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

    # 3. Calculate current net worth & estimated delta
    all_balances = await calculate_all_account_balances(db)
    acc_map_res = await db.execute(select(Account))
    all_accs = acc_map_res.scalars().all()
    
    current_total_nw = sum(
        convert_currency(all_balances.get(a.account_id, 0.0), a.currency or "EUR", target_currency)
        for a in all_accs
    )

    # 4. Calculate start-of-year/period net worth to derive true change in net worth
    start_total_nw = 0.0
    for acc in all_accs:
        acc_curr = acc.currency or "EUR"
        snaps = await calculate_account_snapshots(db, account_id=acc.account_id, end_date=end_date)
        if snaps:
            valid_start_snaps = [s for s in snaps if s["snapshot_date"] <= start_date]
            if valid_start_snaps:
                start_total_nw += convert_currency(valid_start_snaps[-1]["net_worth"], acc_curr, target_currency)

    net_savings = total_income - total_expenses
    net_worth_delta = current_total_nw - start_total_nw
    net_worth_delta_pct = (net_worth_delta / start_total_nw * 100.0) if start_total_nw > 0 else 0.0

    return AnnualSnapshotResponse(
        year_label=year_label,
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        investments_done=round(investments_done, 2),
        investments_closed=round(investments_closed, 2),
        net_worth_delta=round(net_worth_delta, 2),
        net_worth_delta_pct=round(net_worth_delta_pct, 2),
        taxes_and_fees=round(taxes_and_fees, 2),
        net_savings=round(net_savings, 2),
        currency=target_currency
    )
