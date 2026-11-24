-- ============================================================================
-- Greenline 1,000 Sample Transaction Data Population Script
-- ============================================================================
-- Description:
--   Populates exactly 1,000 transaction rows spanning 2 full calendar years
--   (from 2024-11-12 to 2026-11-12):
--     - 900 Cashflow Transactions:
--         * Single account + Single category (~225 rows)
--         * Multi-Category split transactions (~225 rows)
--         * Multi-Account split payment transactions (~225 rows)
--         * BOTH Multi-Category AND Multi-Account split transactions (~225 rows)
--     - 100 Stock Investment Transactions:
--         * 60 Stock Buys creating FIFO Lots (AAPL, MSFT, GOOGL, AMZN, NVDA)
--         * 40 Stock Sells linked to Lots with LotSale records (FIFO PnL, holding period)
--         * Asset Price History across dates for valuation accuracy
--
-- Compatibility:
--   Oracle Autonomous Database (ADB), Oracle Database 23ai / Free, SQLcl, SQL*Plus.
-- ============================================================================

SET DEFINE OFF;
SET SERVEROUTPUT ON SIZE UNLIMITED;

DECLARE
    -- Configure the target user_id (Default: 15 for active Greenline user, change as needed)
    c_user_id       CONSTANT PLS_INTEGER := 15;
    c_marker        CONSTANT VARCHAR2(64) := 'GREENLINE_SAMPLE_1000_V1';
    c_start_date    CONSTANT DATE := DATE '2024-11-12';
    c_span_days     CONSTANT PLS_INTEGER := 730; -- Exactly 2 years

    v_existing      PLS_INTEGER := 0;

    -- Account IDs
    v_acc_bank_id   accounts.account_id%TYPE;
    v_acc_rev_id    accounts.account_id%TYPE;
    v_acc_cash_id   accounts.account_id%TYPE;
    v_acc_broker_id accounts.account_id%TYPE;

    -- Category IDs
    v_cat_salary    categories.category_id%TYPE;
    v_cat_bonus     categories.category_id%TYPE;
    v_cat_freelance categories.category_id%TYPE;
    v_cat_groceries categories.category_id%TYPE;
    v_cat_dining    categories.category_id%TYPE;
    v_cat_housing   categories.category_id%TYPE;
    v_cat_util      categories.category_id%TYPE;
    v_cat_transport categories.category_id%TYPE;
    v_cat_health    categories.category_id%TYPE;
    v_cat_entertain categories.category_id%TYPE;
    v_cat_shopping  categories.category_id%TYPE;
    v_cat_travel    categories.category_id%TYPE;

    -- Variables for cashflow generation
    v_cashflow_id   cashflow_transactions.cashflow_id%TYPE;
    v_cf_date       DATE;
    v_title         VARCHAR2(120);
    v_kind          VARCHAR2(16);
    v_total_amt     NUMBER(12,2);
    v_item_amt1     NUMBER(12,2);
    v_item_amt2     NUMBER(12,2);
    v_pmt_amt1      NUMBER(12,2);
    v_pmt_amt2      NUMBER(12,2);
    v_cat_id1       categories.category_id%TYPE;
    v_cat_id2       categories.category_id%TYPE;
    v_acc_id1       accounts.account_id%TYPE;
    v_acc_id2       accounts.account_id%TYPE;

    -- Variables for investment generation
    TYPE t_lot_rec IS RECORD (
        lot_id            lots.lot_id%TYPE,
        asset_id          assets.asset_id%TYPE,
        buy_date          DATE,
        quantity_original NUMBER(12,4),
        quantity_rem      NUMBER(12,4),
        cost_per_unit     NUMBER(12,4)
    );
    TYPE t_lot_table IS TABLE OF t_lot_rec INDEX BY PLS_INTEGER;
    v_lots          t_lot_table;
    v_lot_count     PLS_INTEGER := 0;

    v_asset_id      assets.asset_id%TYPE;
    v_symbol        VARCHAR2(16);
    v_asset_name    VARCHAR2(100);
    v_tx_id         transactions.transaction_id%TYPE;
    v_lot_id        lots.lot_id%TYPE;
    v_tx_date       DATE;
    v_shares        NUMBER(12,4);
    v_price         NUMBER(12,4);
    v_cost_basis    NUMBER(12,2);
    v_proceeds      NUMBER(12,2);
    v_realized_pnl  NUMBER(12,2);
    v_sell_qty      NUMBER(12,4);
    v_hold_days     PLS_INTEGER;

    -- Helper functions
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
    END ensure_account;

    FUNCTION ensure_category(p_name VARCHAR2, p_type VARCHAR2, p_label VARCHAR2)
        RETURN categories.category_id%TYPE
    IS
        l_id categories.category_id%TYPE;
    BEGIN
        BEGIN
            SELECT category_id INTO l_id
              FROM categories
             WHERE user_id = c_user_id AND name = p_name
             FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO categories (user_id, name, category_type, default_label, created_at)
                VALUES (c_user_id, p_name, p_type, p_label, SYSTIMESTAMP)
                RETURNING category_id INTO l_id;
        END;
        RETURN l_id;
    END ensure_category;

    FUNCTION ensure_asset(p_symbol VARCHAR2, p_name VARCHAR2, p_exchange VARCHAR2)
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
                VALUES (p_symbol, p_name, 'stock', p_exchange, 'Technology & Equities', 'Common Stock', 'EUR')
                RETURNING asset_id INTO l_id;
        END;
        RETURN l_id;
    END ensure_asset;

