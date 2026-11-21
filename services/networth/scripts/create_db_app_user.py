#!/usr/bin/env python3
"""
Create Least-Privilege DML-Only Database User for Greenline
Connects using ADMIN credentials from .env and provisions a dedicated
application user with SELECT, INSERT, UPDATE, DELETE privileges on all 21 Greenline tables.
"""

import os
import sys
import argparse
import secrets
import string
import oracledb
from dotenv import load_dotenv

# Ensure root .env is loaded
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

ALL_GREENLINE_TABLES = [
    "users",
    "accounts",
    "categories",
    "assets",
    "transactions",
    "lots",
    "lot_sales",
    "price_history",
    "dividends",
    "expected_dividends",
    "cash_flows",
    "networth_snapshots",
    "networth_by_asset_class",
    "benchmarks",
    "xirr_cache",
    "cashflow_transactions",
    "cashflow_payments",
    "cashflow_items",
    "app_settings",
    "api_keys",
    "schema_migrations",
]


def generate_secure_oracle_password(length: int = 18) -> str:
    """Generate a password compliant with Oracle Autonomous Database password complexity rules."""
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    symbols = "#_$"
    sym = secrets.choice(symbols)
    all_chars = string.ascii_letters + string.digits + symbols
    rest = "".join(secrets.choice(all_chars) for _ in range(length - 4))
    return f"{upper}{lower}{digit}{sym}{rest}"


def clean_credential(val: str) -> str:
    if isinstance(val, str):
        return val.strip("\"' \t\r\n")
    return val


def main():
    parser = argparse.ArgumentParser(description="Create least-privilege Greenline application user in Oracle DB")
    parser.add_argument("--username", default="GREENLINE_APP", help="Name of application user to create (default: GREENLINE_APP)")
    parser.add_argument("--password", default=None, help="Password for application user (generated if not provided)")
    parser.add_argument("--schema", default=None, help="Schema containing tables (defaults to ADMIN user from .env)")
    args = parser.parse_args()

    admin_user = clean_credential(os.getenv("ORACLE_USER", "ADMIN"))
    admin_password = clean_credential(os.getenv("ORACLE_PASSWORD", ""))
    dsn = clean_credential(os.getenv("ORACLE_DSN", ""))
    target_schema = clean_credential(args.schema or admin_user or "ADMIN")

    if not admin_password or not dsn:
        print("[Error] Missing ORACLE_PASSWORD or ORACLE_DSN in .env file.")
        sys.exit(1)

    app_user = clean_credential(args.username).upper()
    app_password = args.password or generate_secure_oracle_password()

    print(f"[*] Connecting to Oracle Database as {admin_user}...")
    try:
        conn = oracledb.connect(user=admin_user, password=admin_password, dsn=dsn)
    except Exception as e:
        print(f"[Error] Failed to connect to Oracle as {admin_user}: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    try:
        # Check if user already exists
        cursor.execute("SELECT username FROM all_users WHERE username = :u", u=app_user)
        exists = cursor.fetchone() is not None

        if exists:
            print(f"[*] User {app_user} already exists. Updating password...")
            cursor.execute(f'ALTER USER {app_user} IDENTIFIED BY "{app_password}"')
        else:
            print(f"[*] Creating user {app_user}...")
            cursor.execute(
                f'CREATE USER {app_user} IDENTIFIED BY "{app_password}" '
                'DEFAULT TABLESPACE DATA TEMPORARY TABLESPACE TEMP QUOTA UNLIMITED ON DATA'
            )

        # Grant session connection only
        print(f"[*] Granting CREATE SESSION to {app_user}...")
        cursor.execute(f"GRANT CREATE SESSION TO {app_user}")

        # Grant DML permissions on all 21 tables
        print(f"[*] Granting SELECT, INSERT, UPDATE, DELETE on {len(ALL_GREENLINE_TABLES)} tables in {target_schema}...")
        granted_count = 0
        for table in ALL_GREENLINE_TABLES:
            try:
                cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {target_schema}.{table} TO {app_user}")
                granted_count += 1
            except Exception as ge:
                print(f"    [Warning] Could not grant on {target_schema}.{table}: {ge}")

        print(f"[+] Granted DML privileges on {granted_count}/{len(ALL_GREENLINE_TABLES)} tables.")

        # Create logon trigger to resolve CURRENT_SCHEMA automatically
        print(f"[*] Creating AFTER LOGON trigger on {app_user} schema...")
        trigger_sql = f"""
        CREATE OR REPLACE TRIGGER {app_user}.set_current_schema
        AFTER LOGON ON {app_user}.SCHEMA
        BEGIN
          EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = {target_schema}';
        END;
        """
        cursor.execute(trigger_sql)
        print("[+] Created AFTER LOGON trigger successfully.")

        conn.commit()
    except Exception as e:
        print(f"[Error] Failed to provision user {app_user}: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    # Verify that the new user can connect and query tables
    print(f"[*] Verifying connection as {app_user}...")
    try:
        test_conn = oracledb.connect(user=app_user, password=app_password, dsn=dsn)
        test_cur = test_conn.cursor()
        test_cur.execute("SELECT COUNT(*) FROM users")
        user_count = test_cur.fetchone()[0]
        print(f"[+] Verification succeeded! Connected as {app_user}, read {user_count} records from users table.")

        # Confirm DDL protection: Attempting CREATE TABLE should fail with ORA-01031
        try:
            test_cur.execute("CREATE TABLE greenline_test_ddl (id NUMBER)")
            print("[-] WARNING: User unexpectedly has CREATE TABLE privilege!")
        except oracledb.DatabaseError as de:
            err, = de.args
            if err.code == 1031:
                print("[+] Verified DDL Protection: CREATE TABLE correctly blocked with ORA-01031 (insufficient privileges).")
            else:
                print(f"[*] DDL block error code: {err.code}")

        test_cur.close()
        test_conn.close()
    except Exception as ve:
        print(f"[Warning] Verification connection check encountered: {ve}")

    print("\n" + "=" * 65)
    print("SUCCESS: DML-Only Database User Provisioned!")
    print("=" * 65)
    print("To switch Greenline to this least-privilege user, update .env with:\n")
    print(f"ORACLE_USER={app_user}")
    print(f"ORACLE_PASSWORD={app_password}")
    print(f"ORACLE_SCHEMA={target_schema}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
