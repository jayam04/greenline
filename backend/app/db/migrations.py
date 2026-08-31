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
        try:
            res = await session.execute(text("""
                SELECT cp.payment_id, cp.amount, ct.transaction_kind,
                       EXISTS(
                           SELECT 1 FROM cashflow_items ci 
                           JOIN categories c ON ci.category_id = c.category_id 
                           WHERE ci.cashflow_id = cp.cashflow_id AND c.category_type = 'TRANSFER'
                       ) as has_transfer,
                       EXISTS(
                           SELECT 1 FROM cashflow_items ci 
                           JOIN categories c ON ci.category_id = c.category_id 
                           WHERE ci.cashflow_id = cp.cashflow_id AND c.category_type = 'INCOME'
                       ) as has_income
                FROM cashflow_payments cp
                JOIN cashflow_transactions ct ON cp.cashflow_id = ct.cashflow_id
            """))
            for row in res.all():
                pmt_id, amt, kind, has_trans, has_inc = row
                is_income = bool(has_inc) or (kind == "INCOME")
                if not bool(has_trans) and not is_income and amt > 0:
                    await session.execute(
                        text("UPDATE cashflow_payments SET amount = :new_amt WHERE payment_id = :pid"),
                        {"new_amt": -abs(amt), "pid": pmt_id}
                    )
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v005_signed_cashflow_amounts", "Migrate legacy unsigned cashflow payments to signed convention")
        applied.add("v005_signed_cashflow_amounts")

    # v006: Add source column to transactions table
    if "v006_transaction_source_column" not in applied:
        try:
            await session.execute(text("ALTER TABLE transactions ADD COLUMN source VARCHAR DEFAULT 'manual'"))
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v006_transaction_source_column", "Add source column to transactions table")
        applied.add("v006_transaction_source_column")

    # v007: Add default_dividend_account_id to accounts table
    if "v007_account_default_dividend_account" not in applied:
        try:
            await session.execute(text("ALTER TABLE accounts ADD COLUMN default_dividend_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL"))
            await session.commit()
        except Exception:
            await session.rollback()
        try:
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_accounts_default_dividend_account_id ON accounts(default_dividend_account_id)"))
            await session.commit()
        except Exception:
            await session.rollback()
        await mark_migration_applied(session, "v007_account_default_dividend_account", "Add default_dividend_account_id to accounts table")
        applied.add("v007_account_default_dividend_account")

    # v008: Add expected_dividends table and expected_dividend_id column to transactions table
    if "v008_expected_dividends_table" not in applied:
        try:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS expected_dividends (
                    expected_dividend_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
                    ex_date DATE NOT NULL,
                    pay_date DATE,
                    eligible_shares FLOAT NOT NULL DEFAULT 0.0,
                    dividend_rate FLOAT NOT NULL DEFAULT 0.0,
                    expected_amount FLOAT NOT NULL DEFAULT 0.0,
                    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    source VARCHAR DEFAULT 'yfinance',
                    matched_transaction_id INTEGER REFERENCES transactions(transaction_id) ON DELETE SET NULL,
                    status VARCHAR NOT NULL DEFAULT 'UNMATCHED',
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            await session.commit()
        except Exception:
            await session.rollback()

        try:
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_asset_id ON expected_dividends(asset_id)"))
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_account_id ON expected_dividends(account_id)"))
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_ex_date ON expected_dividends(ex_date)"))
            await session.commit()
        except Exception:
            await session.rollback()

        try:
            await session.execute(text("ALTER TABLE transactions ADD COLUMN expected_dividend_id INTEGER REFERENCES expected_dividends(expected_dividend_id) ON DELETE SET NULL"))
            await session.commit()
        except Exception:
            await session.rollback()

        try:
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_expected_dividend_id ON transactions(expected_dividend_id)"))
            await session.commit()
        except Exception:
            await session.rollback()

        await mark_migration_applied(session, "v008_expected_dividends_table", "Create expected_dividends table and add expected_dividend_id to transactions")
        applied.add("v008_expected_dividends_table")

