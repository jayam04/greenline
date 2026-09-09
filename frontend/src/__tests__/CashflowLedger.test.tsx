import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { isCategoryAllowedForKind } from '@/components/CashflowModal';
import { ThemeProvider } from '@/components/ThemeProvider';
import CashflowPage from '@/app/cashflow/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

describe('Cashflow Category Directional Filtering (Issue #3)', () => {
  const dividendCat = { category_id: 1, name: 'Dividends', category_type: 'INVESTMENT', level: 1 };
  const stakingCat = { category_id: 2, name: 'Interest & Staking', category_type: 'INVESTMENT', level: 1 };
  const stockPurchaseCat = { category_id: 3, name: 'Stock & ETF Purchases', category_type: 'INVESTMENT', level: 1 };
  const sipCat = { category_id: 4, name: 'Mutual Funds & SIPs', category_type: 'INVESTMENT', level: 1 };
  const salaryCat = { category_id: 5, name: 'Base Salary', category_type: 'INCOME', level: 1 };
  const groceryCat = { category_id: 6, name: 'Groceries', category_type: 'EXPENSE', level: 1 };

  it('allows income-friendly investment categories in INCOME mode and excludes spend-only investment categories', () => {
    expect(isCategoryAllowedForKind(dividendCat, 'INCOME')).toBe(true);
    expect(isCategoryAllowedForKind(stakingCat, 'INCOME')).toBe(true);
    expect(isCategoryAllowedForKind(salaryCat, 'INCOME')).toBe(true);

    // Spend-only investment categories should NOT show in Income mode
    expect(isCategoryAllowedForKind(stockPurchaseCat, 'INCOME')).toBe(false);
    expect(isCategoryAllowedForKind(sipCat, 'INCOME')).toBe(false);
    expect(isCategoryAllowedForKind(groceryCat, 'INCOME')).toBe(false);
  });

  it('allows spend-friendly investment categories in EXPENSE mode and excludes income-only investment categories', () => {
    expect(isCategoryAllowedForKind(stockPurchaseCat, 'EXPENSE')).toBe(true);
    expect(isCategoryAllowedForKind(sipCat, 'EXPENSE')).toBe(true);
    expect(isCategoryAllowedForKind(groceryCat, 'EXPENSE')).toBe(true);

    // Income-only investment categories should NOT show in Expense mode
    expect(isCategoryAllowedForKind(dividendCat, 'EXPENSE')).toBe(false);
    expect(isCategoryAllowedForKind(stakingCat, 'EXPENSE')).toBe(false);
    expect(isCategoryAllowedForKind(salaryCat, 'EXPENSE')).toBe(false);
  });
});

