import os
import re
import pytest

# Optional oracledb import for live DB tests
try:
    import oracledb
    ORACLEDB_AVAILABLE = True
except ImportError:
    oracledb = None
    ORACLEDB_AVAILABLE = False


ANALYTICAL_INPUT_TABLES = [
    "users",
    "accounts",
    "assets",
    "transactions",
    "lots",
    "lot_sales",
    "price_history",
    "dividends",
    "cash_flows",
    "cashflow_transactions",
    "cashflow_payments",
    "cashflow_items",
    "categories",
]

OUTPUT_CACHE_TABLES = [
    "networth_snapshots",
    "networth_by_asset_class",
    "xirr_cache",
    "benchmarks",
]

EXCLUDED_TABLES = [
    "api_keys",
    "app_settings",
    "expected_dividends",
    "schema_migrations",
]

NETWORTH_TEST_USER = "GREENLINE_NETWORTH"
NETWORTH_TEST_PASS = "SecureNetworth2026#DbPass"
ORACLE_TEST_DSN = os.getenv("ORACLE_TEST_DSN", "localhost:1521/FREEPDB1")


def get_setup_sql_paths():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_sql = os.path.join(repo_root, "scripts", "setup_networth_user.sql")
    backend_sql = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_networth_user.sql")
    return root_sql, backend_sql


def test_setup_networth_user_sql_file_exists():
    """Verify that scripts/setup_networth_user.sql exists at expected path(s)."""
    root_sql, backend_sql = get_setup_sql_paths()
    assert os.path.exists(root_sql) or os.path.exists(backend_sql), (
        f"setup_networth_user.sql must exist at {root_sql} or {backend_sql}"
    )


def test_setup_networth_user_sql_static_privileges():
    """Verify scripts/setup_networth_user.sql enforces least-privilege security specifications."""
    root_sql, backend_sql = get_setup_sql_paths()
    sql_path = root_sql if os.path.exists(root_sql) else backend_sql
    assert os.path.exists(sql_path), f"SQL script not found at {sql_path}"

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip SQL single-line and multi-line comments for pure DDL/DML statement inspection
    clean_sql = re.sub(r"--.*$", "", content, flags=re.MULTILINE)
    clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)

    # 1. User creation and connection capability only
    assert "CREATE USER GREENLINE_NETWORTH" in clean_sql
    assert "GRANT CREATE SESSION TO GREENLINE_NETWORTH" in clean_sql

    # 2. SELECT ONLY on all 13 Analytical Input Tables
    for table in ANALYTICAL_INPUT_TABLES:
        # Must have SELECT granted
        assert re.search(
            rf"GRANT\s+SELECT\s+ON\s+(?:ADMIN|GREENLINE_TEST)\.{table}\s+TO\s+GREENLINE_NETWORTH",
            clean_sql,
            re.IGNORECASE,
        ), f"SELECT must be granted on {table} to GREENLINE_NETWORTH"

        # Must NOT have INSERT, UPDATE, or DELETE granted on analytical input tables
        for forbidden_op in ["INSERT", "UPDATE", "DELETE"]:
            pattern = rf"GRANT\s+[^;]*\b{forbidden_op}\b[^;]*\b(?:ADMIN|GREENLINE_TEST)\.{table}\b\s+TO\s+GREENLINE_NETWORTH"
            assert not re.search(pattern, clean_sql, re.IGNORECASE), (
                f"{forbidden_op} must NOT be granted on analytical input table {table}"
            )

    # 3. SELECT, INSERT, UPDATE, DELETE on all 4 Output/Cache Tables
    for table in OUTPUT_CACHE_TABLES:
        pattern = rf"GRANT\s+[^;]*\bSELECT\b[^;]*\bINSERT\b[^;]*\bUPDATE\b[^;]*\bDELETE\b[^;]*\b(?:ADMIN|GREENLINE_TEST)\.{table}\b\s+TO\s+GREENLINE_NETWORTH"
        assert re.search(
            pattern,
            clean_sql,
            re.IGNORECASE,
        ), f"SELECT, INSERT, UPDATE, DELETE must be granted on {table} to GREENLINE_NETWORTH"

    # 4. Excluded tables must NOT receive any grant
    for table in EXCLUDED_TABLES:
        assert not re.search(
            rf"GRANT\s+[^;]*\b(?:ADMIN|GREENLINE_TEST)\.{table}\b\s+TO\s+GREENLINE_NETWORTH",
            clean_sql,
            re.IGNORECASE,
        ), f"Excluded table {table} must NOT be granted to GREENLINE_NETWORTH"

    # 5. Zero DDL privileges (No CREATE TABLE, DROP, ALTER)
    assert not re.search(r"GRANT\s+CREATE\s+TABLE", clean_sql, re.IGNORECASE)
    assert not re.search(r"GRANT\s+DROP", clean_sql, re.IGNORECASE)
    assert not re.search(r"GRANT\s+ALTER", clean_sql, re.IGNORECASE)

    # 6. AFTER LOGON trigger setting CURRENT_SCHEMA
    assert "ALTER SESSION SET CURRENT_SCHEMA" in clean_sql


