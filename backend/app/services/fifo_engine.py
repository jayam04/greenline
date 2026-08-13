import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, delete
from app.db.models import Transaction, Lot, LotSale, CashFlow, Dividend

async def process_transaction_event(db: AsyncSession, tx: Transaction) -> None:
    """
    Processes transaction events (buy, sell, deposit, withdrawal, dividend)
    and updates lots, lot_sales, cash_flows, and dividends.
    """
    t_type = tx.transaction_type.lower()
    
    if t_type == "buy":
        if tx.quantity is None or tx.quantity <= 0:
            return
        
        # Calculate cost per unit including fees/taxes
        cost_per_unit = tx.price_per_unit if tx.price_per_unit else (tx.total_amount / tx.quantity)
        
        lot = Lot(
            account_id=tx.account_id,
            asset_id=tx.asset_id,
            buy_transaction_id=tx.transaction_id,
            buy_date=tx.transaction_date,
            quantity_original=tx.quantity,
            quantity_remaining=tx.quantity,
            cost_per_unit=cost_per_unit
        )
        db.add(lot)
        
        # Cash flows (Negative for investments)
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="buy"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=tx.account_id,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="buy"
        ))
        if tx.asset_id:
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=-abs(tx.total_amount),
                flow_type="buy"
            ))
        await db.flush()

    elif t_type == "sell":
        if tx.quantity is None or tx.quantity <= 0:
            return
            
        sale_qty_remaining = tx.quantity
        sale_price = tx.price_per_unit if tx.price_per_unit else (tx.total_amount / tx.quantity)
        
        # Find open lots FIFO (ordered by buy_date ASC, lot_id ASC)
        stmt = (
            select(Lot)
            .where(
                Lot.account_id == tx.account_id,
                Lot.asset_id == tx.asset_id,
                Lot.quantity_remaining > 0
            )
            .order_by(asc(Lot.buy_date), asc(Lot.lot_id))
        )
        result = await db.execute(stmt)
        open_lots: List[Lot] = list(result.scalars().all())

        if not open_lots:
            stmt_all = (
                select(Lot)
                .where(
                    Lot.asset_id == tx.asset_id,
                    Lot.quantity_remaining > 0
                )
                .order_by(asc(Lot.buy_date), asc(Lot.lot_id))
            )
            result_all = await db.execute(stmt_all)
            open_lots = list(result_all.scalars().all())
        
        for lot in open_lots:
            if sale_qty_remaining <= 0:
                break
                
            qty_to_take = min(lot.quantity_remaining, sale_qty_remaining)
            lot.quantity_remaining -= qty_to_take
            sale_qty_remaining -= qty_to_take
            
            cost_basis = qty_to_take * lot.cost_per_unit
            sale_proceeds = qty_to_take * sale_price
            realized_pnl = sale_proceeds - cost_basis
            holding_days = (tx.transaction_date - lot.buy_date).days
            
            lot_sale = LotSale(
                lot_id=lot.lot_id,
                sell_transaction_id=tx.transaction_id,
                quantity_sold=qty_to_take,
                sale_price_per_unit=sale_price,
                cost_basis=cost_basis,
                realized_pnl=realized_pnl,
                holding_period_days=max(0, holding_days)
            )
            db.add(lot_sale)
            
        # Cash flows (Positive for sales)
        net_proceeds = abs(tx.total_amount) - tx.fees - tx.taxes
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=net_proceeds,
            flow_type="sell"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=tx.account_id,
            flow_date=tx.transaction_date,
            amount=net_proceeds,
            flow_type="sell"
        ))
        if tx.asset_id:
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=net_proceeds,
                flow_type="sell"
            ))
        await db.flush()

    elif t_type == "deposit":
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=abs(tx.total_amount),
            flow_type="deposit"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=tx.account_id,
            flow_date=tx.transaction_date,
            amount=abs(tx.total_amount),
            flow_type="deposit"
        ))
        await db.flush()

    elif t_type == "withdrawal":
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="withdrawal"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=tx.account_id,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="withdrawal"
        ))
        await db.flush()

    elif t_type == "dividend":
        if tx.asset_id:
            div = Dividend(
                asset_id=tx.asset_id,
                account_id=tx.account_id,
                pay_date=tx.transaction_date,
                amount_per_share=tx.price_per_unit,
                total_amount=tx.total_amount,
                tax_withheld=tx.taxes
            )
            db.add(div)
            
            db.add(CashFlow(
                scope_type="portfolio",
                scope_id=None,
                flow_date=tx.transaction_date,
                amount=abs(tx.total_amount),
                flow_type="dividend"
            ))
            db.add(CashFlow(
                scope_type="account",
                scope_id=tx.account_id,
                flow_date=tx.transaction_date,
                amount=abs(tx.total_amount),
                flow_type="dividend"
            ))
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=abs(tx.total_amount),
                flow_type="dividend"
            ))
            await db.flush()

async def recalculate_all_lots(db: AsyncSession) -> None:
    """
    Clears all derived state (lot_sales, lots, cash_flows, dividends)
    and re-processes all transactions chronologically.
    """
    db.expire_all()
    await db.execute(delete(LotSale))
    await db.execute(delete(Lot))
    await db.execute(delete(CashFlow))
    await db.execute(delete(Dividend))
    await db.commit()

    stmt = select(Transaction).order_by(asc(Transaction.transaction_date), asc(Transaction.transaction_id))
    result = await db.execute(stmt)
    all_txs: List[Transaction] = result.scalars().all()

    for tx in all_txs:
        await process_transaction_event(db, tx)

    await db.commit()
