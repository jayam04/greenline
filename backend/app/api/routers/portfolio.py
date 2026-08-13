from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.database import get_db
from app.db.models import (
    Lot, LotSale, Asset, PriceHistory, Transaction, User, Account
)
from app.schemas.schemas import (
    PortfolioSummaryResponse, HoldingSummary, LotResponse, LotSaleResponse
)
from app.services.xirr_engine import calculate_xirr_for_scope
from app.services.snapshot_engine import generate_daily_snapshot
from app.api.deps import get_current_user
import datetime

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    snapshot = await generate_daily_snapshot(db)
    
    # Calculate overall Portfolio XIRR
    p_xirr = await calculate_xirr_for_scope(
        db=db,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=snapshot.net_worth
    )
    
    # Asset Allocation dictionary
    alloc_map: Dict[str, float] = {}
    for b in snapshot.asset_class_breakdowns:
        alloc_map[b.asset_class] = b.value
        
    # Get top holdings
    holdings_data = await get_holdings_data(db)
    
    return PortfolioSummaryResponse(
        total_net_worth=snapshot.net_worth,
        total_invested=snapshot.total_invested,
        total_current_value=snapshot.total_current_value,
        cash_balance=snapshot.cash_balance,
        total_realized_pnl=snapshot.total_realized_pnl,
        total_unrealized_pnl=snapshot.total_unrealized_pnl,
        portfolio_xirr=p_xirr,
        asset_allocation=alloc_map,
        top_holdings=holdings_data[:5]
    )

@router.get("/holdings", response_model=List[HoldingSummary])
async def get_holdings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_holdings_data(db)

async def get_holdings_data(db: AsyncSession) -> List[HoldingSummary]:
    # Query realized P&L per asset
    realized_stmt = (
        select(Lot.asset_id, func.sum(LotSale.realized_pnl))
        .join(LotSale, Lot.lot_id == LotSale.lot_id)
        .group_by(Lot.asset_id)
    )
    realized_res = await db.execute(realized_stmt)
    realized_map: Dict[int, float] = {row[0]: (row[1] or 0.0) for row in realized_res.all()}

    # Fetch all open lots
    lot_stmt = select(Lot).where(Lot.quantity_remaining > 0)
    lot_res = await db.execute(lot_stmt)
    open_lots: List[Lot] = lot_res.scalars().all()
    
    # Group by asset_id
    asset_lots_map: Dict[int, List[Lot]] = {}
    for lot in open_lots:
        asset_lots_map.setdefault(lot.asset_id, []).append(lot)
        
    all_asset_ids = set(asset_lots_map.keys()).union(set(realized_map.keys()))
    if not all_asset_ids:
        return []
        
    # Fetch assets
    asset_stmt = select(Asset).where(Asset.asset_id.in_(list(all_asset_ids)))
    asset_res = await db.execute(asset_stmt)
    assets = asset_res.scalars().all()
    
    holdings: List[HoldingSummary] = []
    
    for asset in assets:
        lots = asset_lots_map.get(asset.asset_id, [])
        total_qty = sum(l.quantity_remaining for l in lots)
        total_cost = sum(l.quantity_remaining * l.cost_per_unit for l in lots)
        avg_cost = total_cost / total_qty if total_qty > 0 else 0.0
        realized_pnl = realized_map.get(asset.asset_id, 0.0)
        
        # Get latest price
        p_stmt = (
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset.asset_id)
            .order_by(desc(PriceHistory.price_date))
            .limit(1)
        )
        p_res = await db.execute(p_stmt)
        ph = p_res.scalar_one_or_none()
        
        latest_price = ph.close_price if ph else avg_cost
        price_date = ph.price_date if ph else None
        
        current_val = total_qty * latest_price
        unrealized_pnl = current_val - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        
        # Stock XIRR
        stk_xirr = await calculate_xirr_for_scope(
            db=db,
            scope_type="asset",
            scope_id=asset.asset_id,
            current_valuation=current_val
        )
        
        lot_responses = []
        for l in lots:
            l_dict = LotResponse.model_validate(l).model_dump()
            l_dict["asset_symbol"] = asset.symbol
            lot_responses.append(LotResponse(**l_dict))
            
        holdings.append(HoldingSummary(
            asset_id=asset.asset_id,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.asset_type,
            sector=asset.sector,
            quantity_held=total_qty,
            avg_cost_price=avg_cost,
            total_cost=total_cost,
            latest_price=latest_price,
            latest_price_date=price_date,
            current_value=current_val,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            realized_pnl=realized_pnl,
            xirr=stk_xirr,
            open_lots=lot_responses
        ))
        
    holdings.sort(key=lambda h: (h.current_value, abs(h.realized_pnl)), reverse=True)
    return holdings

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
        ls_dict = LotSaleResponse.model_validate(lot_sale).model_dump()
        ls_dict["buy_date"] = buy_date
        ls_dict["sell_date"] = sell_date
        ls_dict["asset_symbol"] = symbol
        out.append(LotSaleResponse(**ls_dict))
        
    return out