BEGIN
    -- 1. Validate User
    SELECT COUNT(*) INTO v_existing FROM users WHERE user_id = c_user_id;
    IF v_existing = 0 THEN
        INSERT INTO users (user_id, username, email)
        VALUES (c_user_id, 'user_' || TO_CHAR(c_user_id), 'user' || TO_CHAR(c_user_id) || '@greenline.local');
        DBMS_OUTPUT.PUT_LINE('Created user with user_id = ' || TO_CHAR(c_user_id));
    END IF;

    -- 2. Check for existing dataset marker (idempotency check)
    SELECT COUNT(*) INTO v_existing
      FROM cashflow_transactions
     WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0;

    IF v_existing >= 900 THEN
        DBMS_OUTPUT.PUT_LINE('Sample dataset (' || c_marker || ') already exists for user ' || TO_CHAR(c_user_id) || '. Skipping insertion.');
        RETURN;
    ELSIF v_existing > 0 THEN
        -- Clean up partial prior run with proper child dependency order
        DELETE FROM lot_sales WHERE user_id = c_user_id AND sell_transaction_id IN (
            SELECT transaction_id FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
        );
        DELETE FROM lots WHERE user_id = c_user_id AND buy_transaction_id IN (
            SELECT transaction_id FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
        );
        DELETE FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0;
        DELETE FROM cashflow_payments WHERE user_id = c_user_id AND cashflow_id IN (
            SELECT cashflow_id FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
        );
        DELETE FROM cashflow_items WHERE user_id = c_user_id AND cashflow_id IN (
            SELECT cashflow_id FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
        );
        DELETE FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0;
        COMMIT;
        DBMS_OUTPUT.PUT_LINE('Cleaned up previous partial run.');
    END IF;

    -- 3. Ensure Accounts
    v_acc_bank_id   := ensure_account('Bank of Ireland (Main)', 'bank', 'EUR');
    v_acc_rev_id    := ensure_account('Revolut (Digital)', 'bank', 'EUR');
    v_acc_cash_id   := ensure_account('Cash Wallet', 'bank', 'EUR');
    v_acc_broker_id := ensure_account('Interactive Brokers', 'demat', 'EUR');

    -- 4. Ensure Categories
    v_cat_salary    := ensure_category('Salary', 'INCOME', 'ESSENTIAL');
    v_cat_bonus     := ensure_category('Bonus & Performance', 'INCOME', 'DISCRETIONARY');
    v_cat_freelance := ensure_category('Freelance & Consulting', 'INCOME', 'DISCRETIONARY');
    v_cat_groceries := ensure_category('Groceries & Supermarket', 'EXPENSE', 'ESSENTIAL');
    v_cat_dining    := ensure_category('Dining Out & Cafes', 'EXPENSE', 'DISCRETIONARY');
    v_cat_housing   := ensure_category('Rent & Housing', 'EXPENSE', 'ESSENTIAL');
    v_cat_util      := ensure_category('Utilities & Internet', 'EXPENSE', 'ESSENTIAL');
    v_cat_transport := ensure_category('Transport & Fuel', 'EXPENSE', 'ESSENTIAL');
    v_cat_health    := ensure_category('Health & Pharmacy', 'EXPENSE', 'ESSENTIAL');
    v_cat_entertain := ensure_category('Entertainment & Leisure', 'EXPENSE', 'DISCRETIONARY');
    v_cat_shopping  := ensure_category('Shopping & Tech', 'EXPENSE', 'DISCRETIONARY');
    v_cat_travel    := ensure_category('Travel & Flights', 'EXPENSE', 'DISCRETIONARY');

    -- ========================================================================
    -- 5. GENERATE 900 CASHFLOW TRANSACTIONS ACROSS 2 YEARS
    -- ========================================================================
    -- Distribution:
    --   Pattern 0 (i MOD 4 = 0): Single Category, Single Account (~225 rows)
    --   Pattern 1 (i MOD 4 = 1): Multi-Category (2 items), Single Account (~225 rows)
    --   Pattern 2 (i MOD 4 = 2): Single Category, Multi-Account (2 payments) (~225 rows)
    --   Pattern 3 (i MOD 4 = 3): BOTH Multi-Category (2 items) AND Multi-Account (2 payments) (~225 rows)
    -- ========================================================================
    FOR i IN 1..900 LOOP
        -- Distribute transaction dates smoothly across the 730 days (2 years)
        v_cf_date := c_start_date + MOD(i * 47, c_span_days);

        -- ~12% Income, 88% Expense
        IF MOD(i, 8) = 0 THEN
            v_kind := 'INCOME';
            v_total_amt := ROUND(1500.00 + MOD(i * 137, 280000) / 100, 2);
            v_title := CASE MOD(i, 3)
                WHEN 0 THEN 'Monthly Salary Paycheck #' || TO_CHAR(i)
                WHEN 1 THEN 'Consulting Milestone Payment #' || TO_CHAR(i)
                ELSE 'Quarterly Performance Bonus #' || TO_CHAR(i)
            END;
            v_cat_id1 := CASE MOD(i, 3) WHEN 0 THEN v_cat_salary WHEN 1 THEN v_cat_freelance ELSE v_cat_bonus END;
            v_cat_id2 := v_cat_bonus;
        ELSE
            v_kind := 'EXPENSE';
            v_total_amt := ROUND(15.00 + MOD(i * 739, 38000) / 100, 2);
            v_title := CASE MOD(i, 9)
                WHEN 0 THEN 'Weekly Supermarket Run #' || TO_CHAR(i)
                WHEN 1 THEN 'Dinner & Drinks with Friends #' || TO_CHAR(i)
                WHEN 2 THEN 'Monthly Rent & Building Maintenance #' || TO_CHAR(i)
                WHEN 3 THEN 'Electricity & Fiber Broadband #' || TO_CHAR(i)
                WHEN 4 THEN 'Fuel & Public Transit Card #' || TO_CHAR(i)
                WHEN 5 THEN 'Pharmacy & Dental Checkup #' || TO_CHAR(i)
                WHEN 6 THEN 'Cinema & Concert Tickets #' || TO_CHAR(i)
                WHEN 7 THEN 'Electronics & Household Goods #' || TO_CHAR(i)
                ELSE 'Flight & Hotel Booking #' || TO_CHAR(i)
            END;
            CASE MOD(i, 9)
                WHEN 0 THEN v_cat_id1 := v_cat_groceries; v_cat_id2 := v_cat_dining;
                WHEN 1 THEN v_cat_id1 := v_cat_dining;    v_cat_id2 := v_cat_entertain;
                WHEN 2 THEN v_cat_id1 := v_cat_housing;   v_cat_id2 := v_cat_util;
                WHEN 3 THEN v_cat_id1 := v_cat_util;      v_cat_id2 := v_cat_housing;
                WHEN 4 THEN v_cat_id1 := v_cat_transport; v_cat_id2 := v_cat_shopping;
                WHEN 5 THEN v_cat_id1 := v_cat_health;    v_cat_id2 := v_cat_groceries;
                WHEN 6 THEN v_cat_id1 := v_cat_entertain; v_cat_id2 := v_cat_dining;
                WHEN 7 THEN v_cat_id1 := v_cat_shopping;  v_cat_id2 := v_cat_util;
                ELSE        v_cat_id1 := v_cat_travel;    v_cat_id2 := v_cat_dining;
            END CASE;
        END IF;

        -- Insert parent CashflowTransaction
        INSERT INTO cashflow_transactions
            (user_id, transaction_date, title, total_amount, currency, transaction_kind, notes, created_at)
        VALUES
            (c_user_id, v_cf_date, v_title, v_total_amt, 'EUR', v_kind, c_marker, SYSTIMESTAMP)
        RETURNING cashflow_id INTO v_cashflow_id;

        -- Apply Category Split vs Single Category
        IF MOD(i, 2) = 1 THEN
            -- Multi-Category split (2 items: 60% / 40%)
            v_item_amt1 := ROUND(v_total_amt * 0.60, 2);
            v_item_amt2 := v_total_amt - v_item_amt1;

            INSERT INTO cashflow_items (user_id, cashflow_id, category_id, amount, label, description)
            VALUES (c_user_id, v_cashflow_id, v_cat_id1, v_item_amt1, 'ESSENTIAL', 'Primary split item');

            INSERT INTO cashflow_items (user_id, cashflow_id, category_id, amount, label, description)
            VALUES (c_user_id, v_cashflow_id, v_cat_id2, v_item_amt2, 'DISCRETIONARY', 'Secondary split item');
        ELSE
            -- Single Category (1 item: 100%)
            INSERT INTO cashflow_items (user_id, cashflow_id, category_id, amount, label, description)
            VALUES (c_user_id, v_cashflow_id, v_cat_id1, v_total_amt, 'ESSENTIAL', 'Full category allocation');
        END IF;

        -- Apply Account Split vs Single Account Payment
        IF MOD(i, 4) IN (2, 3) THEN
            -- Multi-Account split payment (2 accounts: 50% / 50%)
            v_pmt_amt1 := ROUND(v_total_amt * 0.50, 2);
            v_pmt_amt2 := v_total_amt - v_pmt_amt1;

            v_acc_id1 := v_acc_bank_id;
            v_acc_id2 := CASE WHEN MOD(i, 2) = 0 THEN v_acc_rev_id ELSE v_acc_cash_id END;

            INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
            VALUES (c_user_id, v_cashflow_id, v_acc_id1, CASE WHEN v_kind = 'INCOME' THEN v_pmt_amt1 ELSE -v_pmt_amt1 END);

            INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
            VALUES (c_user_id, v_cashflow_id, v_acc_id2, CASE WHEN v_kind = 'INCOME' THEN v_pmt_amt2 ELSE -v_pmt_amt2 END);
        ELSE
            -- Single Account payment (1 account: 100%)
            v_acc_id1 := CASE MOD(i, 3)
                WHEN 0 THEN v_acc_bank_id
                WHEN 1 THEN v_acc_rev_id
                ELSE v_acc_cash_id
            END;

            INSERT INTO cashflow_payments (user_id, cashflow_id, account_id, amount)
            VALUES (c_user_id, v_cashflow_id, v_acc_id1, CASE WHEN v_kind = 'INCOME' THEN v_total_amt ELSE -v_total_amt END);
        END IF;
    END LOOP;

    -- ========================================================================
    -- 6. GENERATE 100 STOCK INVESTMENT TRANSACTIONS (60 BUYS, 40 SELLS)
    -- ========================================================================
    -- Across 5 prominent tech & index equities:
    --   AAPL, MSFT, GOOGL, AMZN, NVDA
    -- ========================================================================
    FOR s IN 1..5 LOOP
        v_symbol := CASE s
            WHEN 1 THEN 'AAPL'
            WHEN 2 THEN 'MSFT'
            WHEN 3 THEN 'GOOGL'
            WHEN 4 THEN 'AMZN'
            ELSE 'NVDA'
        END;
        v_asset_name := CASE s
            WHEN 1 THEN 'Apple Inc.'
            WHEN 2 THEN 'Microsoft Corporation'
            WHEN 3 THEN 'Alphabet Inc.'
            WHEN 4 THEN 'Amazon.com, Inc.'
            ELSE 'NVIDIA Corporation'
        END;

        v_asset_id := ensure_asset(v_symbol, v_asset_name, 'NASDAQ');

        -- 12 buys per stock = 60 total buys
        FOR b IN 1..12 LOOP
            v_tx_date := c_start_date + (s - 1) * 15 + (b - 1) * 55;
            v_shares  := 5 + MOD(b * 3 + s * 2, 15);
            v_price   := ROUND(100.00 + s * 30 + b * 4.50, 2);
            v_total_amt := ROUND(v_shares * v_price + 1.50, 2); -- Total includes 1.50 fee

            -- Buy Transaction
            INSERT INTO transactions
                (user_id, account_id, asset_id, transaction_type, transaction_date,
                 quantity, price_per_unit, total_amount, fees, taxes, source, notes)
            VALUES
                (c_user_id, v_acc_broker_id, v_asset_id, 'buy', v_tx_date,
                 v_shares, v_price, v_total_amt, 1.50, 0.00, 'seeded_1000', c_marker || ': buy ' || v_symbol)
            RETURNING transaction_id INTO v_tx_id;

            -- Corresponding Lot
            INSERT INTO lots
                (user_id, account_id, asset_id, buy_transaction_id, buy_date,
                 quantity_original, quantity_remaining, cost_per_unit)
            VALUES
                (c_user_id, v_acc_broker_id, v_asset_id, v_tx_id, v_tx_date,
                 v_shares, v_shares, ROUND(v_total_amt / v_shares, 4))
            RETURNING lot_id INTO v_lot_id;

            -- Record lot in memory array for FIFO matching during sells
            v_lot_count := v_lot_count + 1;
            v_lots(v_lot_count).lot_id := v_lot_id;
            v_lots(v_lot_count).asset_id := v_asset_id;
            v_lots(v_lot_count).buy_date := v_tx_date;
            v_lots(v_lot_count).quantity_original := v_shares;
            v_lots(v_lot_count).quantity_rem := v_shares;
            v_lots(v_lot_count).cost_per_unit := ROUND(v_total_amt / v_shares, 4);

            -- Ensure Price History record exists
            BEGIN
                INSERT INTO price_history (user_id, asset_id, price_date, close_price, source)
                VALUES (c_user_id, v_asset_id, v_tx_date, v_price, 'seeded_1000');
            EXCEPTION
                WHEN DUP_VAL_ON_INDEX THEN NULL;
            END;
        END LOOP;

        -- 8 sells per stock = 40 total sells (depleting earliest lots in FIFO order)
        FOR sel IN 1..8 LOOP
            v_tx_date := c_start_date + 180 + (s - 1) * 20 + (sel - 1) * 65;
            v_sell_qty := 4 + MOD(sel * 2, 6);
            v_price   := ROUND(125.00 + s * 35 + sel * 7.20, 2);
            v_proceeds := ROUND(v_sell_qty * v_price - 2.00, 2); -- Net proceeds minus 2.00 fee

            -- Sell Transaction
            INSERT INTO transactions
                (user_id, account_id, asset_id, transaction_type, transaction_date,
                 quantity, price_per_unit, total_amount, fees, taxes, source, notes)
            VALUES
                (c_user_id, v_acc_broker_id, v_asset_id, 'sell', v_tx_date,
                 v_sell_qty, v_price, v_proceeds, 2.00, 0.00, 'seeded_1000', c_marker || ': sell ' || v_symbol)
            RETURNING transaction_id INTO v_tx_id;

            -- Update price history for sell date
            BEGIN
                INSERT INTO price_history (user_id, asset_id, price_date, close_price, source)
                VALUES (c_user_id, v_asset_id, v_tx_date, v_price, 'seeded_1000');
            EXCEPTION
                WHEN DUP_VAL_ON_INDEX THEN NULL;
            END;

            -- Match against earliest open lot for this asset (FIFO)
            FOR idx IN 1..v_lot_count LOOP
                IF v_lots(idx).asset_id = v_asset_id AND v_lots(idx).quantity_rem > 0 AND v_lots(idx).buy_date <= v_tx_date THEN
                    DECLARE
                        v_deplete_qty NUMBER(12,4);
                    BEGIN
                        v_deplete_qty := LEAST(v_lots(idx).quantity_rem, v_sell_qty);
                        v_cost_basis  := ROUND(v_deplete_qty * v_lots(idx).cost_per_unit, 2);
                        v_realized_pnl := ROUND((v_deplete_qty * v_price) - v_cost_basis - 2.00, 2);
                        v_hold_days   := GREATEST(1, TRUNC(v_tx_date) - TRUNC(v_lots(idx).buy_date));

                        -- Insert LotSale
                        INSERT INTO lot_sales
                            (user_id, lot_id, sell_transaction_id, quantity_sold,
                             sale_price_per_unit, cost_basis, realized_pnl, holding_period_days)
                        VALUES
                            (c_user_id, v_lots(idx).lot_id, v_tx_id, v_deplete_qty,
                             v_price, v_cost_basis, v_realized_pnl, v_hold_days);

                        -- Update DB Lot remaining quantity
                        UPDATE lots
                           SET quantity_remaining = quantity_remaining - v_deplete_qty
                         WHERE lot_id = v_lots(idx).lot_id;

                        -- Update in-memory record
                        v_lots(idx).quantity_rem := v_lots(idx).quantity_rem - v_deplete_qty;
                        v_sell_qty := v_sell_qty - v_deplete_qty;

                        EXIT WHEN v_sell_qty <= 0.0001;
                    END;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;

    -- Ensure latest price history as of today for all 5 assets
    FOR s IN 1..5 LOOP
        v_symbol := CASE s WHEN 1 THEN 'AAPL' WHEN 2 THEN 'MSFT' WHEN 3 THEN 'GOOGL' WHEN 4 THEN 'AMZN' ELSE 'NVDA' END;
        SELECT asset_id INTO v_asset_id FROM assets WHERE symbol = v_symbol;
        BEGIN
            INSERT INTO price_history (user_id, asset_id, price_date, close_price, source)
            VALUES (c_user_id, v_asset_id, DATE '2026-11-12', 150.00 + s * 40, 'seeded_1000');
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN
                UPDATE price_history
                   SET close_price = 150.00 + s * 40
                 WHERE asset_id = v_asset_id AND price_date = DATE '2026-11-12';
        END;
    END LOOP;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('================================================================');
    DBMS_OUTPUT.PUT_LINE('SUCCESS: 1,000 Transactions Created for User ' || TO_CHAR(c_user_id));
    DBMS_OUTPUT.PUT_LINE('  - Cashflow Transactions : 900 rows across 2024-11-12 to 2026-11-12');
    DBMS_OUTPUT.PUT_LINE('  - Stock Buy Transactions:  60 rows (AAPL, MSFT, GOOGL, AMZN, NVDA)');
    DBMS_OUTPUT.PUT_LINE('  - Stock Sell Transactions: 40 rows (FIFO closed with LotSale records)');
    DBMS_OUTPUT.PUT_LINE('  - Total Transactions    : 1,000 rows exactly');
    DBMS_OUTPUT.PUT_LINE('================================================================');
