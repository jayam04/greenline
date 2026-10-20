import re
with open('backend/app/api/routers/transactions.py', 'r') as f:
    content = f.read()

helper = """
async def _adjust_price_history_for_split(db: AsyncSession, tx: Transaction):
    from app.db.models import Asset, Lot, PriceHistory
    from sqlalchemy import func
    
    if tx.transaction_type not in ["split", "bonus"] or not tx.asset_id or not tx.quantity:
        return
        
    stmt_asset = select(Asset).where(Asset.asset_id == tx.asset_id)
    res_asset = await db.execute(stmt_asset)
    asset = res_asset.scalars().first()
    
    if asset and asset.asset_type == "Private Equity":
        # Calculate old shares
        stmt_lots = select(func.sum(Lot.quantity_remaining)).where(
            Lot.account_id == tx.account_id,
            Lot.asset_id == tx.asset_id,
            Lot.buy_date < tx.transaction_date
        )
        old_shares = (await db.execute(stmt_lots)).scalar() or 0.0
        
        if old_shares > 0:
            multiplier = (old_shares + float(tx.quantity)) / old_shares
            if multiplier > 0:
                stmt_ph = select(PriceHistory).where(
                    PriceHistory.asset_id == tx.asset_id,
                    PriceHistory.price_date <= tx.transaction_date
                )
                res_ph = await db.execute(stmt_ph)
                for ph in res_ph.scalars().all():
                    ph.close_price /= multiplier
                await db.commit()

"""

content = content.replace("async def _ensure_price_history_for_tx(db: AsyncSession, tx: Transaction):", helper + "async def _ensure_price_history_for_tx(db: AsyncSession, tx: Transaction):")

replacement_create = """
    # Auto-populate price history for transaction date if missing
    await _ensure_price_history_for_tx(db, tx)
    await _adjust_price_history_for_split(db, tx)
"""
content = content.replace("    # Auto-populate price history for transaction date if missing\n    await _ensure_price_history_for_tx(db, tx)", replacement_create)

with open('backend/app/api/routers/transactions.py', 'w') as f:
    f.write(content)
