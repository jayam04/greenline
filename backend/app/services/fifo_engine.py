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
        
        buy_fees = float(tx.fees or 0.0)
        buy_taxes = float(tx.taxes or 0.0)
        unit_price = float(tx.price_per_unit) if tx.price_per_unit is not None else (float(tx.total_amount) / float(tx.quantity))
        total_buy_cost = (float(tx.quantity) * unit_price) + buy_fees + buy_taxes
        
        # Calculate cost per unit including fees/taxes
        cost_per_unit = total_buy_cost / float(tx.quantity)
        
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
        
        funding_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
        # Cash flows (Negative for investments, full outlay including fees & taxes)
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=-abs(total_buy_cost),
            flow_type="buy"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=funding_acc_id,
            flow_date=tx.transaction_date,
            amount=-abs(total_buy_cost),
            flow_type="buy"
        ))
        if tx.asset_id:
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=-abs(total_buy_cost),
                flow_type="buy"
            ))
        await db.flush()

    elif t_type == "sell":
        if tx.quantity is None or tx.quantity <= 0:
            return
            
        sale_qty_remaining = float(tx.quantity)
        sell_fees = float(tx.fees or 0.0)
        sell_taxes = float(tx.taxes or 0.0)
        unit_price = float(tx.price_per_unit) if tx.price_per_unit is not None else (float(tx.total_amount) / float(tx.quantity))
        net_total_sale_proceeds = (float(tx.quantity) * unit_price) - sell_fees - sell_taxes
        net_sale_price_per_unit = net_total_sale_proceeds / float(tx.quantity)
        
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
        for lot in open_lots:
            if sale_qty_remaining <= 0:
                break
                
            qty_to_take = min(lot.quantity_remaining, sale_qty_remaining)
            lot.quantity_remaining -= qty_to_take
            sale_qty_remaining -= qty_to_take
            
            cost_basis = qty_to_take * lot.cost_per_unit
            net_lot_proceeds = qty_to_take * net_sale_price_per_unit
            realized_pnl = net_lot_proceeds - cost_basis
            holding_days = (tx.transaction_date - lot.buy_date).days
            
            lot_sale = LotSale(
                lot_id=lot.lot_id,
                sell_transaction_id=tx.transaction_id,
                quantity_sold=qty_to_take,
                sale_price_per_unit=net_sale_price_per_unit,
                cost_basis=cost_basis,
                realized_pnl=realized_pnl,
                holding_period_days=max(0, holding_days)
            )
            db.add(lot_sale)
            
        funding_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
        # Cash flows (Positive for sales, net proceeds after fees & taxes)
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=net_total_sale_proceeds,
            flow_type="sell"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=funding_acc_id,
            flow_date=tx.transaction_date,
            amount=net_total_sale_proceeds,
            flow_type="sell"
        ))
        if tx.asset_id:
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=net_total_sale_proceeds,
                flow_type="sell"
            ))
        await db.flush()

    elif t_type == "deposit":
        funding_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=abs(tx.total_amount),
            flow_type="deposit"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=funding_acc_id,
            flow_date=tx.transaction_date,
            amount=abs(tx.total_amount),
            flow_type="deposit"
        ))
        await db.flush()

    elif t_type == "withdrawal":
        funding_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
        db.add(CashFlow(
            scope_type="portfolio",
            scope_id=None,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="withdrawal"
        ))
        db.add(CashFlow(
            scope_type="account",
            scope_id=funding_acc_id,
            flow_date=tx.transaction_date,
            amount=-abs(tx.total_amount),
            flow_type="withdrawal"
        ))
        await db.flush()

    elif t_type == "dividend":
        funding_acc_id = getattr(tx, "funding_account_id", None) or tx.account_id
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
            
            net_dividend = abs(tx.total_amount) - tx.taxes
            db.add(CashFlow(
                scope_type="portfolio",
                scope_id=None,
                flow_date=tx.transaction_date,
                amount=net_dividend,
                flow_type="dividend"
            ))
            db.add(CashFlow(
                scope_type="account",
                scope_id=funding_acc_id,
                flow_date=tx.transaction_date,
                amount=net_dividend,
                flow_type="dividend"
            ))
            db.add(CashFlow(
                scope_type="asset",
                scope_id=tx.asset_id,
                flow_date=tx.transaction_date,
                amount=net_dividend,
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
