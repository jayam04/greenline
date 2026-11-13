-- ==============================================================================
-- Greenline Least-Privilege DML-Only Database User Setup
-- Run this script as the ADMIN schema owner in Oracle Autonomous Database
-- ==============================================================================

-- 1. Create the application user (Replace 'ChangeThisSecurePassword2026#' with a strong password)
-- In Oracle Autonomous Cloud DB: Passwords must be 12-30 characters, contain uppercase, lowercase, numbers, and not include username.
CREATE USER GREENLINE_APP IDENTIFIED BY "ChangeThisSecurePassword2026#"
  DEFAULT TABLESPACE DATA
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON DATA;

-- 2. Grant basic connection capability ONLY (Zero DDL privileges)
GRANT CREATE SESSION TO GREENLINE_APP;

-- 3. Grant full DML permissions (SELECT, INSERT, UPDATE, DELETE) on all 21 Greenline tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.users TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.accounts TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.categories TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.assets TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.transactions TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.lots TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.lot_sales TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.price_history TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.dividends TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.expected_dividends TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.cash_flows TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.networth_snapshots TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.networth_by_asset_class TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.benchmarks TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.xirr_cache TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.cashflow_transactions TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.cashflow_payments TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.cashflow_items TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.app_settings TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.api_keys TO GREENLINE_APP;
GRANT SELECT, INSERT, UPDATE, DELETE ON ADMIN.schema_migrations TO GREENLINE_APP;

-- 4. Create an AFTER LOGON trigger on GREENLINE_APP schema to automatically resolve
-- table names against the ADMIN schema without needing "ADMIN." prefixes in queries
CREATE OR REPLACE TRIGGER GREENLINE_APP.set_current_schema
AFTER LOGON ON GREENLINE_APP.SCHEMA
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = ADMIN';
END;
/

-- Verification query (Run as GREENLINE_APP to confirm successful access):
-- SELECT COUNT(*) FROM users;
