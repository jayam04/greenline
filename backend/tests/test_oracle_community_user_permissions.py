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


COMMUNITY_ALLOWED_TABLES = [
    "community_posts",
    "community_comments",
]

CORE_FINANCIAL_TABLES = [
    "users",
    "accounts",
    "assets",
    "transactions",
    "lots",
    "lot_sales",
    "price_history",
    "dividends",
    "expected_dividends",
    "cash_flows",
    "cashflow_transactions",
    "cashflow_payments",
    "cashflow_items",
    "categories",
    "networth_snapshots",
    "networth_by_asset_class",
    "xirr_cache",
    "benchmarks",
    "app_settings",
    "api_keys",
    "schema_migrations",
]

CONCEPTUAL_FINANCIAL_ALIASES = [
    "holdings",
    "portfolios",
]

COMMUNITY_TEST_USER = "GREENLINE_COMMUNITY"
COMMUNITY_TEST_PASS = os.getenv("COMMUNITY_DB_PASSWORD", "SecureCommunity2026#DbPass")
ORACLE_TEST_DSN = os.getenv("ORACLE_TEST_DSN", os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1"))


def get_setup_sql_paths():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_sql = os.path.join(repo_root, "scripts", "setup_community_user.sql")
    backend_sql = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_community_user.sql")
    return root_sql, backend_sql


def get_create_script_paths():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_py = os.path.join(repo_root, "scripts", "create_db_community_user.py")
    backend_py = os.path.join(os.path.dirname(__file__), "..", "scripts", "create_db_community_user.py")
    return root_py, backend_py


def test_setup_community_user_sql_file_exists():
    """Verify that scripts/setup_community_user.sql exists at expected path(s)."""
    root_sql, backend_sql = get_setup_sql_paths()
    assert os.path.exists(root_sql) or os.path.exists(backend_sql), (
        f"setup_community_user.sql must exist at {root_sql} or {backend_sql}"
    )


def test_create_db_community_user_script_exists():
    """Verify that scripts/create_db_community_user.py exists at expected path(s)."""
    root_py, backend_py = get_create_script_paths()
    assert os.path.exists(root_py) or os.path.exists(backend_py), (
        f"create_db_community_user.py must exist at {root_py} or {backend_py}"
    )


def test_setup_community_user_sql_static_privileges():
    """Verify scripts/setup_community_user.sql enforces least-privilege security specifications."""
    root_sql, backend_sql = get_setup_sql_paths()
    sql_path = root_sql if os.path.exists(root_sql) else backend_sql
    assert os.path.exists(sql_path), f"SQL script not found at {sql_path}"

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip SQL comments for pure statement inspection
    clean_sql = re.sub(r"--.*$", "", content, flags=re.MULTILINE)
    clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)

    # 1. User creation and connection capability only
    assert "CREATE USER GREENLINE_COMMUNITY" in clean_sql
    assert "GRANT CREATE SESSION TO GREENLINE_COMMUNITY" in clean_sql

    # 2. SELECT, INSERT, UPDATE, DELETE on community tables
    for table in COMMUNITY_ALLOWED_TABLES:
        pattern = rf"GRANT\s+[^;]*\bSELECT\b[^;]*\bINSERT\b[^;]*\bUPDATE\b[^;]*\bDELETE\b[^;]*\b(?:ADMIN|GREENLINE_TEST)\.{table}\b\s+TO\s+GREENLINE_COMMUNITY"
        assert re.search(
            pattern,
            clean_sql,
            re.IGNORECASE,
        ), f"SELECT, INSERT, UPDATE, DELETE must be granted on {table} to GREENLINE_COMMUNITY"

    # 3. Core financial tables must NOT receive any grant
    for table in CORE_FINANCIAL_TABLES:
        assert not re.search(
            rf"GRANT\s+[^;]*\b(?:ADMIN|GREENLINE_TEST)\.{table}\b\s+TO\s+GREENLINE_COMMUNITY",
            clean_sql,
            re.IGNORECASE,
        ), f"Core financial table {table} must NOT be granted to GREENLINE_COMMUNITY"

    # 4. Zero DDL privileges (No CREATE TABLE, DROP, ALTER)
    assert not re.search(r"GRANT\s+CREATE\s+TABLE", clean_sql, re.IGNORECASE)
    assert not re.search(r"GRANT\s+DROP", clean_sql, re.IGNORECASE)
    assert not re.search(r"GRANT\s+ALTER", clean_sql, re.IGNORECASE)

    # 5. AFTER LOGON trigger setting CURRENT_SCHEMA
    assert "ALTER SESSION SET CURRENT_SCHEMA" in clean_sql


