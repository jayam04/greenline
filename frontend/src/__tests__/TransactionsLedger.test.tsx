import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CashflowTransactionsPage from '@/app/cashflow/transactions/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

const mockAccounts = [
  { account_id: 1, account_name: 'Main Checking Bank', currency: 'EUR', account_type: 'bank' },
  { account_id: 2, account_name: 'Zerodha Demat', currency: 'INR', account_type: 'demat' },
];

const mockCashflowTxs = [
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
  },
  {
    cashflow_id: 102,
    transaction_date: '2026-08-22',
    title: 'Whole Foods Market',
    total_amount: 150.0,
    currency: 'EUR',
    transaction_kind: 'EXPENSE',
    notes: 'Weekly fresh produce',
    items: [
      {
        item_id: 2,
        category_name: 'Groceries',
        category_type: 'EXPENSE',
        description: 'Organic groceries',
        effective_label: 'ESSENTIAL',
        amount: 150.0,
      }
    ],
    payments: [
      {
        account_id: 1,
        account_name: 'Main Checking Bank',
        account_currency: 'EUR',
        amount: -150.0,
      }
    ]
  }
];

const mockTradeTxs = [
  {
    transaction_id: 201,
    transaction_date: '2026-08-25',
    asset_id: 4,
    asset_symbol: 'GROWW.BO',
    account_id: 2,
    account_name: 'Zerodha Demat',
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
  },
  {
    transaction_id: 202,
    transaction_date: '2026-08-26',
    asset_id: 5,
    asset_symbol: 'TCS',
    account_id: 2,
    account_name: 'Zerodha Demat',
    account_currency: 'INR',
    funding_account_id: 1,
    funding_account_name: 'Main Checking Bank',
    funding_account_currency: 'EUR',
    transaction_type: 'sell',
    quantity: 50.0,
    price_per_unit: 3600.0,
    total_amount: 180000.0,
    fees: 200.0,
    taxes: 50.0,
    notes: 'Sell 50 TCS shares',
  }
];

describe('Cashflow Transactions Page (src/app/cashflow/transactions/page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/cashflow') return mockCashflowTxs;
      if (endpoint === '/transactions') return mockTradeTxs;
      if (endpoint === '/accounts') return mockAccounts;
      if (endpoint === '/categories') return [];
      if (endpoint === '/categories/tree') return [];
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });
  });

  it('renders all day-to-day and investment transactions directly with holdings delta in unified ledger', async () => {
    render(<CashflowTransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Cashflow Transactions')).toBeInTheDocument();
    });

    // Verify cashflow records exist directly
    expect(screen.getByText('Monthly Salary')).toBeInTheDocument();
    expect(screen.getByText('Base Salary')).toBeInTheDocument();
    expect(screen.getByText('Whole Foods Market')).toBeInTheDocument();
    expect(screen.getByText('Groceries')).toBeInTheDocument();

    // Verify buy trade record with positive holding delta (+186 GROWW.BO)
    expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    expect(screen.getByText('Stock & ETF Purchases')).toBeInTheDocument();
    expect(screen.getByText(/Bought x186 at/i)).toBeInTheDocument();
    expect(screen.getByText('(+186 GROWW.BO)')).toBeInTheDocument();

    // Verify sell trade record with negative holding delta (-50 TCS)
    expect(screen.getByText('TCS')).toBeInTheDocument();
    expect(screen.getByText('Stock Sale Proceeds')).toBeInTheDocument();
    expect(screen.getByText(/Sold x50 at/i)).toBeInTheDocument();
    expect(screen.getByText('(-50 TCS)')).toBeInTheDocument();

    // Check fee line item
    expect(screen.getAllByText('Investment Fees & Charges').length).toBeGreaterThanOrEqual(1);

    // Check tax line item
    expect(screen.getAllByText('Taxes & Duties').length).toBeGreaterThanOrEqual(1);

    // Check payment account display
    expect(screen.getAllByText(/Main Checking Bank/i).length).toBeGreaterThanOrEqual(1);
  });

  it('filters unified transactions when typing in search input', async () => {
    render(<CashflowTransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Monthly Salary')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search merchant, account, category/i);
    fireEvent.change(searchInput, { target: { value: 'GROWW' } });

    expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    expect(screen.queryByText('Monthly Salary')).not.toBeInTheDocument();
    expect(screen.queryByText('Whole Foods Market')).not.toBeInTheDocument();
  });
});
