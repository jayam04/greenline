#!/usr/bin/env python3
"""
Create Least-Privilege Database User for Greenline Networth Microservice
Connects using ADMIN/DBA credentials and provisions a dedicated
GREENLINE_NETWORTH user with:
- SELECT ONLY on 13 analytical input tables
- SELECT, INSERT, UPDATE, DELETE on 4 output/cache tables
- ZERO grants on excluded tables (api_keys, app_settings, etc.)
- Zero DDL privileges (CREATE SESSION only)
- AFTER LOGON trigger setting CURRENT_SCHEMA
"""

import os
import sys
import argparse
import secrets
import string
import oracledb
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

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


def generate_secure_oracle_password(length: int = 20) -> str:
    """Generate a password compliant with Oracle Autonomous Database complexity rules."""
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    sym = secrets.choice("#_$")
    all_chars = string.ascii_letters + string.digits + "#_$"
    rest = "".join(secrets.choice(all_chars) for _ in range(length - 4))
    return f"{upper}{lower}{digit}{sym}{rest}"


def clean_credential(val: str) -> str:
    if isinstance(val, str):
        return val.strip("\"' \t\r\n")
    return val


def main():
    parser = argparse.ArgumentParser(description="Create least-privilege Networth user in Oracle DB")
    parser.add_argument("--username", default="GREENLINE_NETWORTH", help="User name to create (default: GREENLINE_NETWORTH)")
    parser.add_argument("--password", default=None, help="Password for user (generated if not provided)")
    parser.add_argument("--schema", default=None, help="Schema containing tables (defaults to ADMIN or GREENLINE_TEST)")
    args = parser.parse_args()

    admin_user = clean_credential(os.getenv("ORACLE_ADMIN_USER", os.getenv("ORACLE_USER", "system")))
    admin_password = clean_credential(os.getenv("ORACLE_ADMIN_PASSWORD", os.getenv("ORACLE_PASSWORD", "test_password")))
    dsn = clean_credential(os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1"))
    target_schema = clean_credential(args.schema or os.getenv("ORACLE_SCHEMA", "ADMIN"))

    user_name = clean_credential(args.username).upper()
    user_password = args.password or generate_secure_oracle_password()

    print(f"[*] Connecting to Oracle Database as {admin_user}...")
    try:
        conn = oracledb.connect(user=admin_user, password=admin_password, dsn=dsn)
    except Exception as e:
        print(f"[Error] Failed to connect to Oracle as {admin_user}: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    try:
        # Detect available permanent tablespace
        cursor.execute("SELECT property_value FROM database_properties WHERE property_name = 'DEFAULT_PERMANENT_TABLESPACE'")
        row = cursor.fetchone()
        default_ts = row[0] if row else "DATA"

        cursor.execute("SELECT username FROM all_users WHERE username = :u", u=user_name)
        exists = cursor.fetchone() is not None

        if exists:
            print(f"[*] User {user_name} already exists. Updating password...")
            cursor.execute(f'ALTER USER {user_name} IDENTIFIED BY "{user_password}"')
        else:
            print(f"[*] Creating user {user_name} with tablespace {default_ts}...")
            cursor.execute(
                f'CREATE USER {user_name} IDENTIFIED BY "{user_password}" '
                f'DEFAULT TABLESPACE {default_ts} TEMPORARY TABLESPACE TEMP QUOTA UNLIMITED ON {default_ts}'
            )

        print(f"[*] Granting CREATE SESSION to {user_name}...")
        cursor.execute(f"GRANT CREATE SESSION TO {user_name}")

        print(f"[*] Granting SELECT ONLY on {len(ANALYTICAL_INPUT_TABLES)} input tables in {target_schema}...")
        for table in ANALYTICAL_INPUT_TABLES:
            cursor.execute(f"GRANT SELECT ON {target_schema}.{table} TO {user_name}")

        print(f"[*] Granting SELECT, INSERT, UPDATE, DELETE on {len(OUTPUT_CACHE_TABLES)} output tables in {target_schema}...")
        for table in OUTPUT_CACHE_TABLES:
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {target_schema}.{table} TO {user_name}")

        print(f"[*] Revoking any privileges on {len(EXCLUDED_TABLES)} excluded tables...")
        for table in EXCLUDED_TABLES:
            try:
                cursor.execute(f"REVOKE ALL ON {target_schema}.{table} FROM {user_name}")
            except Exception:
                pass

        print(f"[*] Creating AFTER LOGON trigger on {user_name} schema...")
        trigger_sql = f"""
        CREATE OR REPLACE TRIGGER {user_name}.set_current_schema
        AFTER LOGON ON {user_name}.SCHEMA
        BEGIN
          EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = {target_schema}';
        END;
        """
        cursor.execute(trigger_sql)
        conn.commit()
        print(f"[+] Successfully provisioned {user_name} with least-privilege security policy.")

    except Exception as e:
        print(f"[Error] Failed to provision user {user_name}: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
