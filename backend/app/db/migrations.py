import datetime
from typing import Set
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.database import Base

async def init_migrations_table(session: AsyncSession) -> None:
    """Creates the schema_migrations tracking table if it does not already exist."""
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR PRIMARY KEY,
            description VARCHAR,
            applied_at DATETIME
        )
    """))
    await session.commit()

async def get_applied_migrations(session: AsyncSession) -> Set[str]:
    """Fetches all applied migration version tags."""
    await init_migrations_table(session)
    res = await session.execute(text("SELECT version FROM schema_migrations"))
    return set(row[0] for row in res.all())

async def mark_migration_applied(session: AsyncSession, version: str, description: str) -> None:
    """Records a migration as successfully applied."""
    await session.execute(
        text("INSERT INTO schema_migrations (version, description, applied_at) VALUES (:version, :desc, :at)"),
        {"version": version, "desc": description, "at": datetime.datetime.utcnow()}
    )
    await session.commit()

async def run_db_migrations(session: AsyncSession) -> None:
    """
    Runs all pending database schema and data migrations deterministically.
    Each migration is executed at most once and tracked in `schema_migrations`.
    """
    applied = await get_applied_migrations(session)

    # v001: Create base schema tables
    if "v001_initial_schema" not in applied:
        conn = await session.connection()
        await conn.run_sync(Base.metadata.create_all)
        await session.commit()
        await mark_migration_applied(session, "v001_initial_schema", "Create initial database schema tables")
        applied.add("v001_initial_schema")

    # v002: Add funding_account_id to transactions table with FK and index
    if "v002_transactions_funding_account" not in applied:
        try:
            await session.execute(text("ALTER TABLE transactions ADD COLUMN funding_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL"))
            await session.commit()
        except Exception:
            await session.rollback()
        try:
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_funding_account_id ON transactions(funding_account_id)"))
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v002_transactions_funding_account", "Add funding_account_id to transactions table")
        applied.add("v002_transactions_funding_account")

    # v003: Add industry to assets table
    if "v003_assets_industry_column" not in applied:
        try:
            await session.execute(text("ALTER TABLE assets ADD COLUMN industry VARCHAR"))
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v003_assets_industry_column", "Add industry column to assets table")
        applied.add("v003_assets_industry_column")

    # v004: Add transaction_kind to cashflow_transactions table
    if "v004_cashflow_transaction_kind" not in applied:
        try:
            await session.execute(text("ALTER TABLE cashflow_transactions ADD COLUMN transaction_kind VARCHAR"))
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v004_cashflow_transaction_kind", "Add transaction_kind column to cashflow_transactions table")
        applied.add("v004_cashflow_transaction_kind")

    # v005: Migrate legacy unsigned cashflow payments to signed convention (one-time)
    if "v005_signed_cashflow_amounts" not in applied:
        from app.db.models import CashflowPayment, CashflowTransaction, CashflowItem
        stmt = (
            select(CashflowPayment, CashflowTransaction)
            .join(CashflowTransaction, CashflowPayment.cashflow_id == CashflowTransaction.cashflow_id)
            .options(selectinload(CashflowTransaction.items).selectinload(CashflowItem.category))
        )
        res = await session.execute(stmt)
        migrated_count = 0
        for pmt, ctx in res.all():
            is_trans = any(i.category and i.category.category_type == "TRANSFER" for i in ctx.items)
            is_inc = not is_trans and (
                any(i.category and i.category.category_type == "INCOME" for i in ctx.items) or
                ctx.transaction_kind == "INCOME"
            )
            if not is_trans and not is_inc and pmt.amount > 0:
                pmt.amount = -abs(pmt.amount)
                migrated_count += 1
        if migrated_count > 0:
            await session.commit()
        await mark_migration_applied(session, "v005_signed_cashflow_amounts", "Migrate legacy unsigned cashflow payments to signed convention")
        applied.add("v005_signed_cashflow_amounts")
