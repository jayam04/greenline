import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import InvestmentsDashboardPage from '@/app/investments/page';
import CashflowOverviewPage from '@/app/cashflow/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

describe('No-Scroll Executive Dashboards', () => {
  const mockPortfolioSummary = {
    net_worth: 135000,
    total_net_worth: 135000,
    total_cost: 114270.36,
    total_invested: 114270.36,
    total_current_value: 135000,
    unrealized_pnl: 20729.64,
    unrealized_pnl_pct: 18.14,
    realized_pnl: 15370.86,
    cash_balance: 5000,
    total_fees: 170,
    total_taxes: 0,
    portfolio_xirr: 0.2745,
    top_holdings: [
      {
        asset_id: 1,
        symbol: 'AAPL',
        name: 'Apple Inc.',
        asset_type: 'stock',
        currency: 'USD',
        quantity_held: 10,
        total_cost: 1500,
        current_value: 1800,
        unrealized_pnl: 300,
        unrealized_pnl_pct: 20,
        realized_pnl: 0,
        weight_pct: 25,
      },
      {
        asset_id: 2,
        symbol: 'VUAA.L',
        name: 'Vanguard S&P 500',
        asset_type: 'etf',
        currency: 'USD',
        quantity_held: 20,
        total_cost: 1800,
        current_value: 2200,
        unrealized_pnl: 400,
        unrealized_pnl_pct: 22.2,
        realized_pnl: 0,
        weight_pct: 75,
      },
    ],
    asset_allocation: { Stock: 1800, ETF: 2200 },
    sector_allocation: { Technology: 1800, Blend: 2200 },
  };

  const mockSnapshots = [
    { snapshot_date: '2026-01-01', net_worth: 100000, total_invested: 90000 },
    { snapshot_date: '2026-11-14', net_worth: 135000, total_invested: 114270 },
  ];

  const mockCashflowSummary = {
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
      { category: 'Groceries', amount: 552.96, pct: 21 },
    ],
  };

  const mockSankeyData = {
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
      if (endpoint === '/portfolio/summary') return mockPortfolioSummary;
      if (endpoint === '/snapshots') return mockSnapshots;
      if (endpoint === '/accounts') return [{ account_id: 1, account_name: 'Zerodha', account_type: 'demat', currency: 'EUR' }];
      if (endpoint.startsWith('/cashflow/summary')) return mockCashflowSummary;
      if (endpoint.startsWith('/cashflow/sankey')) return mockSankeyData;
      if (endpoint === '/settings') return { master_currency: 'EUR' };
      return null;
    });
  });

  it('renders Portfolio as a compact executive cockpit without giant scrolling tables', async () => {
    render(<InvestmentsDashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Portfolio' })).toBeInTheDocument();
      expect(screen.getByText(/How your investments are performing across all brokers/i)).toBeInTheDocument();
    });

    // 4 Metric cards
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
    expect(screen.getByText('Realized P&L')).toBeInTheDocument();
    expect(screen.getByText('Annualised return')).toBeInTheDocument();

    // Side-by-side cockpit: Value chart + Allocation
    expect(screen.getByText('Portfolio value')).toBeInTheDocument();
    expect(screen.getByText('Allocation')).toBeInTheDocument();

    // Verify link to full holdings page
    expect(screen.getByRole('link', { name: /View all positions/i })).toHaveAttribute('href', '/investments/holdings');

    // Verify it does NOT contain the giant inline positions table headers
    expect(screen.queryByText('Positions & Holdings')).not.toBeInTheDocument();
    expect(screen.queryByText('Closed Positions / Capital Gains History')).not.toBeInTheDocument();
  });

  it('renders Income & Spend as a compact executive cockpit with Sankey and no scrolling transactions table', async () => {
    render(<CashflowOverviewPage />);

    await waitFor(() => {
      expect(screen.getByText('Income & spend')).toBeInTheDocument();
      expect(screen.getByText(/Where money came from and where it went/i)).toBeInTheDocument();
    });

    // 4 Metric Cards
    expect(screen.getByText('Total inflow')).toBeInTheDocument();
    expect(screen.getByText('Total spends')).toBeInTheDocument();
    expect(screen.getByText('Net retained')).toBeInTheDocument();
    expect(screen.getByText('Classification')).toBeInTheDocument();

    // Sankey Diagram
    expect(screen.getByText('Cashflow diagram')).toBeInTheDocument();

    // Link to detailed transactions page
    expect(screen.getByRole('link', { name: /View all transactions/i })).toHaveAttribute('href', '/cashflow/transactions');

    // Verify it does NOT render the giant unified transactions ledger table
    expect(screen.queryByText(/Income & Spend Transactions/i)).not.toBeInTheDocument();
  });
});