@pytest.fixture(scope="session")
def oracle_community_db_user():
    """
    Session fixture that provisions GREENLINE_COMMUNITY user in local test Oracle container
    according to least-privilege specifications if Oracle is available.
    """
    if not ORACLEDB_AVAILABLE:
        pytest.skip("oracledb is not installed")

    # Connect as system / DBA user to provision GREENLINE_COMMUNITY in FREEPDB1
    try:
        dba_conn = oracledb.connect(
            user=os.getenv("ORACLE_ADMIN_USER", "system"),
            password=os.getenv("ORACLE_ADMIN_PASSWORD", "test_password"),
            dsn=ORACLE_TEST_DSN,
        )
    except Exception as e:
        pytest.skip(f"Local Oracle DB container not accessible ({e})")

    cursor = dba_conn.cursor()

    try:
        # Detect available permanent tablespace
        cursor.execute(
            "SELECT property_value FROM database_properties WHERE property_name = 'DEFAULT_PERMANENT_TABLESPACE'"
        )
        row = cursor.fetchone()
        default_ts = row[0] if row else "USERS"

        # Detect schema owner: check where USERS or SCHEMA_MIGRATIONS exists
        cursor.execute(
            "SELECT owner FROM all_tables WHERE table_name = 'USERS' AND owner IN ('GREENLINE_TEST', 'ADMIN')"
        )
        row = cursor.fetchone()
        schema_owner = row[0] if row else os.getenv("ORACLE_SCHEMA", "GREENLINE_TEST")

        # Ensure community tables exist in schema_owner
        cursor.execute(
            "SELECT table_name FROM all_tables WHERE owner = :o AND table_name = 'COMMUNITY_POSTS'",
            o=schema_owner,
        )
        if not cursor.fetchone():
            cursor.execute(f"""
            CREATE TABLE {schema_owner}.community_posts (
                id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                user_id VARCHAR2(255) NOT NULL,
                author_pseudonym VARCHAR2(100) NOT NULL,
                content CLOB NOT NULL,
                media_attachments CLOB,
                comments_count NUMBER DEFAULT 0 NOT NULL,
                created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
            )
            """)

        cursor.execute(
            "SELECT table_name FROM all_tables WHERE owner = :o AND table_name = 'COMMUNITY_COMMENTS'",
            o=schema_owner,
        )
        if not cursor.fetchone():
            cursor.execute(f"""
            CREATE TABLE {schema_owner}.community_comments (
                id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                post_id NUMBER NOT NULL REFERENCES {schema_owner}.community_posts(id) ON DELETE CASCADE,
                parent_comment_id NUMBER REFERENCES {schema_owner}.community_comments(id) ON DELETE CASCADE,
                user_id VARCHAR2(255) NOT NULL,
                author_pseudonym VARCHAR2(100) NOT NULL,
                content CLOB NOT NULL,
                created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
            )
            """)

        # Check if user exists; if so update password, otherwise create
        cursor.execute("SELECT username FROM all_users WHERE username = :u", u=COMMUNITY_TEST_USER)
        if cursor.fetchone():
            cursor.execute(f'ALTER USER {COMMUNITY_TEST_USER} IDENTIFIED BY "{COMMUNITY_TEST_PASS}"')
        else:
            cursor.execute(
                f'CREATE USER {COMMUNITY_TEST_USER} IDENTIFIED BY "{COMMUNITY_TEST_PASS}" '
                f'DEFAULT TABLESPACE {default_ts} TEMPORARY TABLESPACE TEMP QUOTA UNLIMITED ON {default_ts}'
            )

        # Grant CREATE SESSION ONLY (zero DDL)
        cursor.execute(f"GRANT CREATE SESSION TO {COMMUNITY_TEST_USER}")

        # Grant SELECT, INSERT, UPDATE, DELETE on community tables
        for table in COMMUNITY_ALLOWED_TABLES:
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {schema_owner}.{table} TO {COMMUNITY_TEST_USER}")

        # Ensure no grants exist on core financial tables for this user
        for table in CORE_FINANCIAL_TABLES:
            try:
                cursor.execute(f"REVOKE ALL ON {schema_owner}.{table} FROM {COMMUNITY_TEST_USER}")
            except Exception:
                pass

        # Create AFTER LOGON trigger to set CURRENT_SCHEMA = schema_owner
        trigger_sql = f"""
        CREATE OR REPLACE TRIGGER {COMMUNITY_TEST_USER}.set_current_schema
        AFTER LOGON ON {COMMUNITY_TEST_USER}.SCHEMA
        BEGIN
          EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = {schema_owner}';
        END;
        """
        cursor.execute(trigger_sql)
        dba_conn.commit()

        yield {
            "user": COMMUNITY_TEST_USER,
            "password": COMMUNITY_TEST_PASS,
            "dsn": ORACLE_TEST_DSN,
            "schema": schema_owner,
        }

    finally:
        cursor.close()
        dba_conn.close()


