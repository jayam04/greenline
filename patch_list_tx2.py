import re

with open("backend/app/api/routers/transactions.py", "r") as f:
    content = f.read()

replacement = """        dummy_tx = Transaction(
            transaction_id=-ca.action_id, # negative to avoid collision
            account_id=0,
            asset_id=ca.asset_id,
            transaction_type=ca.action_type,
            transaction_date=ca.action_date,
            quantity=0.0,
            price_per_unit=0.0,
            total_amount=0.0,
            fees=0.0,
            taxes=0.0,
            notes=f"Ratio: {ca.ratio}" + (f" - {ca.notes}" if ca.notes else "")
        )"""

content = re.sub(r'        dummy_tx = Transaction\(\n            transaction_id=-ca.action_id, # negative to avoid collision\n            account_id=0,\n            asset_id=ca.asset_id,\n            transaction_type=ca.action_type,\n            transaction_date=ca.action_date,\n            quantity=0.0,\n            price_per_unit=0.0,\n            total_amount=0.0,\n            notes=f"Ratio: {ca.ratio}" \+ \(f" - {ca.notes}" if ca.notes else ""\)\n        \)', replacement, content)

with open("backend/app/api/routers/transactions.py", "w") as f:
    f.write(content)
