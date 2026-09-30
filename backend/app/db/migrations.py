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
        cols_res = await session.execute(text("PRAGMA table_info(transactions)"))
        tx_cols = {row[1] for row in cols_res.all()}
        if "source" not in tx_cols:
            await session.execute(text("ALTER TABLE transactions ADD COLUMN source VARCHAR DEFAULT 'manual'"))
            await session.commit()
        await mark_migration_applied(session, "v006_transaction_source_column", "Add source column to transactions table")
        applied.add("v006_transaction_source_column")

    # v007: Add default_dividend_account_id to accounts table
    if "v007_account_default_dividend_account" not in applied:
        acc_cols_res = await session.execute(text("PRAGMA table_info(accounts)"))
        acc_cols = {row[1] for row in acc_cols_res.all()}
        if "default_dividend_account_id" not in acc_cols:
            await session.execute(text("ALTER TABLE accounts ADD COLUMN default_dividend_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL"))
            await session.commit()
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_accounts_default_dividend_account_id ON accounts(default_dividend_account_id)"))
        await session.commit()
        await mark_migration_applied(session, "v007_account_default_dividend_account", "Add default_dividend_account_id to accounts table")
        applied.add("v007_account_default_dividend_account")

    # v008: Add expected_dividends table and expected_dividend_id column to transactions table
    if "v008_expected_dividends_table" not in applied:
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
        await session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uix_expected_dividend_asset_account_date ON expected_dividends(asset_id, account_id, ex_date)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_asset_id ON expected_dividends(asset_id)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_account_id ON expected_dividends(account_id)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_expected_dividends_ex_date ON expected_dividends(ex_date)"))
        await session.commit()

        tx_cols_res = await session.execute(text("PRAGMA table_info(transactions)"))
        tx_cols = {row[1] for row in tx_cols_res.all()}
        if "expected_dividend_id" not in tx_cols:
            await session.execute(text("ALTER TABLE transactions ADD COLUMN expected_dividend_id INTEGER REFERENCES expected_dividends(expected_dividend_id) ON DELETE SET NULL"))
            await session.commit()

        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_expected_dividend_id ON transactions(expected_dividend_id)"))
        await session.commit()

        await mark_migration_applied(session, "v008_expected_dividends_table", "Create expected_dividends table and add expected_dividend_id to transactions")
        applied.add("v008_expected_dividends_table")

    # v009: Add AI import staging tables (import_batches, staged_records)
    if "v009_ai_import_staging_tables" not in applied:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS import_batches (
                batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename VARCHAR NOT NULL,
                file_type VARCHAR NOT NULL,
                file_size_bytes INTEGER DEFAULT 0,
                status VARCHAR NOT NULL DEFAULT 'processing',
                scope VARCHAR NOT NULL DEFAULT 'unified',
                target_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL,
                default_currency VARCHAR(3) DEFAULT 'USD',
                custom_instructions TEXT,
                progress_pct INTEGER DEFAULT 0,
                current_step VARCHAR,
                error_message TEXT,
                total_records INTEGER DEFAULT 0,
                new_records INTEGER DEFAULT 0,
                exact_matches INTEGER DEFAULT 0,
                probable_matches INTEGER DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS staged_records (
                staged_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES import_batches(batch_id) ON DELETE CASCADE,
                record_type VARCHAR NOT NULL,
                review_status VARCHAR NOT NULL DEFAULT 'pending',
                match_status VARCHAR NOT NULL DEFAULT 'new',
                matched_entity_id INTEGER,
                matched_entity_details TEXT,
                confidence_score FLOAT DEFAULT 1.0,
                transaction_date DATE NOT NULL,
                action_type VARCHAR NOT NULL,
                account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL,
                account_name_raw VARCHAR,
                asset_id INTEGER REFERENCES assets(asset_id) ON DELETE SET NULL,
                asset_symbol_raw VARCHAR,
                asset_name_raw VARCHAR,
                category_id INTEGER REFERENCES categories(category_id) ON DELETE SET NULL,
                category_name_raw VARCHAR,
                quantity FLOAT,
                price_per_unit FLOAT,
                total_amount FLOAT NOT NULL,
                fees FLOAT DEFAULT 0.0,
                taxes FLOAT DEFAULT 0.0,
                currency VARCHAR(3) DEFAULT 'USD',
                notes TEXT,
                source_raw_text TEXT
            )
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_staged_records_batch_id ON staged_records(batch_id)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_staged_records_batch_status ON staged_records(batch_id, review_status)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_staged_records_transaction_date ON staged_records(transaction_date)"))
        await session.commit()
        await mark_migration_applied(session, "v009_ai_import_staging_tables", "Create import_batches and staged_records tables")
        applied.add("v009_ai_import_staging_tables")

    # v010: Add api_keys table for MCP and agent authentication
    if "v010_api_keys_table" not in applied:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                name VARCHAR NOT NULL,
                key_prefix VARCHAR NOT NULL,
                key_hash VARCHAR NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used_at DATETIME
            )
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys(key_hash)"))
        await session.commit()
        await mark_migration_applied(session, "v010_api_keys_table", "Create api_keys table for MCP authentication")
        applied.add("v010_api_keys_table")


