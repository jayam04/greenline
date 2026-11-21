-- Additive, repeat-safe synthetic dataset for user 19.
-- Run in the Greenline application schema using SQLcl or SQL*Plus.
-- Generates 4,000 cashflow transactions plus their category/payment links,
-- US equity trades/lots, and dividend transaction + dividend records.
SET DEFINE OFF;
SET SERVEROUTPUT ON;

DECLARE
    c_user_id       CONSTANT PLS_INTEGER := 19;
    c_marker        CONSTANT VARCHAR2(64) := 'GREENLINE_TESTDATA_U19_V1';
    c_start_date    CONSTANT DATE := DATE '2024-11-11';
    c_span_days     CONSTANT PLS_INTEGER := 731;
    v_existing      PLS_INTEGER;
    v_boi_id        accounts.account_id%TYPE;
    v_revolut_id    accounts.account_id%TYPE;
    v_broker_id     accounts.account_id%TYPE;
    v_account_id    accounts.account_id%TYPE;
    v_category_a    categories.category_id%TYPE;
    v_category_b    categories.category_id%TYPE;
    v_asset_id      assets.asset_id%TYPE;
    v_tx_id         transactions.transaction_id%TYPE;
    v_lot_id        lots.lot_id%TYPE;
    v_cashflow_id   cashflow_transactions.cashflow_id%TYPE;
    v_name          VARCHAR2(100);
    v_kind          VARCHAR2(16);
    v_amount        NUMBER(12,2);
    v_part_a        NUMBER(12,2);
    v_part_b        NUMBER(12,2);
    v_shares        NUMBER(12,4);
    v_price         NUMBER(12,4);
    v_rate          NUMBER(12,4);
    v_total         NUMBER(12,2);
    v_symbol        VARCHAR2(12);
    v_asset_name    VARCHAR2(100);
    v_share_count   PLS_INTEGER := 0;

    FUNCTION ensure_account(p_name VARCHAR2, p_type VARCHAR2, p_currency VARCHAR2)
        RETURN accounts.account_id%TYPE
    IS
        l_id accounts.account_id%TYPE;
    BEGIN
        BEGIN
            SELECT account_id INTO l_id
              FROM accounts
             WHERE user_id = c_user_id AND account_name = p_name
             FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO accounts (user_id, account_name, broker_name, account_type, currency, created_at)
                VALUES (c_user_id, p_name, p_name, p_type, p_currency, c_start_date)
                RETURNING account_id INTO l_id;
        END;
        RETURN l_id;
    END;

    FUNCTION ensure_category(p_name VARCHAR2, p_type VARCHAR2)
        RETURN categories.category_id%TYPE
    IS
        l_id categories.category_id%TYPE;
    BEGIN
        BEGIN
            SELECT category_id INTO l_id
              FROM (
                    SELECT category_id
                      FROM categories
                     WHERE user_id IN (0, c_user_id)
                       AND name = p_name
                       AND category_type = p_type
                     ORDER BY CASE WHEN user_id = c_user_id THEN 0 ELSE 1 END
                   )
             WHERE ROWNUM = 1;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO categories (user_id, name, category_type, default_label, created_at)
                VALUES (c_user_id, p_name, p_type,
                        CASE WHEN p_type = 'INCOME' THEN 'ESSENTIAL' ELSE 'DISCRETIONARY' END,
                        SYSTIMESTAMP)
                RETURNING category_id INTO l_id;
        END;
        RETURN l_id;
    END;

    FUNCTION ensure_asset(p_symbol VARCHAR2, p_name VARCHAR2)
        RETURN assets.asset_id%TYPE
    IS
        l_id assets.asset_id%TYPE;
    BEGIN
        BEGIN
            SELECT asset_id INTO l_id
              FROM assets
             WHERE symbol = p_symbol
             FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO assets (symbol, name, asset_type, exchange, sector, industry, currency)
                VALUES (p_symbol, p_name, 'stock',
                        CASE WHEN p_symbol IN ('AAPL', 'MSFT') THEN 'NASDAQ' ELSE 'NYSE' END,
                        'US Equities', 'Common Stock', 'USD')
                RETURNING asset_id INTO l_id;
        END;
        RETURN l_id;
    END;