@pytest.fixture(scope="session")
def oracle_networth_db_user():
    """
    Session fixture that provisions GREENLINE_NETWORTH user in local test Oracle container
    according to least-privilege specifications if Oracle is available.
    """
    if not ORACLEDB_AVAILABLE:
        pytest.skip("oracledb is not installed")

    # Connect as system / DBA user to provision GREENLINE_NETWORTH in FREEPDB1
    try:
        dba_conn = oracledb.connect(
            user=os.getenv("ORACLE_ADMIN_USER", "system"),
            password=os.getenv("ORACLE_ADMIN_PASSWORD", "test_password"),
            dsn=ORACLE_TEST_DSN,
        )
    except Exception as e:
        pytest.skip(f"Local Oracle DB container not accessible ({e})")

    cursor = dba_conn.cursor()
    schema_owner = "GREENLINE_TEST"

    try:
        # Detect available permanent tablespace
        cursor.execute(
            "SELECT property_value FROM database_properties WHERE property_name = 'DEFAULT_PERMANENT_TABLESPACE'"
        )
        row = cursor.fetchone()
        default_ts = row[0] if row else "USERS"

        # Check if user exists; if so update password, otherwise create
        cursor.execute("SELECT username FROM all_users WHERE username = :u", u=NETWORTH_TEST_USER)
        if cursor.fetchone():
            cursor.execute(f'ALTER USER {NETWORTH_TEST_USER} IDENTIFIED BY "{NETWORTH_TEST_PASS}"')
        else:
            cursor.execute(
                f'CREATE USER {NETWORTH_TEST_USER} IDENTIFIED BY "{NETWORTH_TEST_PASS}" '
                f'DEFAULT TABLESPACE {default_ts} TEMPORARY TABLESPACE TEMP QUOTA UNLIMITED ON {default_ts}'
            )

        # Grant CREATE SESSION ONLY (zero DDL)
        cursor.execute(f"GRANT CREATE SESSION TO {NETWORTH_TEST_USER}")

        # Grant SELECT ONLY on 13 input tables
        for table in ANALYTICAL_INPUT_TABLES:
            cursor.execute(f"GRANT SELECT ON {schema_owner}.{table} TO {NETWORTH_TEST_USER}")

        # Grant SELECT, INSERT, UPDATE, DELETE on 4 output tables
        for table in OUTPUT_CACHE_TABLES:
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {schema_owner}.{table} TO {NETWORTH_TEST_USER}")

        # Ensure no grants exist on excluded tables for this user
        for table in EXCLUDED_TABLES:
            try:
                cursor.execute(f"REVOKE ALL ON {schema_owner}.{table} FROM {NETWORTH_TEST_USER}")
            except Exception:
                pass

        # Create AFTER LOGON trigger to set CURRENT_SCHEMA = GREENLINE_TEST
        trigger_sql = f"""
        CREATE OR REPLACE TRIGGER {NETWORTH_TEST_USER}.set_current_schema
        AFTER LOGON ON {NETWORTH_TEST_USER}.SCHEMA
        BEGIN
          EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = {schema_owner}';
        END;
        """
        cursor.execute(trigger_sql)
        dba_conn.commit()

        yield {
            "user": NETWORTH_TEST_USER,
            "password": NETWORTH_TEST_PASS,
            "dsn": ORACLE_TEST_DSN,
            "schema": schema_owner,
        }

    finally:
        cursor.close()
        dba_conn.close()


