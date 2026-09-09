import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ValuationsPage from '@/app/investments/valuations/page';
import * as api from '@/lib/api';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

const mockPrices = [
  {
    price_id: 1,
    asset_id: 10,
    asset_symbol: "STARTUP_EQ",
    asset_name: "Startup Equity Ltd",
    currency: "USD",
    price_date: "2026-08-10",
    close_price: 120.0,
    source: "manual",
  },
];

const mockAssets = [
  {
    asset_id: 10,
    symbol: "STARTUP_EQ",
    name: "Startup Equity Ltd",
    asset_type: "stock",
    currency: "USD",
  },
  {
    asset_id: 20,
    symbol: "GOLD_BAR",
    name: "Physical Gold 24k",
    asset_type: "gold",
    currency: "USD",
  },
];

describe('ValuationsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders custom valuation records and form', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/prices/custom') return mockPrices;
      if (endpoint === '/assets') return mockAssets;
      return {};
    });

    render(<ValuationsPage />);

    expect(screen.getByText(/Custom Valuations/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('STARTUP_EQ')).toBeInTheDocument();
      expect(screen.getByText('$120.00')).toBeInTheDocument();
      expect(screen.getByText('2026-08-10')).toBeInTheDocument();
    });
  });

  it('submits a new manual price valuation', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/prices/custom') return mockPrices;
      if (endpoint === '/assets') return mockAssets;
      if (endpoint === '/prices' && options?.method === 'POST') {
        return {
          price_id: 2,
          asset_id: 20,
          price_date: "2026-08-15",
          close_price: 2500.0,
          source: "manual",
        };
      }
      return {};
    });

    render(<ValuationsPage />);

    await waitFor(() => {
      expect(screen.getByText('STARTUP_EQ')).toBeInTheDocument();
    });

    // Select GOLD_BAR
    const assetSelect = screen.getByLabelText(/Select Asset/i);
    fireEvent.change(assetSelect, { target: { value: '20' } });

    // Enter Price
    const priceInput = screen.getByLabelText(/Unit Valuation Price/i);
    fireEvent.change(priceInput, { target: { value: '2500' } });

    // Submit form
    const saveBtn = screen.getByRole('button', { name: /Save Valuation/i });
    fireEvent.submit(saveBtn.closest('form')!);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith(
        '/prices',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"close_price":2500'),
        })
      );
    });
  });

  it('deletes an existing custom valuation', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/prices/custom') return mockPrices;
      if (endpoint === '/assets') return mockAssets;
      if (endpoint === '/prices/1' && options?.method === 'DELETE') {
        return {};
      }
      return {};
    });

    render(<ValuationsPage />);

    await waitFor(() => {
      expect(screen.getByText('STARTUP_EQ')).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole('button', { name: /Delete Valuation/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/prices/1', { method: 'DELETE' });
    });
  });
});
