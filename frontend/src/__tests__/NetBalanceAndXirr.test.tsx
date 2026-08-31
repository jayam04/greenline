import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

const mockHoldingsSummary = {
  total_net_worth: 25000,
  total_invested: 20000,
  total_current_value: 24000,
  cash_balance: 1000,
  total_realized_pnl: 500,
  total_unrealized_pnl: 4000,
  total_fees: 50,
  total_taxes: 20,
  portfolio_xirr: 0.185, // 18.50%
  top_holdings: [
    {
      asset_id: 1,
      symbol: "AAPL",
      name: "Apple Inc.",
      asset_type: "STOCK",
      sector: "Technology",
      currency: "USD",
      quantity_held: 10,
      avg_cost_price: 150,
      total_cost: 1500,
      latest_price: 180,
      latest_price_date: "2026-08-30",
      current_value: 1800,
      unrealized_pnl: 300,
      unrealized_pnl_pct: 20,
      realized_pnl: 0,
      realized_pnl_pct: 0,
      net_pnl: 300,
      net_pnl_pct: 20,
      xirr: 0.224,
      open_lots: [],
    },
  ],
  closed_holdings: [],
};

const mockAccounts = [
  { account_id: 1, account_name: "Chase Checking", currency: "USD", account_type: "CHECKING" },
  { account_id: 2, account_name: "Robinhood Cash", currency: "USD", account_type: "DEMAT" },
];

const mockCashflowTxs = [
  {
    cashflow_id: 101,
    transaction_date: "2026-08-01",
    title: "Salary Deposit",
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
    transaction_date: "2026-08-05",
    title: "Grocery Shopping",
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

const mockTradeTxs = [
  {
    transaction_id: 201,
    account_id: 2,
    account_name: "Robinhood Demat",
    account_currency: "USD",
    funding_account_id: 1,
    funding_account_name: "Chase Checking",
    funding_account_currency: "USD",
    transaction_type: "buy",
    transaction_date: "2026-08-10",
    asset_id: 1,
    asset_symbol: "AAPL",
    asset_name: "Apple Inc.",
    quantity: 10,
    price_per_unit: 150,
    total_amount: 1500,
    fees: 10,
    taxes: 0,
    notes: "Bought 10 AAPL"
  }
];

describe('Stack 3 Layer 4A: Net XIRR & Net Balance Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Net Portfolio XIRR summary KPI card and table footer in HoldingsPage', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/portfolio/summary') return mockHoldingsSummary;
      if (endpoint === '/settings') return { master_currency: "USD" };
      return {};
    });

    render(<HoldingsPage />);

    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    });

    // Check that Net Portfolio XIRR KPI card is present with 18.5%
    expect(screen.getByText(/Net Portfolio XIRR/i)).toBeInTheDocument();
    expect(screen.getByText('18.5%')).toBeInTheDocument();
  });

  it('calculates chronological running balance across cashflow and trade transactions', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/cashflow') return mockCashflowTxs;
      if (endpoint === '/transactions') return mockTradeTxs;
      if (endpoint === '/accounts') return mockAccounts;
      return {};
    });

    render(<CashflowTransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Salary Deposit')).toBeInTheDocument();
      expect(screen.getByText('Grocery Shopping')).toBeInTheDocument();
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    });

    // Check table header has Net Balance column
    expect(screen.getByText(/Net Balance/i)).toBeInTheDocument();

    // Verify chronological statement balances for Chase Checking:
    // Aug 01: +$5000 -> Running Bal: $5,000.00
    // Aug 05: -$200  -> Running Bal: $4,800.00
    // Aug 10: -$1510 -> Running Bal: $3,290.00
    expect(screen.getAllByText('$5,000.00').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('$4,800.00').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('$3,290.00').length).toBeGreaterThanOrEqual(1);
  });

  it('filters by specific account and updates net statement balances accordingly', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/cashflow') return mockCashflowTxs;
      if (endpoint === '/transactions') return mockTradeTxs;
      if (endpoint === '/accounts') return mockAccounts;
      return {};
    });

    render(<CashflowTransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Salary Deposit')).toBeInTheDocument();
    });

    // Select Chase Checking filter
    const accountSelect = screen.getByLabelText(/account-filter/i);
    fireEvent.change(accountSelect, { target: { value: '1' } });

    await waitFor(() => {
      // Running balance of latest transaction (Aug 10) on Chase Checking is $3,290.00
      expect(screen.getAllByText('$3,290.00').length).toBeGreaterThanOrEqual(1);
    });
  });
});
