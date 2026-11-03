"""One-time migration of Greenline rows from SQLite into an empty Oracle schema."""
import asyncio
import os
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import (
    create_database_engine, get_tables_in_dependency_order,
    sync_oracle_identity_values,
)
from app.db import models  # noqa: F401 - ensure every ORM table is registered


def _tables_in_copy_order() -> list:
    # SQLAlchemy sorts foreign-key dependencies. The app has one nullable
    # expected-dividend/transaction cycle, handled with a second update pass.
    return get_tables_in_dependency_order()


async def copy_database(source_sessionmaker, target_sessionmaker, batch_size: int = 500) -> dict:
    """Copy all mapped rows, preserving IDs; target must already have an empty schema."""
    tables = _tables_in_copy_order()
    async with target_sessionmaker() as target:
        connection = await target.connection()
        counts = await connection.run_sync(
            lambda sync_connection: {
                table.name: sync_connection.execute(select(func.count()).select_from(table)).scalar_one()
                for table in tables
            }
        )
        if any(counts.values()):
            raise ValueError("Oracle target must be empty before migration.")

        copied_tables = set()
        deferred_updates = []
        source_counts = {}
        async with source_sessionmaker() as source:
            try:
                for table in tables:
                    result = await source.execute(select(table))
                    rows = [dict(row) for row in result.mappings().all()]
                    source_counts[table.name] = len(rows)
                    primary_keys = [column.name for column in table.primary_key.columns]
                    fk_targets = {
                        fk.parent.name: fk.column.table.name
                        for fk in table.foreign_keys
                    }
                    immediate_rows = []
                    for row in rows:
                        delayed = {}
                        for column_name, target_table in fk_targets.items():
                            if target_table not in copied_tables and row.get(column_name) is not None:
                                column = table.c[column_name]
                                if not column.nullable:
                                    raise ValueError(
                                        f"Cannot copy required circular reference {table.name}.{column_name}."
                                    )
                                delayed[column_name] = row[column_name]
                                row[column_name] = None
                        immediate_rows.append(row)
                        if delayed:
                            key = {name: row[name] for name in primary_keys}
                            deferred_updates.append((table, key, delayed))

                    for start in range(0, len(immediate_rows), batch_size):
                        await target.execute(table.insert(), immediate_rows[start:start + batch_size])
                    copied_tables.add(table.name)

                for table, key, values in deferred_updates:
                    await target.execute(table.update().where(
                        *[table.c[name] == value for name, value in key.items()]
                    ).values(**values))

                await target.commit()
                await sync_oracle_identity_values(target)
                await target.commit()
            except Exception:
                await target.rollback()
                raise

        copied_counts = {}
        for table in tables:
            copied_counts[table.name] = await target.scalar(select(func.count()).select_from(table))
        if copied_counts != source_counts:
            raise RuntimeError("Migration verification failed: source and target row counts differ.")
        return copied_counts


async def main() -> None:
    source_url = os.environ.get("SQLITE_SOURCE_URL")
    target_url = (
        os.environ.get("ORACLE_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ("oracle+oracledb://@" if os.environ.get("ORACLE_DSN") else None)
    )
    if not source_url or not source_url.startswith("sqlite"):
        raise SystemExit("Set SQLITE_SOURCE_URL to the source SQLite URL.")
    if not target_url or not target_url.startswith("oracle+oracledb://"):
        raise SystemExit("Set ORACLE_DATABASE_URL to an oracle+oracledb SQLAlchemy URL.")

    source_engine = create_database_engine(source_url)
    target_engine = create_database_engine(target_url)
    source_sessionmaker = async_sessionmaker(source_engine, expire_on_commit=False)
    target_sessionmaker = async_sessionmaker(target_engine, expire_on_commit=False)
    try:
        counts = await copy_database(source_sessionmaker, target_sessionmaker)
        print(f"Copied {sum(counts.values())} rows across {len(counts)} tables.")
        for table_name, count in counts.items():
            print(f"{table_name}: {count}")
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
