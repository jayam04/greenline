import re

with open("backend/app/api/routers/corporate_actions.py", "r") as f:
    content = f.read()

replacement = """    # Fully recalculate all lots with the new action interleaving
    await recalculate_all_lots(db)
    
    from app.services.snapshot_engine import recalculate_past_snapshots
    await recalculate_past_snapshots(db, start_date=action.action_date)

    return action"""

content = re.sub(r'    # Fully recalculate all lots with the new action interleaving\n    await recalculate_all_lots\(db\)\n\n    return action', replacement, content)

with open("backend/app/api/routers/corporate_actions.py", "w") as f:
    f.write(content)
