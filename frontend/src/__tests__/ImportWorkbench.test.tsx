import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReviewWorkbenchPage from '@/app/import/[batch_id]/page';
import * as api from '@/lib/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  useParams: () => ({
    batch_id: '42',
  }),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getAuthToken: vi.fn(() => 'mock-token'),
}));

const mockBatch = {
  batch_id: 42,
  filename: "zerodha_trades_2025.csv",
  file_type: "csv",
  status: "ready_for_review",
  target_account_name: "Trading Demat",
  default_currency: "USD",
  custom_instructions: "All Swiggy as Food",
  total_records: 2,
  new_records: 1,
  exact_matches: 0,
  probable_matches: 1,
  created_at: "2025-06-01T12:00:00Z"
};

const mockRecords = [
  {
    staged_id: 101,
    batch_id: 42,
    record_type: "investment",
    transaction_date: "2025-06-01",
    action_type: "buy",
    asset_symbol_raw: "AAPL",
    asset_name_raw: "Apple Inc",
    quantity: 10,
    price_per_unit: 150,
    total_amount: 1500,
    fees: 5,
    taxes: 0,
    currency: "USD",
    notes: "New tech position",
    review_status: "approved",
    match_status: "new",
    matched_entity_id: null,
    matched_entity_details: null
  },
  {
    staged_id: 102,
    batch_id: 42,
    record_type: "investment",
    transaction_date: "2025-06-03",
    action_type: "buy",
    asset_symbol_raw: "MSFT",
    asset_name_raw: "Microsoft Corp",
    quantity: 5,
    price_per_unit: 400,
    total_amount: 2000,
    fees: 0,
    taxes: 0,
    currency: "USD",
    notes: "Probable settlement match",
    review_status: "pending",
    match_status: "probable_match",
    matched_entity_id: 99,
    matched_entity_details: {
      transaction_id: 99,
      transaction_date: "2025-06-01",
      asset_symbol: "MSFT",
      transaction_type: "buy",
      total_amount: 2000,
      account_name: "Trading Demat",
      match_reason: "Date settlement offset (±2 days)"
    }
  }
];

describe('ReviewWorkbenchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.apiFetch as any).mockImplementation(async (url: string) => {
      if (url.includes('/import/batches/42/records')) {
        return mockRecords;
      }
      if (url.includes('/import/batches/42')) {
        return mockBatch;
      }
      return null;
    });
  });

  it('renders batch metadata and KPI summary cards correctly', async () => {
    render(<ReviewWorkbenchPage params={Promise.resolve({ batch_id: '42' })} />);

    await waitFor(() => {
      expect(screen.getByText('zerodha_trades_2025.csv')).toBeInTheDocument();
      expect(screen.getByText('ready for review')).toBeInTheDocument();
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
    });

    // Check match status badges
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('Probable Match')).toBeInTheDocument();
  });

  it('opens side-by-side comparison modal when clicking probable match', async () => {
    render(<ReviewWorkbenchPage params={Promise.resolve({ batch_id: '42' })} />);

    await waitFor(() => {
      expect(screen.getByText('Probable Match')).toBeInTheDocument();
    });

    const compareBtn = screen.getByText('Probable Match');
    fireEvent.click(compareBtn);

    await waitFor(() => {
      expect(screen.getByText('Side-by-Side Duplicate Comparison')).toBeInTheDocument();
      expect(screen.getByText('Date settlement offset (±2 days)')).toBeInTheDocument();
      expect(screen.getByText('Incoming Document Record')).toBeInTheDocument();
      expect(screen.getByText('Existing Ledger Transaction')).toBeInTheDocument();
    });
  });

  it('triggers Final Green Flag commit modal and executes merge API call', async () => {
    (api.apiFetch as any).mockImplementation(async (url: string, opts?: any) => {
      if (url.includes('/commit')) {
        return {
          batch_id: 42,
          status: 'merged',
          committed_count: 1,
          skipped_count: 1,
          message: 'Successfully merged 1 records into live portfolio.'
        };
      }
      if (url.includes('/import/batches/42/records')) return mockRecords;
      if (url.includes('/import/batches/42')) return mockBatch;
      return null;
    });

    render(<ReviewWorkbenchPage params={Promise.resolve({ batch_id: '42' })} />);

    await waitFor(() => {
      expect(screen.getByTestId('final-green-flag-button')).toBeInTheDocument();
    });

    const finalGreenFlagBtn = screen.getByTestId('final-green-flag-button');
    fireEvent.click(finalGreenFlagBtn);

    await waitFor(() => {
      expect(screen.getByText('Final Green Flag Merge')).toBeInTheDocument();
    });

    const confirmBtn = screen.getByText('Confirm & Merge');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByText('Portfolio Successfully Merged!')).toBeInTheDocument();
    });
  });
});
