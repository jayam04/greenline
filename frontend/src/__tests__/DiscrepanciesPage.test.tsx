import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DiscrepanciesPage from '@/app/investments/discrepancies/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

const mockSummary = {
  total_count: 2,
  total_unlinked_amount: 175.50,
  auto_linkable_count: 1,
  unlinked_items: [
    {
      transaction_id: 101,
      account_id: 1,
      account_name: "Zerodha Demat",
      asset_id: 10,
      asset_symbol: "AAPL",
      asset_name: "Apple Inc.",
      currency: "USD",
      transaction_date: "2024-05-15",
      quantity: 50.0,
      price_per_unit: 1.0,
      total_amount: 50.0,
      taxes: 5.0,
      net_amount: 45.0,
      source: "yfinance_auto",
      suggested_funding_account_id: 2,
      suggested_funding_account_name: "Chase Checking",
      notes: "Auto-generated dividend",
    },
    {
      transaction_id: 102,
      account_id: 3,
      account_name: "Schwab Demat",
      asset_id: 20,
      asset_symbol: "MSFT",
      asset_name: "Microsoft Corp.",
      currency: "USD",
      transaction_date: "2024-06-01",
      quantity: 100.0,
      price_per_unit: 1.5,
      total_amount: 150.0,
      taxes: 19.5,
      net_amount: 130.50,
      source: "yfinance_auto",
      suggested_funding_account_id: null,
      suggested_funding_account_name: null,
      notes: "Auto-generated dividend",
    },
  ],
};

const mockAccounts = [
  { account_id: 1, account_name: "Zerodha Demat", account_type: "demat", currency: "USD" },
  { account_id: 2, account_name: "Chase Checking", account_type: "bank", currency: "USD" },
  { account_id: 4, account_name: "Wells Fargo", account_type: "bank", currency: "USD" },
];

describe('DiscrepanciesPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders unlinked dividend items and KPI summary cards correctly', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/discrepancies') return mockSummary;
      if (endpoint === '/accounts') return mockAccounts;
      return {};
    });

    render(<DiscrepanciesPage />);

    expect(screen.getByText(/Investments Discrepancies/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
    });

    // Check KPI counts
    expect(screen.getByText('Unlinked Distributions')).toBeInTheDocument();
    expect(screen.getByText('Total Unlinked Value')).toBeInTheDocument();
    expect(screen.getByText('Pre-Matched Ready')).toBeInTheDocument();

    // Suggested default badge
    expect(screen.getByText(/Default: Chase Checking/i)).toBeInTheDocument();

    // Auto-link button
    expect(screen.getByText(/Auto-Link Defaults \(1\)/i)).toBeInTheDocument();
  });

  it('triggers auto-link defaults when clicked', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/discrepancies') return mockSummary;
      if (endpoint === '/accounts') return mockAccounts;
      if (endpoint === '/discrepancies/auto-link-defaults') return { status: 'success', linked_count: 1 };
      return {};
    });

    render(<DiscrepanciesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Auto-Link Defaults \(1\)/i)).toBeInTheDocument();
    });

    const autoLinkBtn = screen.getByText(/Auto-Link Defaults \(1\)/i);
    fireEvent.click(autoLinkBtn);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/discrepancies/auto-link-defaults', { method: 'POST' });
    });
  });

  it('renders empty state when there are 0 discrepancies', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/discrepancies') {
        return {
          total_count: 0,
          total_unlinked_amount: 0.0,
          auto_linkable_count: 0,
          unlinked_items: [],
        };
      }
      if (endpoint === '/accounts') return mockAccounts;
      return {};
    });

    render(<DiscrepanciesPage />);

    await waitFor(() => {
      expect(screen.getByText('No Discrepancies Found')).toBeInTheDocument();
    });
    expect(screen.getByText(/All dividend distributions and cash movements are currently matched/i)).toBeInTheDocument();
  });
});
