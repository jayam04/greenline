-- ==============================================================================
-- Greenline Least-Privilege Database User Setup for Networth Microservice
-- Run this script as the ADMIN schema owner in Oracle Autonomous Database
-- or as DBA / schema owner in local Oracle 23ai (FREEPDB1)
-- ==============================================================================
--
-- Deployment Instructions:
-- 1. Oracle Autonomous Database (Cloud):
--    Run as ADMIN user directly in SQL Worksheet, SQL Developer, or SQL*Plus.
--    The default tablespace is DATA and schema owner is ADMIN.
--
-- 2. Local Docker Container (Oracle Free 23ai / FREEPDB1):
--    Run as SYSTEM or schema owner. If running in the local docker container where
--    default permanent tablespace is USERS and schema owner is GREENLINE_TEST:
--    - Substitute DATA with USERS
--    - Substitute ADMIN. with GREENLINE_TEST.
-- ==============================================================================

-- 1. Create the dedicated Networth microservice database user
-- In Oracle Autonomous Cloud DB: Passwords must be 12-30 characters, contain
-- uppercase, lowercase, numbers, and not include username.
CREATE USER GREENLINE_NETWORTH IDENTIFIED BY "SecureNetworth2026#DbPass"
  DEFAULT TABLESPACE DATA
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON DATA;

-- 2. Grant basic connection capability ONLY (Zero DDL privileges)
GRANT CREATE SESSION TO GREENLINE_NETWORTH;

-- 3. Grant SELECT ONLY on Analytical Input Tables (Read-Only)
-- The Networth microservice must NEVER write, modify, or delete core financial ledgers
GRANT SELECT ON ADMIN.users TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.accounts TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.assets TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.transactions TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.lots TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.lot_sales TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.price_history TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.dividends TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.cash_flows TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.cashflow_transactions TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.cashflow_payments TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.cashflow_items TO GREENLINE_NETWORTH;
GRANT SELECT ON ADMIN.categories TO GREENLINE_NETWORTH;

-- 4. Grant DML (SELECT, INSERT, UPDATE, DELETE) on Output & Cache Tables
-- The Networth microservice stores precalculated snapshots, asset class allocations,
-- Newton-Raphson XIRR iterations, and market benchmark historical points
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.networth_snapshots TO GREENLINE_NETWORTH;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.networth_by_asset_class TO GREENLINE_NETWORTH;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.xirr_cache TO GREENLINE_NETWORTH;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.benchmarks TO GREENLINE_NETWORTH;

-- 5. Excluded Tables (Explicitly NO grants):
-- api_keys, app_settings, expected_dividends, schema_migrations
-- Security-critical credentials, application configurations, and schema migrations
-- remain strictly isolated to the Core API domain.

-- 6. Attach AFTER LOGON trigger on GREENLINE_NETWORTH schema to automatically resolve
-- table names against schema owner without requiring "ADMIN." prefixes in queries
CREATE OR REPLACE TRIGGER GREENLINE_NETWORTH.set_current_schema
AFTER LOGON ON GREENLINE_NETWORTH.SCHEMA
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = ADMIN';
END;
/

-- Verification queries (Run as GREENLINE_NETWORTH to verify permissions):
-- 1. Read input: SELECT COUNT(*) FROM transactions; (Must succeed)
-- 2. Write snapshot: INSERT INTO networth_snapshots (user_id, snapshot_date, total_invested, total_current_value, cash_balance, total_realized_pnl, total_unrealized_pnl, net_worth) VALUES (0, DATE '2026-01-04', 1000, 1200, 500, 0, 200, 1700); (Must succeed)
-- 3. Forbidden write test: DELETE FROM transactions; (Must fail with ORA-01031 / ORA-41900: insufficient privileges)
-- 4. Forbidden table test: SELECT * FROM api_keys; (Must fail with ORA-00942: table or view does not exist)
