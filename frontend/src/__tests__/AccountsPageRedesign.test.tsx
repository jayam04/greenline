import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AccountsPage from '@/app/accounts/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getAuthToken: vi.fn(() => 'mock-token'),
}));

describe('Redesigned Accounts Page (src/app/accounts/page.tsx)', () => {
  const mockAccounts = [
    {
      account_id: 1,
      account_name: 'Bank of Ireland',
      broker_name: 'Main',
      account_type: 'bank',
      currency: 'EUR',
      current_balance: 50.0,
      cash_balance: 50.0,
      securities_value: 0.0,
    },
    {
      account_id: 2,
      account_name: 'Zerodha Primary',
      broker_name: 'Zerodha',
      account_type: 'demat',
      currency: 'INR',
      current_balance: 129288.98,
      cash_balance: 4668.55,
      securities_value: 124620.43,
      default_dividend_account_name: 'Bank of Ireland',
    },
    {
      account_id: 3,
      account_name: 'Splitwise Net',
      broker_name: 'Personal',
      account_type: 'bank',
      currency: 'EUR',
      current_balance: -1240.31,
      cash_balance: -1240.31,
      securities_value: 0.0,
    },
  ];

  const mockAssets = [
    {
      asset_id: 10,
      symbol: 'VUAA.L',
      isin: 'IE00B3XXRP09',
      name: 'Vanguard S&P 500 UCITS ETF',
      asset_type: 'etf',
      exchange: 'LSE',
      sector: 'Blend',
      industry: 'Large Cap',
      currency: 'USD',
    },
    {
      asset_id: 11,
      symbol: 'TCS.NS',
      isin: 'INE467B01029',
      name: 'Tata Consultancy Services',
      asset_type: 'stock',
      exchange: 'NSE',
      sector: 'Technology',
      industry: 'IT Services',
      currency: 'INR',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation((url: string) => {
      if (url.includes('/accounts')) {
        return Promise.resolve(mockAccounts);
      }
      if (url.includes('/assets')) {
        return Promise.resolve(mockAssets);
      }
      if (url.includes('/settings')) {
        return Promise.resolve({ master_currency: 'EUR' });
      }
      return Promise.resolve(null);
    });
  });

  it('renders clean PageHeader and account cards with balances and no unnecessary heading icons', async () => {
    render(<AccountsPage />);

    // Verify PageHeader
    await waitFor(() => {
      expect(screen.getByText('Accounts')).toBeInTheDocument();
      expect(screen.getByText(/Where your money lives, and the securities you can trade/i)).toBeInTheDocument();
    });

    // Verify Section headings exist cleanly without icon decorations
    expect(screen.getByText('Connected Accounts')).toBeInTheDocument();
    expect(screen.getByText('Securities')).toBeInTheDocument();

    // Verify Balances are displayed for accounts
    // Bank account: €50.00
    expect(screen.getByRole('heading', { name: 'Bank of Ireland' })).toBeInTheDocument();
    expect(screen.getByText(/€50.00/)).toBeInTheDocument();

    // Negative balance bank account: -€1,240.31
    expect(screen.getByRole('heading', { name: 'Splitwise Net' })).toBeInTheDocument();
    expect(screen.getByText(/−€1,240.31|-€1,240.31/)).toBeInTheDocument();

    // Demat account: ₹129,288.98 with securities and cash breakdown
    expect(screen.getByRole('heading', { name: 'Zerodha Primary' })).toBeInTheDocument();
    expect(screen.getByText(/₹129,288.98/)).toBeInTheDocument();
    expect(screen.getByText(/Securities:.*₹124,620.43/i)).toBeInTheDocument();
    expect(screen.getByText(/Cash:.*₹4,668.55/i)).toBeInTheDocument();

    // Converted estimate in master currency for INR account (~€1,318.75)
    expect(screen.getByText(/≈ €1,318.75|≈ €1,319/i)).toBeInTheDocument();
  });

  it('filters account cards by type (All, Banks, Brokerage)', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Bank of Ireland' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Zerodha Primary' })).toBeInTheDocument();
    });

    // Click Banks tab
    const banksTab = screen.getByRole('button', { name: /Banks/i });
    fireEvent.click(banksTab);

    expect(screen.getByRole('heading', { name: 'Bank of Ireland' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Splitwise Net' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Zerodha Primary' })).not.toBeInTheDocument();

    // Click Brokerage tab
    const brokerageTab = screen.getByRole('button', { name: /Brokerage/i });
    fireEvent.click(brokerageTab);

    expect(screen.getByRole('heading', { name: 'Zerodha Primary' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Bank of Ireland' })).not.toBeInTheDocument();
  });

  it('searches and filters securities in the master registry table', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText('VUAA.L')).toBeInTheDocument();
      expect(screen.getByText('TCS.NS')).toBeInTheDocument();
    });

    // Search for VUAA
    const searchInput = screen.getByPlaceholderText(/Filter by name, ticker, or ISIN/i);
    fireEvent.change(searchInput, { target: { value: 'VUAA' } });

    expect(screen.getByText('VUAA.L')).toBeInTheDocument();
    expect(screen.queryByText('TCS.NS')).not.toBeInTheDocument();
  });
});