END;
/

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- 1. Total Primary Transactions Count & Date Span
SELECT 'Cashflow Transactions' AS dataset, COUNT(*) AS row_count,
       MIN(transaction_date) AS min_date, MAX(transaction_date) AS max_date
  FROM cashflow_transactions
 WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0
UNION ALL
SELECT 'Investment Transactions (Buy/Sell)', COUNT(*),
       MIN(transaction_date), MAX(transaction_date)
  FROM transactions
 WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0
UNION ALL
SELECT 'TOTAL TRANSACTIONS', 
       (SELECT COUNT(*) FROM cashflow_transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0) +
       (SELECT COUNT(*) FROM transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0),
       LEAST((SELECT MIN(transaction_date) FROM cashflow_transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0),
             (SELECT MIN(transaction_date) FROM transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0)),
       GREATEST((SELECT MAX(transaction_date) FROM cashflow_transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0),
                (SELECT MAX(transaction_date) FROM transactions WHERE DBMS_LOB.INSTR(notes, 'GREENLINE_SAMPLE_1000_V1') > 0))
  FROM DUAL;

-- 2. Breakdown by Split Patterns (Categories, Accounts, and Both)
SELECT 
    CASE 
        WHEN item_count > 1 AND pmt_count > 1 THEN 'Both Multi-Category & Multi-Account'
        WHEN item_count > 1 AND pmt_count = 1 THEN 'Multi-Category Split Only'
        WHEN item_count = 1 AND pmt_count > 1 THEN 'Multi-Account Split Payment Only'
        ELSE 'Single Category & Single Account'
    END AS transaction_pattern,
    COUNT(*) AS transaction_count,
    ROUND(AVG(total_amount), 2) AS avg_amount,
    MIN(transaction_date) AS earliest,
    MAX(transaction_date) AS latest