BEGIN
    SELECT COUNT(*) INTO v_existing FROM users WHERE user_id = c_user_id;
    IF v_existing = 0 THEN
        RAISE_APPLICATION_ERROR(-20019, 'User 19 must exist before loading this dataset.');
    END IF;

    SELECT COUNT(*) INTO v_existing
      FROM cashflow_transactions
     WHERE user_id = c_user_id AND notes = c_marker;

    IF v_existing > 0 THEN
        DBMS_OUTPUT.PUT_LINE('Dataset already present for user 19; no rows inserted.');
    ELSE
        v_boi_id := ensure_account('Bank of Ireland', 'bank', 'EUR');
        v_revolut_id := ensure_account('Revolut', 'bank', 'EUR');
        v_broker_id := ensure_account('Interactive Brokers US', 'demat', 'USD');

        -- 4,000 parent transactions, exactly 2 category items per parent,
        -- and 1 or 2 payments per parent: at least 18,000 cashflow rows.
        FOR i IN 1..4000 LOOP
            v_kind := CASE WHEN MOD(i, 10) = 0 THEN 'INCOME' ELSE 'EXPENSE' END;
            v_amount := ROUND(12 + MOD(i * 7919, 180000) / 100, 2);
            v_part_a := ROUND(v_amount * (0.25 + MOD(i, 5) * 0.10), 2);
            v_part_b := v_amount - v_part_a;
            v_name := CASE MOD(i, 10)
                WHEN 0 THEN 'Synthetic salary or bonus ' || TO_CHAR(i)
                WHEN 1 THEN 'Groceries and household ' || TO_CHAR(i)
                WHEN 2 THEN 'Dining and local travel ' || TO_CHAR(i)
                WHEN 3 THEN 'Utilities and subscriptions ' || TO_CHAR(i)
                WHEN 4 THEN 'Housing and maintenance ' || TO_CHAR(i)
                WHEN 5 THEN 'Transport and fuel ' || TO_CHAR(i)
                WHEN 6 THEN 'Health and fitness ' || TO_CHAR(i)
                WHEN 7 THEN 'Shopping and personal ' || TO_CHAR(i)
                WHEN 8 THEN 'Travel and entertainment ' || TO_CHAR(i)
                ELSE 'Education and services ' || TO_CHAR(i)
            END;

            INSERT INTO cashflow_transactions
                (user_id, transaction_date, title, total_amount, currency, transaction_kind, notes, created_at)
            VALUES
                (c_user_id,
                 c_start_date + MOD(i * 37, c_span_days),
                 v_name,
                 v_amount,
                 'EUR',
                 v_kind,
                 c_marker,
                 SYSTIMESTAMP)
            RETURNING cashflow_id INTO v_cashflow_id;

            IF v_kind = 'INCOME' THEN
                v_category_a := ensure_category('Salary', 'INCOME');
                v_category_b := ensure_category('Other Income', 'INCOME');
            ELSE
                CASE MOD(i, 8)
                    WHEN 0 THEN
                        v_category_a := ensure_category('Groceries', 'EXPENSE');
                        v_category_b := ensure_category('Dining', 'EXPENSE');
                    WHEN 1 THEN
                        v_category_a := ensure_category('Housing', 'EXPENSE');
                        v_category_b := ensure_category('Utilities', 'EXPENSE');
                    WHEN 2 THEN
                        v_category_a := ensure_category('Transport', 'EXPENSE');
                        v_category_b := ensure_category('Travel', 'EXPENSE');
                    WHEN 3 THEN
                        v_category_a := ensure_category('Health', 'EXPENSE');
                        v_category_b := ensure_category('Fitness', 'EXPENSE');
                    WHEN 4 THEN
                        v_category_a := ensure_category('Shopping', 'EXPENSE');
                        v_category_b := ensure_category('Personal Care', 'EXPENSE');
                    WHEN 5 THEN
                        v_category_a := ensure_category('Dining', 'EXPENSE');
                        v_category_b := ensure_category('Entertainment', 'EXPENSE');
                    WHEN 6 THEN
                        v_category_a := ensure_category('Utilities', 'EXPENSE');
                        v_category_b := ensure_category('Subscriptions', 'EXPENSE');
                    ELSE
                        v_category_a := ensure_category('Education', 'EXPENSE');
                        v_category_b := ensure_category('Household', 'EXPENSE');
                END CASE;
            END IF;

            INSERT INTO cashflow_items
                (user_id, cashflow_id, category_id, amount, label, description)
            VALUES
                (c_user_id, v_cashflow_id, v_category_a, v_part_a,
                 CASE WHEN v_kind = 'INCOME' THEN 'ESSENTIAL' ELSE 'DISCRETIONARY' END,
                 'Primary category allocation');
            INSERT INTO cashflow_items
                (user_id, cashflow_id, category_id, amount, label, description)
            VALUES
                (c_user_id, v_cashflow_id, v_category_b, v_part_b,
                 CASE WHEN v_kind = 'INCOME' THEN 'DISCRETIONARY' ELSE 'DISCRETIONARY' END,
                 'Secondary category allocation');

            -- Some transactions use both accounts; others use one of the two.
            IF MOD(i, 4) IN (0, 1) THEN
                v_part_a := ROUND(v_amount / 2, 2);
                v_part_b := v_amount - v_part_a;
                INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
                VALUES (c_user_id, v_cashflow_id, v_boi_id,
                        CASE WHEN v_kind = 'INCOME' THEN v_part_a ELSE -v_part_a END);
                INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
                VALUES (c_user_id, v_cashflow_id, v_revolut_id,
                        CASE WHEN v_kind = 'INCOME' THEN v_part_b ELSE -v_part_b END);
            ELSE
                v_account_id := CASE WHEN MOD(i, 2) = 0 THEN v_boi_id ELSE v_revolut_id END;
                INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
                VALUES (c_user_id, v_cashflow_id, v_account_id,
                        CASE WHEN v_kind = 'INCOME' THEN v_amount ELSE -v_amount END);
            END IF;
        END LOOP;

        -- Six US dividend-paying stocks. Each stock receives eight buys and
        -- eight quarterly dividend payments across the same two-year window.
        FOR j IN 1..6 LOOP
            v_symbol := CASE j
                WHEN 1 THEN 'AAPL' WHEN 2 THEN 'MSFT' WHEN 3 THEN 'KO'
                WHEN 4 THEN 'JNJ' WHEN 5 THEN 'PG' ELSE 'PEP' END;
            v_asset_name := CASE j
                WHEN 1 THEN 'Apple Inc.' WHEN 2 THEN 'Microsoft Corporation'
                WHEN 3 THEN 'The Coca-Cola Company' WHEN 4 THEN 'Johnson & Johnson'
                WHEN 5 THEN 'Procter & Gamble Company' ELSE 'PepsiCo, Inc.' END;
            v_asset_id := ensure_asset(v_symbol, v_asset_name);
            v_shares := 10 + j;
            v_price := CASE j
                WHEN 1 THEN 190 WHEN 2 THEN 390 WHEN 3 THEN 60
                WHEN 4 THEN 150 WHEN 5 THEN 160 ELSE 170 END;
            v_rate := CASE j
                WHEN 1 THEN 0.25 WHEN 2 THEN 0.83 WHEN 3 THEN 0.49
                WHEN 4 THEN 1.24 WHEN 5 THEN 1.01 ELSE 1.36 END;

            FOR k IN 0..7 LOOP
                v_total := ROUND(v_shares * v_price * (1 + k * 0.012), 2);
                INSERT INTO transactions
                    (user_id, account_id, asset_id, transaction_type, transaction_date,
                     quantity, price_per_unit, total_amount, fees, taxes, source, notes)
                VALUES
                    (c_user_id, v_broker_id, v_asset_id, 'buy',
                     c_start_date + j * 13 + k * 80,
                     v_shares, ROUND(v_total / v_shares, 4), v_total,
                     0.35, 0, 'seeded_test_data', c_marker || ': buy ' || v_symbol)
                RETURNING transaction_id INTO v_tx_id;

                INSERT INTO lots
                    (user_id, account_id, asset_id, buy_transaction_id, buy_date,
                     quantity_original, quantity_remaining, cost_per_unit)
                VALUES
                    (c_user_id, v_broker_id, v_asset_id, v_tx_id,
                     c_start_date + j * 13 + k * 80,
                     v_shares, v_shares, ROUND((v_total + 0.35) / v_shares, 4));
                v_share_count := v_share_count + 1;

                v_total := ROUND(v_shares * v_rate, 2);
                INSERT INTO transactions
                    (user_id, account_id, asset_id, transaction_type, transaction_date,
                     quantity, price_per_unit, total_amount, fees, taxes, source, notes)
                VALUES
                    (c_user_id, v_broker_id, v_asset_id, 'dividend',
                     c_start_date + j * 13 + k * 80 + 45,
                     v_shares, v_rate, v_total, 0, ROUND(v_total * 0.15, 2),
                     'seeded_test_data', c_marker || ': dividend ' || v_symbol);

                INSERT INTO dividends
                    (user_id, asset_id, account_id, ex_date, pay_date,
                     amount_per_share, total_amount, tax_withheld)
                VALUES
                    (c_user_id, v_asset_id, v_broker_id,
                     c_start_date + j * 13 + k * 80 + 31,
                     c_start_date + j * 13 + k * 80 + 45,
                     v_rate, v_total, ROUND(v_total * 0.15, 2));
            END LOOP;
        END LOOP;

        DBMS_OUTPUT.PUT_LINE('Inserted 4,000 cashflow transactions, 8,000 category items, 6,000 payments, 48 US stock buys/lots, and 48 dividend pairs.');
        COMMIT;
    END IF;
