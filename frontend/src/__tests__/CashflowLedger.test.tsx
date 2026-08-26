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
});
