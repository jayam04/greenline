import { test, expect } from '@playwright/test';

test.describe('Greenline Core End-to-End User Journeys', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock authentication token in localStorage
    await page.addInitScript(() => {
      localStorage.setItem('token', 'e2e-test-auth-token');
      localStorage.setItem('greenline_master_currency', 'EUR');
    });

    // Intercept backend API routes to provide deterministic fixtures
    await page.route('*/**/api/v1/settings*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ master_currency: 'EUR', fiscal_year_start: '01-01' }),
      });
    });

    await page.route('*/**/api/v1/accounts*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            account_id: 1,
            account_name: 'Main Checking Bank',
            account_type: 'bank',
            currency: 'EUR',
            cash_balance: 5000.0,
            securities_value: 0.0,
            current_balance: 5000.0,
          },
          {
            account_id: 2,
            account_name: 'Zerodha Trading Demat',
            account_type: 'demat',
            currency: 'INR',
            cash_balance: 500.0,
            securities_value: 37823.10,
            current_balance: 38323.10,
          }
        ]),
      });
    });

    await page.route('*/**/api/v1/portfolio/summary*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          net_worth: 40000.0,
          total_net_worth: 40000.0,
          total_invested: 32000.0,
          total_current_value: 37823.10,
          cash_balance: 5500.0,
          total_realized_pnl: 0.0,
          total_unrealized_pnl: 6975.46,
          total_fees: 602.64,
          total_taxes: 113.0,
          portfolio_xirr: 0.245,
          top_holdings: [
            {
              asset_id: 4,
              symbol: 'GROWW.BO',
              name: 'Billionbrains Garage Ventures Limited',
              asset_type: 'stock',
              sector: 'Technology',
              currency: 'INR',
              quantity_held: 186.0,
              avg_cost_price: 162.0,
              total_cost: 30847.64,
              latest_price: 203.35,
              latest_price_date: '2026-08-25',
              current_value: 37823.10,
              unrealized_pnl: 6975.46,
              unrealized_pnl_pct: 22.61,
              realized_pnl: 0.0,
              realized_pnl_pct: 0.0,
              net_pnl: 6975.46,
              net_pnl_pct: 22.61,
              xirr: 0.245,
              open_lots: [
                {
                  lot_id: 1,
                  buy_date: '2025-09-19',
                  quantity_original: 186.0,
                  quantity_remaining: 186.0,
                  cost_per_unit: 165.85,
                }
              ]
            }
          ],
          asset_allocation: { stock: 37823.10, cash: 5500.0 },
          sector_allocation: { Technology: 37823.10 },
        }),
      });
    });

    await page.route('*/**/api/v1/portfolio/annual_snapshot*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          year_label: 'CY 2026',
          start_date: '2026-01-01',
          end_date: '2026-08-25',
          total_income: 50000.0,
          total_expenses: 25000.0,
          investments_done: 20000.0,
          investments_closed: 0.0,
          net_worth_delta: 15000.0,
          net_worth_delta_pct: 37.5,
          taxes_and_fees: 715.64,
          net_savings: 25000.0,
          currency: 'EUR',
        }),
      });
    });

    await page.route('*/**/api/v1/snapshots*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('*/**/api/v1/categories*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('*/**/api/v1/cashflow*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            cashflow_id: 101,
            transaction_date: '2026-08-20',
            title: 'Monthly Salary',
            total_amount: 5000.0,
            currency: 'EUR',
            transaction_kind: 'INCOME',
            notes: 'Direct deposit',
            items: [
              {
                item_id: 1,
                category_name: 'Base Salary',
                category_type: 'INCOME',
                description: 'Tech Corp Net Pay',
                effective_label: 'INCOME',
                amount: 5000.0,
              }
            ],
            payments: [
              {
                account_id: 1,
                account_name: 'Main Checking Bank',
                account_currency: 'EUR',
                amount: 5000.0,
              }
            ]
          }
        ]),
      });
    });

    await page.route('*/**/api/v1/transactions*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            transaction_id: 201,
            transaction_date: '2026-08-25',
            asset_id: 4,
            asset_symbol: 'GROWW.BO',
            account_id: 2,
            account_name: 'Zerodha Trading Demat',
            account_currency: 'INR',
            funding_account_id: 1,
            funding_account_name: 'Main Checking Bank',
            funding_account_currency: 'EUR',
            transaction_type: 'buy',
            quantity: 186.0,
            price_per_unit: 162.0,
            total_amount: 30132.0,
            fees: 602.64,
            taxes: 113.0,
            notes: 'Portfolio rebalance',
          }
        ]),
      });
    });
  });

  test('Journey 1: Dashboard loads with net worth and account breakdown (Cash + Securities)', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Greenline|Portfolio|Tracker/i);

    // Verify navigation links in navbar
    await expect(page.getByRole('link', { name: 'Investments', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Cashflow', exact: true })).toBeVisible();

    // Verify accounts table renders Demat account with cash and stocks valuation breakdown
    await expect(page.getByRole('table').getByText('Zerodha Trading Demat')).toBeVisible();
    await expect(page.getByRole('table').getByText('Securities & Stocks')).toBeVisible();
    await expect(page.getByRole('table').getByText('Main Checking Bank')).toBeVisible();
    await expect(page.getByRole('table').getByText('Cash & Bank', { exact: true })).toBeVisible();
  });

  test('Journey 2: Holdings page renders production table columns and FIFO lots', async ({ page }) => {
    await page.goto('/investments/holdings');
    await expect(page.locator('h1')).toContainText(/Positions & Holdings/i);

    // Verify table headers
    await expect(page.getByText('Total Cost')).toBeVisible();
    await expect(page.getByText('Current Value')).toBeVisible();
    await expect(page.getByText('Net P&L', { exact: true })).toBeVisible();
    await expect(page.getByText('XIRR')).toBeVisible();

    // Verify holding data
    await expect(page.getByText('GROWW.BO')).toBeVisible();
    await expect(page.getByText('₹30,847.64')).toBeVisible();
    await expect(page.getByText('₹37,823.10')).toBeVisible();

    // Expand FIFO lot subrow
    await page.getByText('GROWW.BO').click();
    await expect(page.getByText(/FIFO Lots Breakdown for GROWW.BO/i)).toBeVisible();
    await expect(page.getByText('₹165.85')).toBeVisible();
  });

  test('Journey 3: Cashflow ledger renders day-to-day transactions and investment trades in unified ledger', async ({ page }) => {
    await page.goto('/cashflow/transactions');
    await expect(page.locator('h1')).toContainText(/Cashflow Transactions/i);

    // Day-to-day transaction
    await expect(page.getByText('Monthly Salary')).toBeVisible();
    await expect(page.getByText('Base Salary')).toBeVisible();

    // Investment trade directly in unified ledger
    await expect(page.getByText('GROWW.BO')).toBeVisible();
    await expect(page.getByText('Stock & ETF Purchases')).toBeVisible();
    await expect(page.getByText('Investment Fees & Charges')).toBeVisible();
    await expect(page.getByText('Taxes & Duties')).toBeVisible();
  });

  test('Journey 4: Privacy Mode Toggle deterministically masks and unmasks balances', async ({ page }) => {
    await page.goto('/');

    // Verify initial balance visibility in accounts table
    await expect(page.getByRole('table').getByText('Main Checking Bank')).toBeVisible();

    // Find Privacy toggle button (contains "Hide" text initially)
    const privacyBtn = page.getByRole('button', { name: /Hide|Show/i }).first();
    await expect(privacyBtn).toBeVisible();
    await expect(privacyBtn).toContainText(/Hide/i);

    // Click to mask balances
    await privacyBtn.click();
    await expect(privacyBtn).toContainText(/Show/i);

    // Assert that balances are masked
    await expect(page.getByText('••••').first()).toBeVisible();

    // Click to unmask balances
    await privacyBtn.click();
    await expect(privacyBtn).toContainText(/Hide/i);
    await expect(page.getByRole('table').getByText('Main Checking Bank')).toBeVisible();
  });
});