def test_oracle_community_user_connection_and_schema_resolution(oracle_community_db_user):
    """Verify GREENLINE_COMMUNITY connects and AFTER LOGON trigger sets CURRENT_SCHEMA."""
    conn = oracledb.connect(
        user=oracle_community_db_user["user"],
        password=oracle_community_db_user["password"],
        dsn=oracle_community_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        # Check current session schema matches schema_owner without explicit ALTER SESSION
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
        current_schema = cursor.fetchone()[0]
        assert current_schema == oracle_community_db_user["schema"], (
            f"Expected CURRENT_SCHEMA {oracle_community_db_user['schema']}, got {current_schema}"
        )

        # Query community tables without schema prefix
        for table in COMMUNITY_ALLOWED_TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count >= 0, f"Failed to select from {table} without prefix"
    finally:
        cursor.close()
        conn.close()


def test_oracle_community_user_posts_dml_lifecycle(oracle_community_db_user):
    """Verify GREENLINE_COMMUNITY has full DML (SELECT, INSERT, UPDATE, DELETE) on community_posts."""
    conn = oracledb.connect(
        user=oracle_community_db_user["user"],
        password=oracle_community_db_user["password"],
        dsn=oracle_community_db_user["dsn"],
    )
    cursor = conn.cursor()
    test_user_id = "auth0|test_community_user_001"
    post_id = None
    try:
        # 1. INSERT post
        post_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute(
            """
            INSERT INTO community_posts (
                user_id, author_pseudonym, content, media_attachments, comments_count
            ) VALUES (
                :user_id_val, :pseudo, :content, :media, :cc
            ) RETURNING id INTO :out_id
            """,
            user_id_val=test_user_id,
            pseudo="Giant Elephant",
            content="Hello Greenline community!",
            media='[{"url": "https://example.com/chart.png", "type": "image/png"}]',
            cc=0,
            out_id=post_id_var,
        )
        conn.commit()
        post_id = int(post_id_var.getvalue()[0])
        assert post_id > 0

        # 2. SELECT post
        cursor.execute(
            "SELECT author_pseudonym, content, comments_count FROM community_posts WHERE id = :pid",
            pid=post_id,
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Giant Elephant"
        content_val = row[1].read() if hasattr(row[1], "read") else row[1]
        assert content_val == "Hello Greenline community!"
        assert int(row[2]) == 0

        # 3. UPDATE post
        cursor.execute(
            "UPDATE community_posts SET content = :new_content, comments_count = 1 WHERE id = :pid",
            new_content="Updated Greenline community post!",
            pid=post_id,
        )
        conn.commit()

        cursor.execute("SELECT content, comments_count FROM community_posts WHERE id = :pid", pid=post_id)
        row = cursor.fetchone()
        content_val = row[0].read() if hasattr(row[0], "read") else row[0]
        assert content_val == "Updated Greenline community post!"
        assert int(row[1]) == 1

        # 4. DELETE post
        cursor.execute("DELETE FROM community_posts WHERE id = :pid", pid=post_id)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM community_posts WHERE id = :pid", pid=post_id)
        assert cursor.fetchone()[0] == 0
        post_id = None

    finally:
        if post_id is not None:
            try:
                cursor.execute("DELETE FROM community_posts WHERE id = :pid", pid=post_id)
                conn.commit()
            except Exception:
                pass
        cursor.close()
        conn.close()


def test_oracle_community_user_comments_dml_lifecycle(oracle_community_db_user):
    """Verify GREENLINE_COMMUNITY has full DML (SELECT, INSERT, UPDATE, DELETE) on community_comments with hierarchy."""
    conn = oracledb.connect(
        user=oracle_community_db_user["user"],
        password=oracle_community_db_user["password"],
        dsn=oracle_community_db_user["dsn"],
    )
    cursor = conn.cursor()
    test_user_id = "auth0|test_community_user_002"
    post_id = None
    parent_comment_id = None
    child_comment_id = None

    try:
        # Create a parent post first
        post_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute(
            """
            INSERT INTO community_posts (
                user_id, author_pseudonym, content
            ) VALUES (
                :user_id_val, :pseudo, :content
            ) RETURNING id INTO :out_id
            """,
            user_id_val=test_user_id,
            pseudo="Crazy Dog",
            content="Parent post for comment tests",
            out_id=post_id_var,
        )
        conn.commit()
        post_id = int(post_id_var.getvalue()[0])

        # 1. INSERT top-level comment
        comment_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute(
            """
            INSERT INTO community_comments (
                post_id, parent_comment_id, user_id, author_pseudonym, content
            ) VALUES (
                :pid, NULL, :user_id_val, :pseudo, :content
            ) RETURNING id INTO :out_id
            """,
            pid=post_id,
            user_id_val=test_user_id,
            pseudo="Crazy Dog",
            content="Top level comment",
            out_id=comment_id_var,
        )
        conn.commit()
        parent_comment_id = int(comment_id_var.getvalue()[0])
        assert parent_comment_id > 0

        # 2. INSERT child/nested comment
        child_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute(
            """
            INSERT INTO community_comments (
                post_id, parent_comment_id, user_id, author_pseudonym, content
            ) VALUES (
                :pid, :pcid, :user_id_val, :pseudo, :content
            ) RETURNING id INTO :out_id
            """,
            pid=post_id,
            pcid=parent_comment_id,
            user_id_val="auth0|user_reply",
            pseudo="Giant Elephant",
            content="Nested reply comment",
            out_id=child_id_var,
        )
        conn.commit()
        child_comment_id = int(child_id_var.getvalue()[0])
        assert child_comment_id > 0

        # 3. SELECT comments
        cursor.execute(
            "SELECT id, post_id, parent_comment_id, author_pseudonym, content FROM community_comments WHERE post_id = :pid ORDER BY id ASC",
            pid=post_id,
        )
        comments = cursor.fetchall()
        assert len(comments) == 2
        assert comments[0][2] is None
        assert comments[1][2] == parent_comment_id

        # 4. UPDATE comment
        cursor.execute(
            "UPDATE community_comments SET content = :new_content WHERE id = :cid",
            new_content="Updated nested reply",
            cid=child_comment_id,
        )
        conn.commit()
        cursor.execute("SELECT content FROM community_comments WHERE id = :cid", cid=child_comment_id)
        content_val = cursor.fetchone()[0]
        content_str = content_val.read() if hasattr(content_val, "read") else content_val
        assert content_str == "Updated nested reply"

        # 5. DELETE comments
        cursor.execute("DELETE FROM community_comments WHERE id = :cid", cid=child_comment_id)
        cursor.execute("DELETE FROM community_comments WHERE id = :cid", cid=parent_comment_id)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM community_comments WHERE post_id = :pid", pid=post_id)
        assert cursor.fetchone()[0] == 0

    finally:
        if post_id is not None:
            try:
                cursor.execute("DELETE FROM community_posts WHERE id = :pid", pid=post_id)
                conn.commit()
            except Exception:
                pass
        cursor.close()
        conn.close()


def test_oracle_community_user_forbidden_financial_tables_denial(oracle_community_db_user):
    """Verify GREENLINE_COMMUNITY has zero access to core financial tables (raises ORA-00942 or ORA-01031)."""
    conn = oracledb.connect(
        user=oracle_community_db_user["user"],
        password=oracle_community_db_user["password"],
        dsn=oracle_community_db_user["dsn"],
    )
    cursor = conn.cursor()
    all_forbidden = CORE_FINANCIAL_TABLES + CONCEPTUAL_FINANCIAL_ALIASES
    try:
        for table in all_forbidden:
            # 1. SELECT attempt
            with pytest.raises(oracledb.DatabaseError) as exc_info:
                cursor.execute(f"SELECT * FROM {table} WHERE ROWNUM <= 1")
            err, = exc_info.value.args
            assert any(code in str(err.message) for code in ["ORA-00942", "ORA-01031"]), (
                f"Expected ORA-00942 or ORA-01031 for table {table}, got {err.message}"
            )

            # 2. DELETE attempt
            with pytest.raises(oracledb.DatabaseError) as exc_info:
                cursor.execute(f"DELETE FROM {table}")
            err, = exc_info.value.args
            assert any(code in str(err.message) for code in ["ORA-00942", "ORA-01031"]), (
                f"Expected ORA-00942 or ORA-01031 for table {table}, got {err.message}"
            )
    finally:
        cursor.close()
        conn.close()


def test_oracle_community_user_zero_ddl_privileges(oracle_community_db_user):
    """Verify GREENLINE_COMMUNITY has zero DDL privileges (cannot CREATE/DROP/ALTER tables, ORA-01031)."""
    conn = oracledb.connect(
        user=oracle_community_db_user["user"],
        password=oracle_community_db_user["password"],
        dsn=oracle_community_db_user["dsn"],
    )
    cursor = conn.cursor()
    try:
        # Attempt CREATE TABLE
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("CREATE TABLE community_rogue_table (id NUMBER)")
        err, = exc_info.value.args
        assert "ORA-01031" in str(err.message), f"Expected ORA-01031 insufficient privileges, got {err.message}"

        # Attempt DROP TABLE on allowed table
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("DROP TABLE community_posts")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-00942"]), (
            f"Expected ORA-01031 or ORA-00942, got {err.message}"
        )

        # Attempt ALTER TABLE on allowed table
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cursor.execute("ALTER TABLE community_posts ADD (injected_column VARCHAR2(50))")
        err, = exc_info.value.args
        assert any(code in str(err.message) for code in ["ORA-01031", "ORA-00942"]), (
            f"Expected ORA-01031 or ORA-00942, got {err.message}"
        )
    finally:
        cursor.close()
        conn.close()