FROM (
    SELECT ct.cashflow_id, ct.total_amount, ct.transaction_date,
           (SELECT COUNT(*) FROM cashflow_items ci WHERE ci.cashflow_id = ct.cashflow_id) AS item_count,
           (SELECT COUNT(*) FROM cashflow_payments cp WHERE cp.cashflow_id = ct.cashflow_id) AS pmt_count
      FROM cashflow_transactions ct
     WHERE DBMS_LOB.INSTR(ct.notes, 'GREENLINE_SAMPLE_1000_V1') > 0
)
GROUP BY 
    CASE 
        WHEN item_count > 1 AND pmt_count > 1 THEN 'Both Multi-Category & Multi-Account'
        WHEN item_count > 1 AND pmt_count = 1 THEN 'Multi-Category Split Only'
        WHEN item_count = 1 AND pmt_count > 1 THEN 'Multi-Account Split Payment Only'
        ELSE 'Single Category & Single Account'
    END
ORDER BY transaction_count DESC;

-- 3. Stock Buys, Sells, and Lot Sales Verification
SELECT t.transaction_type, COUNT(*) AS tx_count,
       SUM(t.quantity) AS total_shares,
       ROUND(SUM(t.total_amount), 2) AS total_volume_eur,
       ROUND(SUM(t.fees), 2) AS total_fees_eur
  FROM transactions t
 WHERE DBMS_LOB.INSTR(t.notes, 'GREENLINE_SAMPLE_1000_V1') > 0
 GROUP BY t.transaction_type;

