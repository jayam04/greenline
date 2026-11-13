#!/usr/bin/env python3
"""
Migrate legacy SQLite database (data/investments.db) to Oracle Database.
Handles user_id alignment, table dependencies, and valuation snapshot generation.
"""

import sys
import os
import sqlite3
import json
import asyncio
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.database import create_database_engine, async_sessionmaker, AsyncSession
from app.services.backup_service import _restore_database_rows
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import generate_daily_snapshot, recalculate_past_snapshots
from sqlalchemy import select, func, text
from app.db.models import Transaction, User

SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "investments.db"

def export_sqlite_tables():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite_")]
    
    payload = {"format": "greenline-db-backup-v1", "created_at": "migration", "tables": {}}
    for t in tables:
        c.execute(f"SELECT * FROM {t}")
        rows = [dict(r) for r in c.fetchall()]
        
        # Ensure user_id 1 in api_keys is mapped to user_id 0 if user 1 does not exist
        if t == "api_keys":
            for row in rows:
                if row.get("user_id") == 1:
                    row["user_id"] = 0

        # Exclude legacy ai/import tables no longer in Oracle schema
        if t in ("import_batches", "staged_records", "corporate_actions"):
            continue

        payload["tables"][t] = rows
        print(f"  [SQLite Export] {t}: {len(rows)} records")
        
    conn.close()
    return payload

async def migrate():
    db_url = os.getenv("DATABASE_URL", "oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1")
    engine = create_database_engine(db_url)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    payload = export_sqlite_tables()
    async with Session() as session:
        print("\n[Oracle Restore] Restoring rows into Oracle Database...")
        await _restore_database_rows(payload, session)
        
        print("[Oracle Restore] Recalculating FIFO lots...")
        await recalculate_all_lots(session)
        
        min_tx = await session.execute(select(func.min(Transaction.transaction_date)))
        earliest_date = min_tx.scalar_one_or_none()
        if earliest_date:
            print(f"[Oracle Restore] Recalculating snapshots from {earliest_date}...")
            await recalculate_past_snapshots(session, start_date=earliest_date)
        else:
            await generate_daily_snapshot(session)
            
        print("[Oracle Restore] Migration successfully completed!")

if __name__ == "__main__":
    asyncio.run(migrate())
