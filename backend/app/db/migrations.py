import datetime
from typing import Set

from sqlalchemy import (
    Column, DateTime, MetaData, String, Table, inspect, select, update,
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
                        if ondelete:
                            ddl += f" ON DELETE {ondelete}"
                    sync_connection.exec_driver_sql(f"ALTER TABLE {table.name} ADD {ddl}")
                    existing_columns.add(column.name)
        # create_all() creates indexes for new tables; this also fills indexes
        # omitted from older installations where their table already existed.
        for table in get_tables_in_dependency_order():
            if table.name in existing_tables:
                for index in table.indexes:
                    index.create(sync_connection, checkfirst=True)

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


async def run_db_migrations(session: AsyncSession) -> None:
    """Bring the database to the current ORM schema using dialect-portable DDL."""
    await init_migrations_table(session)
    applied = await get_applied_migrations(session)
    await _ensure_latest_schema(session)

    for version, description in _VERSIONS:
        if version in applied:
            continue
        if version == "v005_signed_cashflow_amounts":
            await _migrate_legacy_cashflow_signs(session)
        await mark_migration_applied(session, version, description)
        applied.add(version)