-- 4. Realized PnL from Closed Lots
SELECT ast.symbol,
       COUNT(ls.lot_sale_id) AS closed_lot_count,
       ROUND(SUM(ls.quantity_sold), 2) AS shares_sold,
       ROUND(SUM(ls.cost_basis), 2) AS cost_basis_eur,
       ROUND(SUM(ls.realized_pnl), 2) AS net_realized_pnl_eur,
       ROUND(AVG(ls.holding_period_days), 0) AS avg_holding_days
  FROM lot_sales ls
  JOIN transactions t ON t.transaction_id = ls.sell_transaction_id
  JOIN assets ast ON ast.asset_id = t.asset_id
 WHERE DBMS_LOB.INSTR(t.notes, 'GREENLINE_SAMPLE_1000_V1') > 0
 GROUP BY ast.symbol
 ORDER BY ast.symbol;

-- ============================================================================
-- OPTIONAL: CLEANUP / RESET SCRIPT
-- ============================================================================
-- If you need to completely remove the 1,000 sample rows, run the block below:
/*
DECLARE
    c_user_id CONSTANT PLS_INTEGER := 15;
    c_marker  CONSTANT VARCHAR2(64) := 'GREENLINE_SAMPLE_1000_V1';
BEGIN
    DELETE FROM lot_sales WHERE user_id = c_user_id AND sell_transaction_id IN (
        SELECT transaction_id FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
    );
    DELETE FROM lots WHERE user_id = c_user_id AND buy_transaction_id IN (
        SELECT transaction_id FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
    );
    DELETE FROM transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0;
    DELETE FROM cashflow_payments WHERE user_id = c_user_id AND cashflow_id IN (
        SELECT cashflow_id FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
    );
    DELETE FROM cashflow_items WHERE user_id = c_user_id AND cashflow_id IN (
        SELECT cashflow_id FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0
    );
    DELETE FROM cashflow_transactions WHERE user_id = c_user_id AND DBMS_LOB.INSTR(notes, c_marker) > 0;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Sample dataset removed successfully.');
END;
/
*/

