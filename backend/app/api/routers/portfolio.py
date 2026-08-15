from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.db.database import get_db
from app.db.models import Account, Asset, Lot, LotSale, PriceHistory, Transaction, User
from app.schemas.schemas import PortfolioSummaryResponse, HoldingSummary, LotResponse, LotSaleResponse
from app.services.xirr_engine import calculate_xirr_for_scope
from app.api.deps import get_current_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    
    # Pre-fetch latest prices for these assets
    asset_prices: Dict[int, float] = {}
    asset_price_dates: Dict[int, str] = {}
    for aid in asset_ids:
        ph_stmt = select(PriceHistory)\
            .where(PriceHistory.asset_id == aid)\
            .order_by(desc(PriceHistory.price_date))\
            .limit(1)
        ph_res = await db.execute(ph_stmt)
        ph = ph_res.scalar_one_or_none()
        if ph:
            asset_prices[aid] = ph.close_price
            asset_price_dates[aid] = ph.price_date.isoformat()
        else:
            asset_prices[aid] = 0.0
            asset_price_dates[aid] = ""

    # Pre-fetch assets metadata
    assets_map: Dict[int, Asset] = {}
    if asset_ids:
        ast_stmt = select(Asset).where(Asset.asset_id.in_(asset_ids))
        ast_res = await db.execute(ast_stmt)
        assets_map = {a.asset_id: a for a in ast_res.scalars().all()}

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
            latest_price_date=asset_price_dates.get(aid, ""),
            current_value=curr_val,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=unrealized_pct,
            realized_pnl=realized_pnl_for_asset,
            realized_pnl_pct=realized_pnl_pct_for_asset,
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
            xirr=c_xirr,
            open_lots=[]
        ))

    # 4. Fetch Realized PnL total
    tot_rpnl_stmt = select(LotSale.realized_pnl)
    if account_id:
        tot_rpnl_stmt = tot_rpnl_stmt.join(Lot, LotSale.lot_id == Lot.lot_id).where(Lot.account_id == account_id)
    tot_rpnl_res = await db.execute(tot_rpnl_stmt)
    total_realized_pnl = sum(tot_rpnl_res.scalars().all())
    
    # 5. Fetch Cash Balance from transactions
    tx_stmt = select(Transaction)
    if account_id:
        tx_stmt = tx_stmt.where(Transaction.account_id == account_id)
    tx_res = await db.execute(tx_stmt)
    all_txs = tx_res.scalars().all()
    
    cash_balance = 0.0
    for tx in all_txs:
        ttype = tx.transaction_type.lower()
        if ttype in ["deposit", "sell", "dividend", "interest"]:
            cash_balance += (tx.total_amount - tx.fees - tx.taxes)
        elif ttype in ["withdrawal", "buy", "fee"]:
            cash_balance -= (tx.total_amount + tx.fees + tx.taxes)
            
    total_net_worth = total_current_value + max(0.0, cash_balance)
    total_unrealized_pnl = total_current_value - total_invested
    
    # Portfolio-wide XIRR
    portfolio_xirr = await calculate_xirr_for_scope(
        db=db,
        scope_type="account" if account_id else "portfolio",
        scope_id=account_id,
        current_valuation=total_net_worth
    )
    
    total_fees = sum(tx.fees for tx in all_txs if tx.fees)
    total_taxes = sum(tx.taxes for tx in all_txs if tx.taxes)

    # Sort top holdings by current value
    holdings_list.sort(key=lambda h: h.current_value, reverse=True)
    closed_holdings_list.sort(key=lambda h: abs(h.realized_pnl), reverse=True)
    
    return PortfolioSummaryResponse(
        total_net_worth=total_net_worth,
        total_invested=total_invested,
        total_current_value=total_current_value,
        cash_balance=cash_balance,
        total_realized_pnl=total_realized_pnl,
        total_unrealized_pnl=total_unrealized_pnl,
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
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    summary = await get_portfolio_summary(account_id=account_id, db=db, current_user=current_user)
    return summary.top_holdings

@router.get("/closed-holdings", response_model=List[HoldingSummary])
async def get_closed_holdings(
    account_id: Optional[int] = Query(None),
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
