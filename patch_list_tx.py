import re

with open("backend/app/api/routers/transactions.py", "r") as f:
    content = f.read()

replacement = """    stmt = stmt.order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id)).limit(limit).offset(offset)
    
    res = await db.execute(stmt)
    rows = res.all()
    
    out = []
    for tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr in rows:
        out.append(_build_transaction_response(tx, acc_name, acc_curr, symbol, asset_name, f_acc_name, f_acc_curr))
        
    # Also fetch Corporate Actions and inject them
    from app.db.models import CorporateAction
    ca_stmt = select(CorporateAction, Asset.symbol, Asset.name).join(Asset, CorporateAction.asset_id == Asset.asset_id)
    if asset_id:
        ca_stmt = ca_stmt.where(CorporateAction.asset_id == asset_id)
    ca_res = await db.execute(ca_stmt)
    ca_rows = ca_res.all()
    
    for ca, symbol, asset_name in ca_rows:
        dummy_tx = Transaction(
            transaction_id=-ca.action_id, # negative to avoid collision
            account_id=0,
            asset_id=ca.asset_id,
            transaction_type=ca.action_type,
            transaction_date=ca.action_date,
            quantity=0.0,
            price_per_unit=0.0,
            total_amount=0.0,
            notes=f"Ratio: {ca.ratio}" + (f" - {ca.notes}" if ca.notes else "")
        )
        out.append(_build_transaction_response(dummy_tx, "System", "USD", symbol, asset_name))

    out.sort(key=lambda x: (x.transaction_date, x.transaction_id), reverse=True)
    out = out[:limit]
        
    return out"""

content = re.sub(r'    stmt = stmt.order_by\(desc\(Transaction.transaction_date\).*?return out', replacement, content, flags=re.DOTALL)

with open("backend/app/api/routers/transactions.py", "w") as f:
    f.write(content)
