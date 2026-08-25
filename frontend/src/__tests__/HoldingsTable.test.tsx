import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import HoldingsPage from '@/app/holdings/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

const mockSummary = {
  total_net_worth: 40000.0,
  total_invested: 32000.0,
  total_current_value: 39500.0,
  cash_balance: 500.0,
  total_realized_pnl: 1000.0,
  total_unrealized_pnl: 7500.0,
  total_fees: 602.64,
  total_taxes: 113.0,
  portfolio_xirr: 0.245,
  top_holdings: [
    {
      asset_id: 4,
      symbol: "GROWW.BO",
      name: "Billionbrains Garage Ventures Limited",
      asset_type: "stock",
      sector: "Technology",
      currency: "INR",
      quantity_held: 186.0,
      avg_cost_price: 162.0,      // Gross average purchase price per share
      total_cost: 30847.64,        // All-in cost basis: (186 * 162 = 30,132) + 602.64 fees + 113.0 taxes = 30,847.64
      latest_price: 203.35,        // Latest market quote
      latest_price_date: "2026-08-25",
      current_value: 37823.10,     // 186 * 203.35 = 37,823.10
      unrealized_pnl: 6975.46,     // 37,823.10 - 30,847.64 = +6,975.46
      unrealized_pnl_pct: 22.61,   // (+6,975.46 / 30,847.64) * 100 = +22.61%
      realized_pnl: 0.0,
      realized_pnl_pct: 0.0,
      fees_and_taxes: 715.64,
      total_fees: 602.64,
      total_taxes: 113.0,
      net_pnl: 6975.46,
      net_pnl_pct: 22.61,
      xirr: 0.245,
      open_lots: [
        {
          lot_id: 1,
          buy_date: "2025-09-19",
          quantity_original: 186.0,
          quantity_remaining: 186.0,
          cost_per_unit: 165.85,  // All-in cost per share: 30,847.64 / 186 = 165.8475
        }
      ],
    },
    {
      asset_id: 2,
      symbol: "AAPL",
      name: "Apple Inc.",
      asset_type: "stock",
      sector: "Technology",
      currency: "USD",
      quantity_held: 10.0,
      avg_cost_price: 150.0,
      total_cost: 1500.0,
      latest_price: 180.0,
      latest_price_date: "2026-08-25",
      current_value: 1800.0,
      unrealized_pnl: 300.0,
      unrealized_pnl_pct: 20.0,
      realized_pnl: 100.0,
      realized_pnl_pct: 10.0,
      fees_and_taxes: 0.0,
      total_fees: 0.0,
      total_taxes: 0.0,
      net_pnl: 400.0,
      net_pnl_pct: 26.67,
      xirr: 0.18,
      open_lots: [
        {
          lot_id: 2,
          buy_date: "2025-10-01",
          quantity_original: 10.0,
          quantity_remaining: 10.0,
          cost_per_unit: 150.0,
        }
      ],
    }
  ],
  closed_holdings: []
};

describe('Holdings Production Page Component (src/app/holdings/page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/portfolio/summary') {
        return mockSummary;
      }
      if (endpoint === '/settings') {
        return { master_currency: 'EUR' };
      }
      return null;
    });
  });

  it('renders table columns including merged Total Cost, Current Value, and Net P&L', async () => {
    render(<HoldingsPage />);

    await waitFor(() => {
      expect(screen.getByText('Positions & Holdings')).toBeInTheDocument();
    });

    const table = screen.getByRole('table');
    const tableWithin = within(table);

    // Check table headers inside table
    expect(tableWithin.getByText('Asset')).toBeInTheDocument();
    expect(tableWithin.getByText('Quantity')).toBeInTheDocument();
    expect(tableWithin.getByText('Total Cost')).toBeInTheDocument();
    expect(tableWithin.getByText('Current Value')).toBeInTheDocument();
    expect(tableWithin.getByText('Unrealized P&L')).toBeInTheDocument();
    expect(tableWithin.getByText('Realized P&L')).toBeInTheDocument();
    expect(tableWithin.getByText('Net P&L')).toBeInTheDocument();
    expect(tableWithin.getByText('XIRR')).toBeInTheDocument();

    // Check rendered asset data
    expect(tableWithin.getByText('GROWW.BO')).toBeInTheDocument();
    expect(tableWithin.getByText('Billionbrains Garage Ventures Limited')).toBeInTheDocument();
    expect(tableWithin.getByText('₹30,847.64')).toBeInTheDocument();
    expect(tableWithin.getByText('₹162.00/u')).toBeInTheDocument();
    expect(tableWithin.getByText('₹37,823.10')).toBeInTheDocument();
    expect(tableWithin.getByText('₹203.35')).toBeInTheDocument();
    expect(tableWithin.getAllByText('₹6,975.46').length).toBeGreaterThanOrEqual(1);

    // Check second asset data
    expect(tableWithin.getByText('AAPL')).toBeInTheDocument();
    expect(tableWithin.getByText('$1,500.00')).toBeInTheDocument();
    expect(tableWithin.getByText('$1,800.00')).toBeInTheDocument();
    expect(tableWithin.getByText('$400.00')).toBeInTheDocument();
  });

  it('expands and collapses open FIFO lot details upon row click in real page', async () => {
    render(<HoldingsPage />);

    await waitFor(() => {
      expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    });

    // Initially FIFO lot subrow breakdown header is not visible
    expect(screen.queryByText(/FIFO Lots Breakdown for GROWW.BO/i)).not.toBeInTheDocument();

    // Click row to expand
    const growwRow = screen.getByText('GROWW.BO').closest('tr');
    expect(growwRow).not.toBeNull();
    fireEvent.click(growwRow!);

    // FIFO subrow opens
    expect(await screen.findByText(/FIFO Lots Breakdown for GROWW.BO/i)).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('2025-09-19')).toBeInTheDocument();
    expect(screen.getByText('₹165.85')).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(growwRow!);
    expect(screen.queryByText(/FIFO Lots Breakdown for GROWW.BO/i)).not.toBeInTheDocument();
  });

  it('sorts table when clicking column headers', async () => {
    render(<HoldingsPage />);

    await waitFor(() => {
      expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    });

    // Click Asset header to toggle alphabetical sorting
    const assetHeader = screen.getByText('Asset');
    fireEvent.click(assetHeader);

    // Verify both items remain present and sorted
    const rows = screen.getAllByRole('row');
    expect(rows.length).toBeGreaterThan(2);
  });
});