describe('Cashflow Overview Page (src/app/cashflow/page.tsx) Unified Transactions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith('/cashflow/summary')) {
        return {
          total_income: 5000,
          total_expenses: 150,
          total_invested: 30132,
          net_savings: 4850,
          savings_rate_pct: 97,
          breakdown_by_label: {},
          top_expense_categories: [],
        };
      }
      if (endpoint.startsWith('/cashflow/sankey')) {
        return { nodes: [], links: [] };
      }
      if (endpoint.startsWith('/cashflow')) {
        return [
          {
            cashflow_id: 101,
            transaction_date: '2026-08-20',
            title: 'Monthly Salary',
            total_amount: 5000.0,
            currency: 'EUR',
            transaction_kind: 'INCOME',
            notes: 'Direct deposit',
            items: [
              { category_name: 'Base Salary', category_type: 'INCOME', amount: 5000.0 }
            ],
            payments: [
              { account_id: 1, account_name: 'Main Checking Bank', amount: 5000.0 }
            ]
          }
        ];
      }
      if (endpoint === '/transactions') {
        return [
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
            transaction_type: 'buy',
            quantity: 186.0,
            price_per_unit: 162.0,
            total_amount: 30132.0,
            fees: 602.64,
            taxes: 113.0,
          }
        ];
      }
      if (endpoint === '/accounts') return [];
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });
  });

  it('renders both cashflow records and investment trades in the cashflow overview table', async () => {
    render(
      <ThemeProvider>
        <CashflowPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Income & Spend Transactions (2)')).toBeInTheDocument();
    });

    // Check Day-to-Day transaction
    expect(screen.getByText('Monthly Salary')).toBeInTheDocument();

    // Check Investment trade transaction
    expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    expect(screen.getByText('Trade')).toBeInTheDocument();
    expect(screen.getByText('Stock & ETF Purchases')).toBeInTheDocument();
  });

  it('filters transactions to the last 30 days only in the overview table', async () => {
    const today = new Date();
    const dateWithin30 = new Date(today);
    dateWithin30.setDate(today.getDate() - 5);
    const dateOver30 = new Date(today);
    dateOver30.setDate(today.getDate() - 45);

    const fmt = (d: Date) => d.toISOString().split('T')[0];

    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith('/cashflow/summary')) return { total_income: 0, total_expenses: 0, total_invested: 0, net_savings: 0, savings_rate_pct: 0, breakdown_by_label: {}, top_expense_categories: [] };
      if (endpoint.startsWith('/cashflow/sankey')) return { nodes: [], links: [] };
      if (endpoint.startsWith('/cashflow')) {
        return [
          {
            cashflow_id: 1,
            transaction_date: fmt(dateWithin30),
            title: 'Recent Expense',
            total_amount: 50.0,
            currency: 'EUR',
            transaction_kind: 'EXPENSE',
            items: [{ category_name: 'Groceries', effective_label: 'ESSENTIAL', amount: 50.0 }],
            payments: [{ account_id: 1, account_name: 'Main Checking Bank', amount: -50.0 }]
          },
          {
            cashflow_id: 2,
            transaction_date: fmt(dateOver30),
            title: 'Old Expense',
            total_amount: 100.0,
            currency: 'EUR',
            transaction_kind: 'EXPENSE',
            items: [{ category_name: 'Groceries', effective_label: 'ESSENTIAL', amount: 100.0 }],
            payments: [{ account_id: 1, account_name: 'Main Checking Bank', amount: -100.0 }]
          }
        ];
      }
      if (endpoint === '/transactions') return [];
      if (endpoint === '/accounts') return [];
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });

    render(
      <ThemeProvider>
        <CashflowPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Recent Expense')).toBeInTheDocument();
    });

    expect(screen.queryByText('Old Expense')).not.toBeInTheDocument();
  });

  it('renders blue dots for stock trade payment lines and shortened label badges (E, D, I, L)', async () => {
    const today = new Date();
    const fmt = (d: Date) => d.toISOString().split('T')[0];

    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith('/cashflow/summary')) return { total_income: 0, total_expenses: 0, total_invested: 0, net_savings: 0, savings_rate_pct: 0, breakdown_by_label: {}, top_expense_categories: [] };
      if (endpoint.startsWith('/cashflow/sankey')) return { nodes: [], links: [] };
      if (endpoint.startsWith('/cashflow')) {
        return [
          {
            cashflow_id: 1,
            transaction_date: fmt(today),
            title: 'Restaurant Dinner',
            total_amount: 80.0,
            currency: 'EUR',
            transaction_kind: 'EXPENSE',
            items: [{ category_name: 'Dining', effective_label: 'DISCRETIONARY', amount: 80.0 }],
            payments: [{ account_id: 1, account_name: 'Credit Card', amount: -80.0 }]
          }
        ];
      }
      if (endpoint === '/transactions') {
        return [
          {
            transaction_id: 10,
            transaction_date: fmt(today),
            asset_id: 1,
            asset_symbol: 'NVDA',
            account_id: 2,
            account_name: 'Brokerage Demat',
            funding_account_id: 1,
            funding_account_name: 'Main Bank',
            transaction_type: 'buy',
            quantity: 5.0,
            price_per_unit: 100.0,
            total_amount: 500.0,
            fees: 5.0,
            taxes: 0.0,
          }
        ];
      }
      if (endpoint === '/accounts') return [];
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });

    const { container } = render(
      <ThemeProvider>
        <CashflowPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('NVDA')).toBeInTheDocument();
    });

    // Check shortened label badges
    expect(screen.getByText('D')).toBeInTheDocument(); // Discretionary -> D
    expect(screen.getByText('I')).toBeInTheDocument(); // Investment -> I

    // Check Blue dots (bg-blue-500) for trade payment lines (Brokerage Demat & Main Bank)
    const tradeRow = screen.getByText('NVDA').closest('tr');
    expect(tradeRow).not.toBeNull();
    const blueDots = tradeRow!.querySelectorAll('.bg-blue-500');
    expect(blueDots.length).toBeGreaterThanOrEqual(2);
  });
});