def test_oracle_networth_user_connection_and_read_grants(oracle_networth_db_user):
    """Verify GREENLINE_NETWORTH can connect and execute SELECT on analytical input tables."""
    conn = oracledb.connect(
        user=oracle_networth_db_user["user"],
        password=oracle_networth_db_user["password"],
        dsn=oracle_networth_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        for table in ["transactions", "accounts", "assets", "users", "categories"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count >= 0, f"Failed to select from {table}"
    finally:
        cursor.close()
        conn.close()


def test_oracle_networth_user_output_table_dml_grants(oracle_networth_db_user):
    """Verify GREENLINE_NETWORTH has full DML (SELECT, INSERT, UPDATE, DELETE) on output tables."""
    conn = oracledb.connect(
        user=oracle_networth_db_user["user"],
        password=oracle_networth_db_user["password"],
        dsn=oracle_networth_db_user["dsn"],
    )
    cursor = conn.cursor()
    test_snapshot_id = 999988
    try:
        # 1. Clean up any stale record
        cursor.execute("DELETE FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
        conn.commit()

        # 2. INSERT
        cursor.execute(
            """
            INSERT INTO networth_snapshots (
                snapshot_id, user_id, snapshot_date, total_invested,
                total_current_value, cash_balance, total_realized_pnl,
                total_unrealized_pnl, net_worth
            ) VALUES (
                :sid, 0, DATE '2026-01-04', 1000.00,
                1200.00, 300.00, 50.00, 200.00, 1500.00
            )
            """,
            sid=test_snapshot_id,
        )
        conn.commit()

        # 3. SELECT
        cursor.execute("SELECT net_worth FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
        row = cursor.fetchone()
        assert row is not None
        assert float(row[0]) == 1500.00

        # 4. UPDATE
        cursor.execute(
            "UPDATE networth_snapshots SET net_worth = 1600.00 WHERE snapshot_id = :sid",
            sid=test_snapshot_id,
        )
        conn.commit()
        cursor.execute("SELECT net_worth FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
        assert float(cursor.fetchone()[0]) == 1600.00

        # 5. DELETE
        cursor.execute("DELETE FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
        assert cursor.fetchone()[0] == 0
    finally:
        # Final cleanup safety
        try:
            cursor.execute("DELETE FROM networth_snapshots WHERE snapshot_id = :sid", sid=test_snapshot_id)
            conn.commit()
        except Exception:
            pass
        cursor.close()
        conn.close()


def test_oracle_networth_user_forbidden_write_on_input_tables(oracle_networth_db_user):
    """Verify GREENLINE_NETWORTH is strictly forbidden from writing to input tables (ORA-01031 / ORA-41900)."""
    conn = oracledb.connect(
        user=oracle_networth_db_user["user"],
        password=oracle_networth_db_user["password"],
        dsn=oracle_networth_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        # Attempt DELETE on transactions
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("DELETE FROM transactions")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-41900"]), (
            f"Expected ORA-01031 or ORA-41900 insufficient privileges, got {err.message}"
        )

        # Attempt UPDATE on accounts
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("UPDATE accounts SET account_name = 'unauthorized'")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-41900"]), (
            f"Expected ORA-01031 or ORA-41900 insufficient privileges, got {err.message}"
        )

        # Attempt INSERT on users
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("INSERT INTO users (user_id, username, password_hash) VALUES (88888, 'bad', 'bad')")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-41900"]), (
            f"Expected ORA-01031 or ORA-41900 insufficient privileges, got {err.message}"
        )
    finally:
        cursor.close()
        conn.close()


def test_oracle_networth_user_forbidden_tables_rejection(oracle_networth_db_user):
    """Verify GREENLINE_NETWORTH has zero access to excluded tables (ORA-00942 table or view does not exist)."""
    conn = oracledb.connect(
        user=oracle_networth_db_user["user"],
        password=oracle_networth_db_user["password"],
        dsn=oracle_networth_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        for excluded_table in EXCLUDED_TABLES:
            with pytest.raises(oracledb.DatabaseError) as exc_info:
                cursor.execute(f"SELECT * FROM {excluded_table}")
            err, = exc_info.value.args
            assert any(code in str(err.message) for code in ["ORA-00942", "ORA-01031"]), (
                f"Expected ORA-00942 or ORA-01031 for excluded table {excluded_table}, got {err.message}"
            )
    finally:
        cursor.close()
        conn.close()


def test_oracle_networth_user_zero_ddl_privileges(oracle_networth_db_user):
    """Verify GREENLINE_NETWORTH has zero DDL privileges (cannot CREATE/DROP tables, ORA-01031)."""
    conn = oracledb.connect(
        user=oracle_networth_db_user["user"],
        password=oracle_networth_db_user["password"],
        dsn=oracle_networth_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        # Attempt CREATE TABLE
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("CREATE TABLE networth_rogue_table (id NUMBER)")
        err, = exc_info.value.args
        assert "ORA-01031" in str(err.message), f"Expected ORA-01031 insufficient privileges, got {err.message}"

        # Attempt DROP TABLE on an output table
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("DROP TABLE networth_snapshots")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-00942"]), (
            f"Expected ORA-01031 or ORA-00942, got {err.message}"
        )
    finally:
        cursor.close()
        conn.close()