END;
/

-- Verification queries: cashflow rows alone should total at least 18,000.
SELECT 'cashflow_transactions' AS dataset, COUNT(*) AS row_count,
       MIN(transaction_date) AS first_date, MAX(transaction_date) AS last_date
  FROM cashflow_transactions
 WHERE user_id = 19 AND notes = 'GREENLINE_TESTDATA_U19_V1'
UNION ALL
SELECT 'cashflow_items', COUNT(*), MIN(ct.transaction_date), MAX(ct.transaction_date)
  FROM cashflow_items ci
  JOIN cashflow_transactions ct ON ct.cashflow_id = ci.cashflow_id
 WHERE ci.user_id = 19 AND ct.notes = 'GREENLINE_TESTDATA_U19_V1'
UNION ALL
SELECT 'cashflow_payments', COUNT(*), MIN(ct.transaction_date), MAX(ct.transaction_date)
  FROM cashflow_payments cp
  JOIN cashflow_transactions ct ON ct.cashflow_id = cp.cashflow_id
 WHERE cp.user_id = 19 AND ct.notes = 'GREENLINE_TESTDATA_U19_V1';

SELECT a.account_name, COUNT(*) AS payment_count
  FROM cashflow_payments cp
  JOIN accounts a ON a.account_id = cp.account_id
  JOIN cashflow_transactions ct ON ct.cashflow_id = cp.cashflow_id
 WHERE cp.user_id = 19 AND ct.notes = 'GREENLINE_TESTDATA_U19_V1'
   AND a.account_name IN ('Bank of Ireland', 'Revolut')
 GROUP BY a.account_name;

SELECT COUNT(*) AS transactions_with_multiple_categories_and_accounts
  FROM cashflow_transactions ct
 WHERE ct.user_id = 19 AND ct.notes = 'GREENLINE_TESTDATA_U19_V1'
   AND (SELECT COUNT(*) FROM cashflow_items ci WHERE ci.cashflow_id = ct.cashflow_id) > 1
   AND (SELECT COUNT(*) FROM cashflow_payments cp WHERE cp.cashflow_id = ct.cashflow_id) > 1;

SELECT ast.symbol, COUNT(*) AS dividend_count, SUM(d.total_amount) AS gross_dividends
  FROM dividends d
  JOIN assets ast ON ast.asset_id = d.asset_id
 WHERE d.user_id = 19 AND ast.exchange = 'NYSE'
   AND EXISTS (
       SELECT 1 FROM transactions tx
        WHERE tx.user_id = 19 AND tx.asset_id = d.asset_id
          AND tx.notes LIKE 'GREENLINE_TESTDATA_U19_V1:%'
   )
 GROUP BY ast.symbol
 ORDER BY ast.symbol;
