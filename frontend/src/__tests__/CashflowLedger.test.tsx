import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { isCategoryAllowedForKind } from '@/components/CashflowModal';
import { ThemeProvider } from '@/components/ThemeProvider';
import CashflowOverviewPage from '@/app/cashflow/page';
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

describe('Cashflow Overview Page (src/app/cashflow/page.tsx) Executive Cockpit', () => {
  const mockSummary = {
    total_income: 7670.08,
    total_expenses: 2626.66,
    total_invested: 0,
    net_savings: 5043.42,
    savings_rate_pct: 65.75,
    breakdown_by_label: {
      ESSENTIAL: 1752.96,
      DISCRETIONARY: 873.7,
      LUXURY: 0,
    },
    top_expense_categories: [
      { category: 'Rent', amount: 1200, pct: 45.6 },
    ],
  };

  const mockSankey = {
    nodes: [
      { id: 'Salary', name: 'Salary', level: 0 },
      { id: 'Inflow', name: 'Inflow', level: 1 },
      { id: 'Essential', name: 'Essential', level: 2 },
    ],
    links: [
      { source: 'Salary', target: 'Inflow', value: 7670.08 },
      { source: 'Inflow', target: 'Essential', value: 1752.96 },
    ],
    total_income: 7670.08,
    total_expenses: 2626.66,
    total_investments: 0,
    depth: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith('/cashflow/summary')) return mockSummary;
      if (endpoint.startsWith('/cashflow/sankey')) return mockSankey;
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });
  });

  it('renders executive cockpit cards and diagram without requiring scrolling', async () => {
    render(
      <ThemeProvider>
        <CashflowOverviewPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Income & spend')).toBeInTheDocument();
      expect(screen.getByText(/Where money came from and where it went/i)).toBeInTheDocument();
    });

    // 4 Key financial metrics
    expect(screen.getByText('Total inflow')).toBeInTheDocument();
    expect(screen.getByText('Total spends')).toBeInTheDocument();
    expect(screen.getByText('Net retained')).toBeInTheDocument();
    expect(screen.getByText('Classification')).toBeInTheDocument();

    // Spend classification labels
    expect(screen.getAllByText('Essential').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Discretionary').length).toBeGreaterThan(0);
    expect(screen.getByText('Luxury')).toBeInTheDocument();

    // Sankey Flow Diagram
    expect(screen.getByText('Cashflow diagram')).toBeInTheDocument();
  });

  it('toggles timeframes via segmented control', async () => {
    render(
      <ThemeProvider>
        <CashflowOverviewPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Month')).toBeInTheDocument();
    });

    const ytdBtn = screen.getByRole('tab', { name: 'YTD' });
    fireEvent.click(ytdBtn);

    expect(api.apiFetch).toHaveBeenCalledWith(expect.stringContaining('/cashflow/summary'));
  });

  it('links out to detailed transactions ledger', async () => {
    render(
      <ThemeProvider>
        <CashflowOverviewPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /View all transactions/i })).toHaveAttribute(
        'href',
        '/cashflow/transactions'
      );
    });
  });
});
