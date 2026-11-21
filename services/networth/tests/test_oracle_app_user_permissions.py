import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import DBAPIError
from app.config import Settings
from app.db.migrations import run_db_migrations


def test_oracle_schema_configuration():
    """Verify ORACLE_SCHEMA setting is respected in Settings."""
    with patch.dict(os.environ, {"ORACLE_SCHEMA": "ADMIN"}):
        s = Settings()
        assert s.ORACLE_SCHEMA == "ADMIN"

    with patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.ORACLE_SCHEMA is None


@pytest.mark.anyio
async def test_run_db_migrations_graceful_on_insufficient_privileges():
    """Verify run_db_migrations does not crash when connected as a DML-only user (ORA-01031)."""
    mock_session = AsyncMock()

    # Simulate ORA-01031: insufficient privileges when attempting DDL
    orig_exc = Exception("ORA-01031: insufficient privileges")
    dbapi_error = DBAPIError("ALTER TABLE users MODIFY (password_hash NULL)", {}, orig_exc)

    async def fail_on_ddl(*args, **kwargs):
        sql = str(args[0]) if args else ""
        if "ALTER TABLE" in sql or "CREATE TABLE" in sql:
            raise dbapi_error
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["v001_initial_schema"]
        return mock_result

    mock_session.execute = AsyncMock(side_effect=fail_on_ddl)
    mock_session.connection = AsyncMock()

    # Should catch ORA-01031 and proceed gracefully without raising
    await run_db_migrations(mock_session)


def test_setup_app_user_sql_contains_all_tables():
    """Ensure the SQL script grants permissions on all 21 Greenline tables."""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_app_user.sql")
    assert os.path.exists(sql_path), "setup_app_user.sql must exist"

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    expected_tables = [
        "users", "accounts", "assets", "transactions", "lots", "lot_sales",
        "price_history", "dividends", "expected_dividends", "cash_flows",
        "networth_snapshots", "networth_by_asset_class", "benchmarks", "xirr_cache",
        "categories", "cashflow_transactions", "cashflow_payments", "cashflow_items",
        "app_settings", "api_keys", "schema_migrations"
    ]

    for table in expected_tables:
        assert f"ADMIN.{table}" in content, f"Table {table} must be granted in setup_app_user.sql"

    # Must contain CURRENT_SCHEMA trigger
    assert "ALTER SESSION SET CURRENT_SCHEMA = ADMIN" in content
    # Must NOT grant DDL privileges like CREATE TABLE or DROP ANY TABLE
    assert "GRANT CREATE TABLE" not in content
    assert "GRANT DROP" not in content
