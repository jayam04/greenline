import datetime
from typing import Set

from sqlalchemy import (
    Column, DateTime, MetaData, String, Table, inspect, select, update, text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateColumn

from app.db.database import Base, get_tables_in_dependency_order
from app.db.models import CashflowItem, CashflowPayment, CashflowTransaction, Category


_migration_metadata = MetaData()
_migrations_table = Table(
    "schema_migrations",
    _migration_metadata,
    Column("version", String(128), primary_key=True),
    Column("description", String(255)),
    Column("applied_at", DateTime),
)
_VERSIONS = (
    ("v001_initial_schema", "Create initial database schema tables"),
    ("v002_transactions_funding_account", "Add funding_account_id to transactions table"),
    ("v003_assets_industry_column", "Add industry to assets table"),
    ("v004_cashflow_transaction_kind", "Add transaction_kind to cashflow_transactions table"),
    ("v005_signed_cashflow_amounts", "Migrate legacy unsigned cashflow payments to signed convention"),
    ("v006_transaction_source_column", "Add source to transactions table"),
    ("v007_account_default_dividend_account", "Add default_dividend_account_id to accounts table"),
    ("v008_expected_dividends_table", "Create expected dividends schema"),
    ("v009_ai_import_staging_tables", "Create import staging schema"),
    ("v010_api_keys_table", "Create API keys schema"),
    ("v011_user_row_level_security", "Add user_id to all user entities with default 0"),
    ("v012_auth0_user_persistence", "Add Auth0 profile fields (sub, email, name, picture) to users table"),
    ("v013_relax_password_hash_nullability", "Relax password_hash nullability on users table for Auth0 users"),
)


async def _ensure_latest_schema(session: AsyncSession) -> None:
    """Create missing tables/columns/indexes with the active SQLAlchemy dialect."""
    connection = await session.connection()
    await connection.run_sync(Base.metadata.create_all)

    def add_missing_columns(sync_connection):
        inspector = inspect(sync_connection)
        existing_tables = set(inspector.get_table_names())
        for table in get_tables_in_dependency_order():
            if table.name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_columns:
                    ddl = str(CreateColumn(column).compile(dialect=sync_connection.dialect))
                    for foreign_key in column.foreign_keys:
                        constraint = foreign_key.constraint
                        if constraint.name:
                            ddl += f" CONSTRAINT {constraint.name}"
                        ddl += f" REFERENCES {foreign_key.column.table.name} ({foreign_key.column.name})"
                        ondelete = constraint.ondelete
                        if ondelete and ondelete.upper() != "RESTRICT":
                            ddl += f" ON DELETE {ondelete}"
                    sync_connection.exec_driver_sql(f"ALTER TABLE {table.name} ADD {ddl}")
                    existing_columns.add(column.name)
        # create_all() creates indexes for new tables; this also fills indexes
        # omitted from older installations where their table already existed.
        for table in get_tables_in_dependency_order():
            if table.name in existing_tables:
                for index in table.indexes:
                    try:
                        index.create(sync_connection, checkfirst=True)
                    except Exception:
                        pass

    await connection.run_sync(add_missing_columns)
    await session.commit()


async def init_migrations_table(session: AsyncSession) -> None:
    """Create the migration tracking table if needed on the active database."""
    connection = await session.connection()
    await connection.run_sync(lambda sync_connection: _migrations_table.create(sync_connection, checkfirst=True))
    await session.commit()


async def get_applied_migrations(session: AsyncSession) -> Set[str]:
    await init_migrations_table(session)
    result = await session.execute(select(_migrations_table.c.version))
    return set(result.scalars().all())


async def mark_migration_applied(session: AsyncSession, version: str, description: str) -> None:
    await session.execute(
        _migrations_table.insert().values(
            version=version,
            description=description,
            applied_at=datetime.datetime.utcnow(),
        )
    )
    await session.commit()


async def _migrate_legacy_cashflow_signs(session: AsyncSession) -> None:
    rows = await session.execute(
        select(
            CashflowPayment.payment_id,
            CashflowPayment.cashflow_id,
            CashflowPayment.amount,
            CashflowTransaction.transaction_kind,
        ).join(CashflowTransaction, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
    )
    item_rows = await session.execute(
        select(CashflowItem.cashflow_id, Category.category_type)
        .join(Category, Category.category_id == CashflowItem.category_id)
    )
    types_by_cashflow = {}
    for cashflow_id, category_type in item_rows.all():
        types_by_cashflow.setdefault(cashflow_id, set()).add(category_type)

    for payment_id, cashflow_id, amount, kind in rows.all():
        item_types = types_by_cashflow.get(cashflow_id, set())
        is_income = "INCOME" in item_types or kind == "INCOME"
        is_transfer = "TRANSFER" in item_types
        if not is_income and not is_transfer and amount > 0:
            await session.execute(
                update(CashflowPayment)
                .where(CashflowPayment.payment_id == payment_id)
                .values(amount=-abs(amount))
            )
    await session.commit()


async def _migrate_user_rls(session: AsyncSession) -> None:
    from app.db.models import User
    from app.config import settings

    admin_res = await session.execute(select(User).order_by(User.user_id.asc()))
    users = admin_res.scalars().all()
    if not users:
        return

    table_names = [
        "accounts", "transactions", "lots", "lot_sales", "dividends",
        "expected_dividends", "cash_flows", "networth_snapshots",
        "networth_by_asset_class", "categories", "cashflow_transactions",
        "cashflow_payments", "cashflow_items", "app_settings",
        "xirr_cache", "price_history", "api_keys"
    ]

    res = await session.execute(select(User).where(User.user_id == 0))
    user0 = res.scalars().first()
    if not user0:
        admin_existing = next((u for u in users if u.username == settings.DEFAULT_ADMIN_USER), users[0])
        old_uid = admin_existing.user_id
        if old_uid != 0:
            target_username = admin_existing.username
            target_pwd = admin_existing.password_hash
            target_created = admin_existing.created_at or datetime.datetime.utcnow()

            # 1. Rename existing user temporarily to avoid unique username collisions
            await session.execute(
                text("UPDATE users SET username = :temp_name WHERE user_id = :old_uid"),
                {"temp_name": f"{target_username}_migrating", "old_uid": old_uid}
            )
            # 2. Insert new user 0 with target credentials so parent key exists
            await session.execute(
                text("INSERT INTO users (user_id, username, password_hash, created_at) "
                     "VALUES (0, :uname, :pwd, :created)"),
                {
                    "uname": target_username,
                    "pwd": target_pwd,
                    "created": target_created,
                }
            )
            # 3. Update all child tables pointing to old_uid to 0
            for tname in table_names:
                try:
                    await session.execute(
                        text(f"UPDATE {tname} SET user_id = 0 WHERE user_id = :old_uid"),
                        {"old_uid": old_uid}
                    )
                except Exception:
                    pass
            # 4. Safely delete the temporary user
            await session.execute(
                text("DELETE FROM users WHERE user_id = :old_uid"),
                {"old_uid": old_uid}
            )
            await session.commit()

    for tname in table_names:
        try:
            await session.execute(text(f"UPDATE {tname} SET user_id = 0 WHERE user_id IS NULL"))
        except Exception:
            pass
    await session.commit()


import logging

logger = logging.getLogger(__name__)

def _is_insufficient_privileges_error(e: Exception) -> bool:
    err_str = str(e).lower()
    return "ora-01031" in err_str or "insufficient privileges" in err_str


async def _migrate_auth0_user_persistence(session: AsyncSession) -> None:
    """Relax password_hash nullability and backfill updated_at for existing users."""
    try:
        bind = getattr(session, "bind", None)
        if bind is None and hasattr(session, "get_bind"):
            bind = session.get_bind()
        if bind and hasattr(bind, "dialect") and getattr(bind.dialect, "name", "") == "oracle":
            await session.execute(text("ALTER TABLE users MODIFY (password_hash NULL)"))
    except Exception as e:
        if not _is_insufficient_privileges_error(e):
            pass
    try:
        await session.execute(
            text("UPDATE users SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
        )
    except Exception:
        pass
    try:
        await session.commit()
    except Exception:
        pass


async def _migrate_relax_password_hash_nullability(session: AsyncSession) -> None:
    """Ensure password_hash column in users table allows NULL across all database dialects."""
    connection = await session.connection()
    def do_alter(sync_conn):
        dialect_name = getattr(sync_conn.dialect, "name", "")
        if dialect_name == "oracle":
            try:
                sync_conn.execute(text("ALTER TABLE users MODIFY (password_hash NULL)"))
            except Exception:
                pass
        elif dialect_name == "postgresql":
            try:
                sync_conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
            except Exception:
                pass
    try:
        await connection.run_sync(do_alter)
        await session.commit()
    except Exception as e:
        if not _is_insufficient_privileges_error(e):
            pass


async def run_db_migrations(session: AsyncSession) -> None:
    """Bring the database to the current ORM schema using dialect-portable DDL."""
    try:
        await init_migrations_table(session)
        applied = await get_applied_migrations(session)
    except Exception as e:
        if _is_insufficient_privileges_error(e):
            logger.info("Connected as DML-only user. Skipping DDL schema migrations.")
            return
        raise

    try:
        await _ensure_latest_schema(session)
    except Exception as e:
        if _is_insufficient_privileges_error(e):
            logger.info("Connected as DML-only user. Skipping DDL table/column creation.")
        else:
            raise

    for version, description in _VERSIONS:
        if version in applied:
            continue
        try:
            if version == "v005_signed_cashflow_amounts":
                await _migrate_legacy_cashflow_signs(session)
            elif version == "v011_user_row_level_security":
                await _migrate_user_rls(session)
            elif version == "v012_auth0_user_persistence":
                await _migrate_auth0_user_persistence(session)
            elif version == "v013_relax_password_hash_nullability":
                await _migrate_relax_password_hash_nullability(session)
            await mark_migration_applied(session, version, description)
            applied.add(version)
        except Exception as e:
            if _is_insufficient_privileges_error(e):
                logger.info(f"Connected as DML-only user. Skipping DDL migration {version}.")
            else:
                raise
