import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import HoldingsPage from '@/app/investments/holdings/page';
import CashflowTransactionsPage from '@/app/cashflow/transactions/page';
import * as api from '@/lib/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  removeAuthToken: vi.fn(),
}));

const mockAccounts = [
  { account_id: 1, account_name: "Chase Checking", currency: "USD", account_type: "bank" },
  { account_id: 2, account_name: "Fidelity Demat", currency: "USD", account_type: "demat" },
  { account_id: 3, account_name: "Emergency Savings", currency: "USD", account_type: "bank" },
];

describe('Stack 3 Layer 4: Net Balance & XIRR Comprehensive Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('1. Chronological Running Balances in Cashflow Ledger', () => {
    it('calculates running balances step-by-step across deposits, expenses, and investment trades', async () => {
      const cashflowData = [
        {
          cashflow_id: 101,
          transaction_date: "2026-08-01",
          title: "Paycheck Deposit",
          total_amount: 5000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [
            { payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 5000 }
          ],
          items: [
            { item_id: 1, category_name: "Salary", category_type: "INCOME", effective_label: "ESSENTIAL", amount: 5000 }
          ]
        },
        {
          cashflow_id: 102,
          transaction_date: "2026-08-03",
          title: "Supermarket Groceries",
          total_amount: 200,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [
            { payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -200 }
          ],
          items: [
            { item_id: 2, category_name: "Groceries", category_type: "EXPENSE", effective_label: "ESSENTIAL", amount: 200 }
          ]
        }
      ];

      const tradeData = [
        {
          transaction_id: 201,
          account_id: 2,
          account_name: "Fidelity Demat",
          account_currency: "USD",
          funding_account_id: 1,
          funding_account_name: "Chase Checking",
          funding_account_currency: "USD",
          transaction_type: "buy",
          transaction_date: "2026-08-06",
          asset_id: 1,
          asset_symbol: "AAPL",
          asset_name: "Apple Inc.",
          quantity: 10,
          price_per_unit: 150,
          total_amount: 1500,
          fees: 10,
          taxes: 0,
          notes: "Bought 10 AAPL"
        },
        {
          transaction_id: 202,
          account_id: 2,
          account_name: "Fidelity Demat",
          account_currency: "USD",
          funding_account_id: 1,
          funding_account_name: "Chase Checking",
          funding_account_currency: "USD",
          transaction_type: "sell",
          transaction_date: "2026-08-10",
          asset_id: 1,
          asset_symbol: "AAPL",
          asset_name: "Apple Inc.",
          quantity: 5,
          price_per_unit: 180,
          total_amount: 900,
          fees: 5,
          taxes: 0,
          notes: "Sold 5 AAPL"
        },
        {
          transaction_id: 203,
          account_id: 2,
          account_name: "Fidelity Demat",
          account_currency: "USD",
          funding_account_id: 1,
          funding_account_name: "Chase Checking",
          funding_account_currency: "USD",
          transaction_type: "dividend",
          transaction_date: "2026-08-12",
          asset_id: 1,
          asset_symbol: "AAPL",
          asset_name: "Apple Inc.",
          quantity: 5,
          price_per_unit: 10,
          total_amount: 50,
          fees: 0,
          taxes: 5,
          notes: "Dividend payout net $45"
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return cashflowData;
        if (endpoint === '/transactions') return tradeData;
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Paycheck Deposit')).toBeInTheDocument();
        expect(screen.getByText('Supermarket Groceries')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(5);

      // Verify reverse-chronological rows with exact computed running balance:
      // Row 0: Aug 12 Dividend -> +$45 net (4185 + 45 = 4230)
      expect(within(rows[0]).getByText('2026-08-12')).toBeInTheDocument();
      expect(within(rows[0]).getByText(/Bal:\s*\$4,230\.00/i)).toBeInTheDocument();

      // Row 1: Aug 10 Sell Trade -> +$895 net (3290 + 895 = 4185)
      expect(within(rows[1]).getByText('2026-08-10')).toBeInTheDocument();
      expect(within(rows[1]).getByText(/Bal:\s*\$4,185\.00/i)).toBeInTheDocument();

      // Row 2: Aug 06 Buy Trade -> -$1,510 total (4800 - 1510 = 3290)
      expect(within(rows[2]).getByText('2026-08-06')).toBeInTheDocument();
      expect(within(rows[2]).getByText(/Bal:\s*\$3,290\.00/i)).toBeInTheDocument();

      // Row 3: Aug 03 Groceries -> -$200 (5000 - 200 = 4800)
      expect(within(rows[3]).getByText('2026-08-03')).toBeInTheDocument();
      expect(within(rows[3]).getByText(/Bal:\s*\$4,800\.00/i)).toBeInTheDocument();

      // Row 4: Aug 01 Paycheck Deposit -> +$5000 (0 + 5000 = 5000)
      expect(within(rows[4]).getByText('2026-08-01')).toBeInTheDocument();
      expect(within(rows[4]).getByText(/Bal:\s*\$5,000\.00/i)).toBeInTheDocument();
    });

    it('correctly handles multiple transactions on the same date with deterministic ordering', async () => {
      // 3 transactions on the same date: 2026-08-05
      const sameDayCashflows = [
        {
          cashflow_id: 101,
          transaction_date: "2026-08-05",
          title: "Initial Transfer In",
          total_amount: 1000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1000 }],
          items: [{ item_id: 1, category_name: "Transfer", category_type: "INCOME", amount: 1000 }]
        },
        {
          cashflow_id: 102,
          transaction_date: "2026-08-05",
          title: "Lunch Meal",
          total_amount: 50,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -50 }],
          items: [{ item_id: 2, category_name: "Food", category_type: "EXPENSE", amount: 50 }]
        }
      ];

      const sameDayTrades = [
        {
          transaction_id: 201,
          account_id: 2,
          account_name: "Fidelity Demat",
          account_currency: "USD",
          funding_account_id: 1,
          funding_account_name: "Chase Checking",
          funding_account_currency: "USD",
          transaction_type: "buy",
          transaction_date: "2026-08-05",
          asset_id: 1,
          asset_symbol: "AAPL",
          asset_name: "Apple Inc.",
          quantity: 2,
          price_per_unit: 150,
          total_amount: 300,
          fees: 0,
          taxes: 0,
          notes: "Bought 2 AAPL"
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return sameDayCashflows;
        if (endpoint === '/transactions') return sameDayTrades;
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Initial Transfer In')).toBeInTheDocument();
        expect(screen.getByText('Lunch Meal')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(3);

      // Chronological sequence on 2026-08-05:
      // 1. cf_101: +$1,000 -> Bal: $1,000.00
      // 2. cf_102: -$50    -> Bal: $950.00
      // 3. tr_201: -$300   -> Bal: $650.00
      // Reversed presentation (newest first):
      expect(within(rows[0]).getByText(/Bal:\s*\$650\.00/i)).toBeInTheDocument();
      expect(within(rows[1]).getByText(/Bal:\s*\$950\.00/i)).toBeInTheDocument();
      expect(within(rows[2]).getByText(/Bal:\s*\$1,000\.00/i)).toBeInTheDocument();
    });

    it('deterministically orders same-day transactions (inflows before outflows) independent of database IDs or array order', async () => {
      // Jan 1: deposit +1000 (id 202), expense -200 (id 201), expense -100 (id 203)
      // Provided in scrambled order with id 201 (-200) having a lower ID than deposit (202)
      const scrambledSameDayCashflows = [
        {
          cashflow_id: 203,
          transaction_date: "2026-01-01",
          title: "Minor Expense",
          total_amount: 100,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -100 }],
          items: [{ item_id: 3, category_name: "Shopping", category_type: "EXPENSE", amount: 100 }]
        },
        {
          cashflow_id: 201,
          transaction_date: "2026-01-01",
          title: "Utility Expense",
          total_amount: 200,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -200 }],
          items: [{ item_id: 1, category_name: "Bills", category_type: "EXPENSE", amount: 200 }]
        },
        {
          cashflow_id: 202,
          transaction_date: "2026-01-01",
          title: "Initial Deposit",
          total_amount: 1000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1000 }],
          items: [{ item_id: 2, category_name: "Deposit", category_type: "INCOME", amount: 1000 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return scrambledSameDayCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Initial Deposit')).toBeInTheDocument();
        expect(screen.getByText('Utility Expense')).toBeInTheDocument();
        expect(screen.getByText('Minor Expense')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(3);

      // Deterministic chronological execution on 2026-01-01:
      // Inflow first: +1000 -> Bal: $1,000.00
      // Outflows next: -200 -> Bal: $800.00
      // Outflows next: -100 -> Bal: $700.00
      // Reversed presentation (newest first):
      // Row 0: Minor Expense (-100) -> Bal: $700.00
      // Row 1: Utility Expense (-200) -> Bal: $800.00
      // Row 2: Initial Deposit (+1000) -> Bal: $1,000.00
      expect(within(rows[0]).getByText('Minor Expense')).toBeInTheDocument();
      expect(within(rows[0]).getByText(/Bal:\s*\$700\.00/i)).toBeInTheDocument();

      expect(within(rows[1]).getByText('Utility Expense')).toBeInTheDocument();
      expect(within(rows[1]).getByText(/Bal:\s*\$800\.00/i)).toBeInTheDocument();

      expect(within(rows[2]).getByText('Initial Deposit')).toBeInTheDocument();
      expect(within(rows[2]).getByText(/Bal:\s*\$1,000\.00/i)).toBeInTheDocument();
    });

    it('handles split payments across multiple accounts within a single transaction', async () => {
      const splitCashflow = [
        {
          cashflow_id: 101,
          transaction_date: "2026-08-01",
          title: "Funding Accounts",
          total_amount: 2000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [
            { payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1500 },
            { payment_id: 2, account_id: 3, account_name: "Emergency Savings", account_currency: "USD", amount: 500 }
          ],
          items: [{ item_id: 1, category_name: "Deposit", category_type: "INCOME", amount: 2000 }]
        },
        {
          cashflow_id: 102,
          transaction_date: "2026-08-04",
          title: "Furniture Purchase Split",
          total_amount: 800,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [
            { payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -600 },
            { payment_id: 4, account_id: 3, account_name: "Emergency Savings", account_currency: "USD", amount: -200 }
          ],
          items: [{ item_id: 2, category_name: "Home", category_type: "EXPENSE", amount: 800 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return splitCashflow;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Furniture Purchase Split')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(2);

      // Latest row (Row 0): Furniture Purchase Split
      // Checking balance: 1500 - 600 = $900.00
      // Savings balance: 500 - 200 = $300.00
      expect(within(rows[0]).getByText(/Bal:\s*\$900\.00/i)).toBeInTheDocument();
      expect(within(rows[0]).getByText(/Bal:\s*\$300\.00/i)).toBeInTheDocument();

      // Older row (Row 1): Funding Accounts
      // Checking balance: $1,500.00
      // Savings balance: $500.00
      expect(within(rows[1]).getByText(/Bal:\s*\$1,500\.00/i)).toBeInTheDocument();
      expect(within(rows[1]).getByText(/Bal:\s*\$500\.00/i)).toBeInTheDocument();
    });

    it('correctly computes and displays negative running balances (overdraft)', async () => {
      const overdraftCashflows = [
        {
          cashflow_id: 101,
          transaction_date: "2026-08-01",
          title: "Small Deposit",
          total_amount: 100,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 100 }],
          items: [{ item_id: 1, category_name: "Deposit", category_type: "INCOME", amount: 100 }]
        },
        {
          cashflow_id: 102,
          transaction_date: "2026-08-03",
          title: "Overdraft Expense",
          total_amount: 250,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -250 }],
          items: [{ item_id: 2, category_name: "Utilities", category_type: "EXPENSE", amount: 250 }]
        },
        {
          cashflow_id: 103,
          transaction_date: "2026-08-05",
          title: "Recovery Deposit",
          total_amount: 500,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 500 }],
          items: [{ item_id: 3, category_name: "Deposit", category_type: "INCOME", amount: 500 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return overdraftCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Overdraft Expense')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(3);

      // Row 0: Recovery -> 100 - 250 + 500 = $350.00
      expect(within(rows[0]).getByText(/Bal:\s*\$350\.00/i)).toBeInTheDocument();
      // Row 1: Overdraft -> 100 - 250 = -$150.00
      expect(within(rows[1]).getByText(/Bal:\s*-\$150\.00/i)).toBeInTheDocument();
      // Row 2: Small Deposit -> $100.00
      expect(within(rows[2]).getByText(/Bal:\s*\$100\.00/i)).toBeInTheDocument();
    });

    it('computes chronological running balances even when API returns out-of-order records', async () => {
      // Scrambled dates from API: Aug 15, Aug 01, Aug 10, Aug 05
      const scrambledCashflows = [
        {
          cashflow_id: 104,
          transaction_date: "2026-08-15",
          title: "Mid-month Utility",
          total_amount: 100,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 4, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -100 }],
          items: [{ item_id: 4, category_name: "Bills", category_type: "EXPENSE", amount: 100 }]
        },
        {
          cashflow_id: 101,
          transaction_date: "2026-08-01",
          title: "Starting Balance",
          total_amount: 1000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1000 }],
          items: [{ item_id: 1, category_name: "Deposit", category_type: "INCOME", amount: 1000 }]
        },
        {
          cashflow_id: 103,
          transaction_date: "2026-08-10",
          title: "Car Insurance",
          total_amount: 200,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -200 }],
          items: [{ item_id: 3, category_name: "Insurance", category_type: "EXPENSE", amount: 200 }]
        },
        {
          cashflow_id: 102,
          transaction_date: "2026-08-05",
          title: "Weekly Food",
          total_amount: 150,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -150 }],
          items: [{ item_id: 2, category_name: "Food", category_type: "EXPENSE", amount: 150 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return scrambledCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Starting Balance')).toBeInTheDocument();
      });

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const rows = tbody.querySelectorAll('tr');
      expect(rows.length).toBe(4);

      // Ledger must be sorted reverse-chronological with correct chronological balances:
      // Row 0 (Aug 15): 1000 - 150 - 200 - 100 = $550.00
      expect(within(rows[0]).getByText('2026-08-15')).toBeInTheDocument();
      expect(within(rows[0]).getByText(/Bal:\s*\$550\.00/i)).toBeInTheDocument();

      // Row 1 (Aug 10): 1000 - 150 - 200 = $650.00
      expect(within(rows[1]).getByText('2026-08-10')).toBeInTheDocument();
      expect(within(rows[1]).getByText(/Bal:\s*\$650\.00/i)).toBeInTheDocument();

      // Row 2 (Aug 05): 1000 - 150 = $850.00
      expect(within(rows[2]).getByText('2026-08-05')).toBeInTheDocument();
      expect(within(rows[2]).getByText(/Bal:\s*\$850\.00/i)).toBeInTheDocument();

      // Row 3 (Aug 01): $1,000.00
      expect(within(rows[3]).getByText('2026-08-01')).toBeInTheDocument();
      expect(within(rows[3]).getByText(/Bal:\s*\$1,000\.00/i)).toBeInTheDocument();
    });

    it('mathematically asserts running balance continuity from transaction amounts', async () => {
      const mathCashflows = [
        {
          cashflow_id: 401,
          transaction_date: "2026-04-01",
          title: "Income A",
          total_amount: 1000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1000 }],
          items: [{ item_id: 1, category_name: "Deposit", category_type: "INCOME", amount: 1000 }]
        },
        {
          cashflow_id: 402,
          transaction_date: "2026-04-02",
          title: "Spend B",
          total_amount: 350,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 2, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -350 }],
          items: [{ item_id: 2, category_name: "Shopping", category_type: "EXPENSE", amount: 350 }]
        },
        {
          cashflow_id: 403,
          transaction_date: "2026-04-03",
          title: "Spend C",
          total_amount: 150,
          currency: "USD",
          transaction_kind: "EXPENSE",
          payments: [{ payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -150 }],
          items: [{ item_id: 3, category_name: "Food", category_type: "EXPENSE", amount: 150 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return mathCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income A')).toBeInTheDocument();
      });

      const badges = screen.getAllByTestId('payment-badge');
      expect(badges.length).toBe(3);

      const balRow0 = parseFloat(badges[0].getAttribute('data-running-balance') || '0');
      const amtRow0 = parseFloat(badges[0].getAttribute('data-amount') || '0');

      const balRow1 = parseFloat(badges[1].getAttribute('data-running-balance') || '0');
      const amtRow1 = parseFloat(badges[1].getAttribute('data-amount') || '0');

      const balRow2 = parseFloat(badges[2].getAttribute('data-running-balance') || '0');
      const amtRow2 = parseFloat(badges[2].getAttribute('data-amount') || '0');

      // Math continuity assertions:
      // Row 2 (oldest): bal2 = amt2 = 1000
      expect(balRow2).toBe(1000);
      expect(amtRow2).toBe(1000);

      // Row 1: bal1 = bal2 + amtRow1 = 1000 + (-350) = 650
      expect(balRow1).toBe(balRow2 + amtRow1);
      expect(balRow1).toBe(650);

      // Row 0: bal0 = bal1 + amtRow0 = 650 + (-150) = 500
      expect(balRow0).toBe(balRow1 + amtRow0);
      expect(balRow0).toBe(500);
    });
  });

  describe('2. Account Filtering & Statement Balance KPI', () => {
    const multiAccountCashflows = [
      {
        cashflow_id: 101,
        transaction_date: "2026-08-01",
        title: "Checking Salary",
        total_amount: 3000,
        currency: "USD",
        transaction_kind: "INCOME",
        payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 3000 }],
        items: [{ item_id: 1, category_name: "Salary", category_type: "INCOME", amount: 3000 }]
      },
      {
        cashflow_id: 102,
        transaction_date: "2026-08-02",
        title: "Savings Initial Deposit",
        total_amount: 1500,
        currency: "USD",
        transaction_kind: "INCOME",
        payments: [{ payment_id: 2, account_id: 3, account_name: "Emergency Savings", account_currency: "USD", amount: 1500 }],
        items: [{ item_id: 2, category_name: "Savings", category_type: "INCOME", amount: 1500 }]
      },
      {
        cashflow_id: 103,
        transaction_date: "2026-08-04",
        title: "Transfer Checking to Savings",
        total_amount: 500,
        currency: "USD",
        transaction_kind: "TRANSFER",
        payments: [
          { payment_id: 3, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: -500 },
          { payment_id: 4, account_id: 3, account_name: "Emergency Savings", account_currency: "USD", amount: 500 }
        ],
        items: [{ item_id: 3, category_name: "Transfer", category_type: "TRANSFER", amount: 500 }]
      }
    ];

    it('filters ledger to selected account and hides unrelated account transactions', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return multiAccountCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Checking Salary')).toBeInTheDocument();
        expect(screen.getByText('Savings Initial Deposit')).toBeInTheDocument();
        expect(screen.getByText('Transfer Checking to Savings')).toBeInTheDocument();
      });

      // Filter by Chase Checking (account_id: 1)
      const accountSelect = screen.getByLabelText(/account-filter/i);
      fireEvent.change(accountSelect, { target: { value: '1' } });

      await waitFor(() => {
        // Checking Salary and Transfer are visible
        expect(screen.getByText('Checking Salary')).toBeInTheDocument();
        expect(screen.getByText('Transfer Checking to Savings')).toBeInTheDocument();
        // Savings Initial Deposit must completely disappear
        expect(screen.queryByText('Savings Initial Deposit')).not.toBeInTheDocument();
      });
    });

    it('displays current statement balance badge for selected account and updates when switching accounts', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return multiAccountCashflows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Checking Salary')).toBeInTheDocument();
      });

      const accountSelect = screen.getByLabelText(/account-filter/i);

      // Select Chase Checking (id: 1) -> 3000 - 500 = $2,500.00
      fireEvent.change(accountSelect, { target: { value: '1' } });
      await waitFor(() => {
        expect(screen.getByText(/Chase Checking:/i)).toBeInTheDocument();
        expect(screen.getByText('$2,500.00')).toBeInTheDocument();
      });

      // Switch to Emergency Savings (id: 3) -> 1500 + 500 = $2,000.00
      fireEvent.change(accountSelect, { target: { value: '3' } });
      await waitFor(() => {
        expect(screen.getByText(/Emergency Savings:/i)).toBeInTheDocument();
        expect(screen.getByText('$2,000.00')).toBeInTheDocument();
        expect(screen.queryByText(/Chase Checking:/i)).not.toBeInTheDocument();
      });

      // Clear filter back to ALL
      fireEvent.change(accountSelect, { target: { value: 'ALL' } });
      await waitFor(() => {
        expect(screen.queryByText(/Emergency Savings:/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/Chase Checking:/i)).not.toBeInTheDocument();
        expect(screen.getByText('Checking Salary')).toBeInTheDocument();
        expect(screen.getByText('Savings Initial Deposit')).toBeInTheDocument();
      });
    });

    it('strictly isolates Account A (+1000) and Account B (+500) during filtering, switching, and clearing', async () => {
      const accountIsolatedFlows = [
        {
          cashflow_id: 301,
          transaction_date: "2026-03-01",
          title: "Account A Funding",
          total_amount: 1000,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 1, account_id: 1, account_name: "Chase Checking", account_currency: "USD", amount: 1000 }],
          items: [{ item_id: 1, category_name: "Deposit", category_type: "INCOME", amount: 1000 }]
        },
        {
          cashflow_id: 302,
          transaction_date: "2026-03-02",
          title: "Account B Funding",
          total_amount: 500,
          currency: "USD",
          transaction_kind: "INCOME",
          payments: [{ payment_id: 2, account_id: 3, account_name: "Emergency Savings", account_currency: "USD", amount: 500 }],
          items: [{ item_id: 2, category_name: "Deposit", category_type: "INCOME", amount: 500 }]
        }
      ];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/cashflow') return accountIsolatedFlows;
        if (endpoint === '/transactions') return [];
        if (endpoint === '/accounts') return mockAccounts;
        return {};
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Account A Funding')).toBeInTheDocument();
        expect(screen.getByText('Account B Funding')).toBeInTheDocument();
      });

      const accountSelect = screen.getByLabelText(/account-filter/i);

      // 1. Filter to Account A (id: 1)
      fireEvent.change(accountSelect, { target: { value: '1' } });
      await waitFor(() => {
        // Account B transactions must not contribute to the balance
        expect(screen.queryByText('Account B Funding')).not.toBeInTheDocument();
        expect(screen.getByText('Account A Funding')).toBeInTheDocument();
        // The displayed running balance must be calculated only from Account A
        expect(screen.getByTestId('selected-account-balance')).toHaveTextContent(/Chase Checking:/i);
        expect(screen.getByTestId('selected-account-balance')).toHaveTextContent('$1,000.00');
        expect(screen.getByTestId('selected-account-balance')).not.toHaveTextContent('$1,500.00');
      });

      // 2. Switching to Account B (id: 3) should recalculate correctly
      fireEvent.change(accountSelect, { target: { value: '3' } });
      await waitFor(() => {
        expect(screen.queryByText('Account A Funding')).not.toBeInTheDocument();
        expect(screen.getByText('Account B Funding')).toBeInTheDocument();
        expect(screen.getByTestId('selected-account-balance')).toHaveTextContent(/Emergency Savings:/i);
        expect(screen.getByTestId('selected-account-balance')).toHaveTextContent('$500.00');
      });

      // 3. Clearing the filter should restore the combined result
      fireEvent.change(accountSelect, { target: { value: 'ALL' } });
      await waitFor(() => {
        expect(screen.queryByTestId('selected-account-balance')).not.toBeInTheDocument();
        expect(screen.getByText('Account A Funding')).toBeInTheDocument();
        expect(screen.getByText('Account B Funding')).toBeInTheDocument();
      });
    });
  });

  describe('3. Net Portfolio XIRR & Precision Formatting', () => {
    it('renders positive Net Portfolio XIRR with proper precision and visual indicator', async () => {
      const summaryPositive = {
        total_net_worth: 25000,
        total_invested: 20000,
        total_current_value: 24000,
        cash_balance: 1000,
        total_realized_pnl: 500,
        total_unrealized_pnl: 4000,
        total_fees: 50,
        total_taxes: 20,
        portfolio_xirr: 0.185, // 18.5%
        asset_allocation: {},
        top_holdings: [
          {
            asset_id: 1,
            symbol: "AAPL",
            name: "Apple Inc.",
            asset_type: "STOCK",
            currency: "USD",
            quantity_held: 10,
            avg_cost_price: 150,
            total_cost: 1500,
            latest_price: 180,
            current_value: 1800,
            unrealized_pnl: 300,
            unrealized_pnl_pct: 20,
            net_pnl: 300,
            net_pnl_pct: 20,
            xirr: 0.224, // 22.4%
            open_lots: []
          }
        ],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return summaryPositive;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
      });

      // KPI card check
      expect(screen.getByText(/Net Portfolio XIRR/i)).toBeInTheDocument();
      expect(screen.getByText('18.5%')).toBeInTheDocument();

      // Per-holding XIRR in table
      expect(screen.getByText('22.4%')).toBeInTheDocument();
    });

    it('renders negative Net Portfolio XIRR with proper precision and negative indicator', async () => {
      const summaryNegative = {
        total_net_worth: 18000,
        total_invested: 20000,
        total_current_value: 17500,
        cash_balance: 500,
        total_realized_pnl: -200,
        total_unrealized_pnl: -2500,
        total_fees: 30,
        total_taxes: 0,
        portfolio_xirr: -0.062, // -6.2%
        asset_allocation: {},
        top_holdings: [
          {
            asset_id: 2,
            symbol: "TSLA",
            name: "Tesla Inc.",
            asset_type: "STOCK",
            currency: "USD",
            quantity_held: 5,
            avg_cost_price: 250,
            total_cost: 1250,
            latest_price: 210,
            current_value: 1050,
            unrealized_pnl: -200,
            unrealized_pnl_pct: -16,
            net_pnl: -200,
            net_pnl_pct: -16,
            xirr: -0.041, // -4.1%
            open_lots: []
          }
        ],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return summaryNegative;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Tesla Inc.')).toBeInTheDocument();
      });

      // KPI card check (formatXirr formats absolute percentage with negative arrow indicator)
      expect(screen.getByText(/Net Portfolio XIRR/i)).toBeInTheDocument();
      expect(screen.getByText('6.2%')).toBeInTheDocument();

      // Per-holding XIRR in table
      expect(screen.getByText('4.1%')).toBeInTheDocument();
    });

    it('handles missing, null, undefined, or NaN XIRR gracefully', async () => {
      const summaryNullXirr = {
        total_net_worth: 5000,
        total_invested: 5000,
        total_current_value: 5000,
        cash_balance: 0,
        total_realized_pnl: 0,
        total_unrealized_pnl: 0,
        portfolio_xirr: null,
        asset_allocation: {},
        top_holdings: [
          {
            asset_id: 3,
            symbol: "NEWSTOCK",
            name: "New Asset Co.",
            asset_type: "STOCK",
            currency: "USD",
            quantity_held: 1,
            avg_cost_price: 100,
            total_cost: 100,
            latest_price: 100,
            current_value: 100,
            unrealized_pnl: 0,
            unrealized_pnl_pct: 0,
            net_pnl: 0,
            net_pnl_pct: 0,
            xirr: null,
            open_lots: []
          }
        ],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return summaryNullXirr;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('New Asset Co.')).toBeInTheDocument();
      });

      // KPI card shows "-" fallback
      expect(screen.getByText(/Net Portfolio XIRR/i)).toBeInTheDocument();
      const kpiCard = screen.getByText(/Net Portfolio XIRR/i).closest('.getquin-card') as HTMLElement;
      expect(within(kpiCard).getByText('-')).toBeInTheDocument();

      // Holding row XIRR column shows "-" fallback
      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const row = tbody.querySelector('tr')!;
      const cells = row.querySelectorAll('td');
      const xirrCell = cells[cells.length - 1];
      expect(within(xirrCell).getByText('-')).toBeInTheDocument();
    });

    it('handles empty portfolio case correctly', async () => {
      const emptySummary = {
        total_net_worth: 0,
        total_invested: 0,
        total_current_value: 0,
        cash_balance: 0,
        total_realized_pnl: 0,
        total_unrealized_pnl: 0,
        portfolio_xirr: null,
        asset_allocation: {},
        top_holdings: [],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return emptySummary;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('No active holdings logged.')).toBeInTheDocument();
      });

      // KPI card shows "-"
      const kpiCard = screen.getByText(/Net Portfolio XIRR/i).closest('.getquin-card') as HTMLElement;
      expect(within(kpiCard).getByText('-')).toBeInTheDocument();
    });

    it('verifies boundary and overflow precision formatting for extreme XIRR values', async () => {
      const summaryExtreme = {
        total_net_worth: 100000,
        total_invested: 1000,
        total_current_value: 100000,
        cash_balance: 0,
        total_realized_pnl: 0,
        total_unrealized_pnl: 99000,
        portfolio_xirr: 12.5, // 1250% -> > 999%
        asset_allocation: {},
        top_holdings: [
          {
            asset_id: 4,
            symbol: "MOON",
            name: "Moonshot Crypto",
            asset_type: "CRYPTO",
            currency: "USD",
            quantity_held: 1,
            avg_cost_price: 10,
            total_cost: 10,
            latest_price: 1500,
            current_value: 1500,
            unrealized_pnl: 1490,
            unrealized_pnl_pct: 14900,
            net_pnl: 1490,
            net_pnl_pct: 14900,
            xirr: 14.9, // 1490% -> > 999%
            open_lots: []
          }
        ],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return summaryExtreme;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Moonshot Crypto')).toBeInTheDocument();
      });

      // Overflows (> 999%) formatted as "999%+"
      const kpiCard = screen.getByText(/Net Portfolio XIRR/i).closest('.getquin-card') as HTMLElement;
      expect(within(kpiCard).getByText('999%+')).toBeInTheDocument();

      const tbody = screen.getByRole('table').querySelector('tbody')!;
      const row = tbody.querySelector('tr')!;
      const cells = row.querySelectorAll('td');
      const xirrCell = cells[cells.length - 1];
      expect(within(xirrCell).getByText('999%+')).toBeInTheDocument();
    });

    it('handles invalid and non-finite XIRR values (Infinity, -Infinity, NaN) gracefully', async () => {
      const summaryNonFinite = {
        total_net_worth: 10000,
        total_invested: 10000,
        total_current_value: 10000,
        cash_balance: 0,
        total_realized_pnl: 0,
        total_unrealized_pnl: 0,
        portfolio_xirr: Infinity,
        asset_allocation: {},
        top_holdings: [
          {
            asset_id: 5,
            symbol: "DIVZERO",
            name: "Divergent Holding",
            asset_type: "STOCK",
            currency: "USD",
            quantity_held: 1,
            avg_cost_price: 100,
            total_cost: 100,
            latest_price: 100,
            current_value: 100,
            unrealized_pnl: 0,
            unrealized_pnl_pct: 0,
            net_pnl: 0,
            net_pnl_pct: 0,
            xirr: -Infinity,
            open_lots: []
          }
        ],
        closed_holdings: []
      };

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint === '/portfolio/summary') return summaryNonFinite;
        if (endpoint === '/settings') return { master_currency: "USD" };
        return {};
      });

      render(<HoldingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Divergent Holding')).toBeInTheDocument();
      });

      // KPI card shows "-" fallback for Infinity
      expect(screen.getByTestId('kpi-portfolio-xirr')).toBeInTheDocument();
      expect(screen.getByTestId('kpi-portfolio-xirr')).toHaveTextContent('-');

      // Holding row shows "-" fallback for -Infinity
      const xirrCell = screen.getByTestId('holding-xirr-cell');
      expect(xirrCell).toHaveTextContent('-');
    });
  });
});
