import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import CashflowTransactionsPage from '@/app/cashflow/transactions/page';
import * as api from '@/lib/api';
import { MockIntersectionObserver } from '@/test/mockIntersectionObserver';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

const mockAccounts = [
  { account_id: 1, account_name: 'Main Checking Bank', currency: 'EUR', account_type: 'bank' },
  { account_id: 2, account_name: 'Zerodha Demat', currency: 'INR', account_type: 'demat' },
];

function makeCashflowTx(id: number, overrides: Partial<any> = {}) {
  const isIncome = id % 3 === 0;
  const isTransfer = id % 5 === 0 && !isIncome;
  const amount = isIncome ? 3000 : 100 + id * 10;
  return {
    cashflow_id: id,
    transaction_date: `2026-08-${String(Math.min(28, (id % 28) + 1)).padStart(2, '0')}`,
    title: isIncome ? `Income Salary ${id}` : `Expense Merchant ${id}`,
    total_amount: amount,
    currency: 'EUR',
    transaction_kind: isTransfer ? 'TRANSFER' : isIncome ? 'INCOME' : 'EXPENSE',
    notes: `Cashflow note ${id}`,
    items: [
      {
        item_id: id * 10,
        category_name: isIncome ? 'Salary' : 'Supplies',
        category_type: isIncome ? 'INCOME' : 'EXPENSE',
        description: `Item description ${id}`,
        effective_label: isIncome ? 'INCOME' : (id % 2 === 0 ? 'ESSENTIAL' : 'LUXURY'),
        amount: amount,
      },
    ],
    payments: [
      {
        account_id: 1,
        account_name: 'Main Checking Bank',
        account_currency: 'EUR',
        amount: isIncome ? amount : -amount,
      },
    ],
    ...overrides,
  };
}

function makeTradeTx(id: number, overrides: Partial<any> = {}) {
  return {
    transaction_id: 1000 + id,
    transaction_date: `2026-08-${String(Math.min(28, (id % 28) + 1)).padStart(2, '0')}`,
    asset_id: 200 + id,
    asset_symbol: `STOCK${id}`,
    asset_name: `Stock ${id} Corp`,
    account_id: 2,
    account_name: 'Zerodha Demat',
    account_currency: 'INR',
    funding_account_id: 1,
    funding_account_name: 'Main Checking Bank',
    funding_account_currency: 'EUR',
    transaction_type: 'buy',
    quantity: 10.0,
    price_per_unit: 50.0,
    total_amount: 500.0,
    fees: 10.0,
    taxes: 5.0,
    notes: `Trade note ${id}`,
    ...overrides,
  };
}

function makePaginatedCashflowResponse(page: number, pageSize = 20, total = 60) {
  const startIndex = (page - 1) * pageSize;
  const items: any[] = [];
  const count = Math.max(0, Math.min(pageSize, total - startIndex));
  for (let i = 0; i < count; i++) {
    items.push(makeCashflowTx(startIndex + i + 1));
  }
  const payload = {
    items,
    total,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(total / pageSize),
    has_more: page * pageSize < total,
  };
  return Object.assign([...items], payload);
}

function makePaginatedTradesResponse(page: number, pageSize = 20, total = 60) {
  const startIndex = (page - 1) * pageSize;
  const items: any[] = [];
  const count = Math.max(0, Math.min(pageSize, total - startIndex));
  for (let i = 0; i < count; i++) {
    items.push(makeTradeTx(startIndex + i + 1));
  }
  const payload = {
    items,
    total,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(total / pageSize),
    has_more: page * pageSize < total,
  };
  return Object.assign([...items], payload);
}

describe('R3: Cashflow Ledger Infinite Scroll & URL Sync (/cashflow/transactions)', () => {
  let replaceStateSpy: any;

  beforeEach(() => {
    vi.clearAllMocks();
    MockIntersectionObserver.reset();
    replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    window.history.replaceState(null, '', '/cashflow/transactions');
  });

  afterEach(() => {
    replaceStateSpy.mockRestore();
    MockIntersectionObserver.reset();
    window.history.replaceState(null, '', '/');
  });

  // =========================================================================
  // Tier 1: Feature Coverage (Category-Partition)
  // =========================================================================
  describe('Tier 1: Feature Coverage', () => {
    it('C1.1: loads and displays initial cashflow chunk and attaches container intersection observer', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) return makePaginatedCashflowResponse(1, 20, 60);
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Verify intersection observer is attached to scroll container sentinel
      expect(MockIntersectionObserver.activeInstances.length).toBeGreaterThanOrEqual(1);
      const observer = MockIntersectionObserver.activeInstances[0];
      expect(observer.elements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
      expect(screen.getByTestId('transaction-selector-pane')).toHaveClass('md:w-2/5');
    });

    it('offers a Load more button that appends the next cashflow page', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories') || endpoint.startsWith('/settings')) return [];
        const page = Number(endpoint.match(/page=(\d+)/)?.[1] || 1);
        if (endpoint.startsWith('/cashflow')) return makePaginatedCashflowResponse(page, 20, 60);
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(page, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);
      await waitFor(() => expect(screen.getByText('Income Salary 3')).toBeInTheDocument());

      fireEvent.click(screen.getByRole('button', { name: /load more/i }));

      await waitFor(() => expect(screen.getByText('Income Salary 21')).toBeInTheDocument());
    });

    it('does not duplicate the initial requests or flash an empty state in Strict Mode', async () => {
      const pending: Record<string, Array<(value: any) => void>> = {
        cashflow: [],
        transactions: [],
      };
      (api.apiFetch as any).mockImplementation((endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return Promise.resolve(mockAccounts);
        if (endpoint.startsWith('/cashflow')) {
          return new Promise((resolve) => pending.cashflow.push(resolve));
        }
        if (endpoint.startsWith('/transactions')) {
          return new Promise((resolve) => pending.transactions.push(resolve));
        }
        return Promise.resolve(null);
      });

      render(
        <React.StrictMode>
          <CashflowTransactionsPage />
        </React.StrictMode>
      );

      await waitFor(() => {
        expect(pending.cashflow).toHaveLength(1);
        expect(pending.transactions).toHaveLength(1);
      });
      expect(screen.getByText('Loading ledger...')).toBeInTheDocument();

      pending.cashflow[0](makePaginatedCashflowResponse(1, 20, 20));
      pending.transactions[0](makePaginatedTradesResponse(1, 20, 20));

      await waitFor(() => expect(screen.getByText('Income Salary 3')).toBeInTheDocument());
      expect(screen.queryByText('No transactions recorded for this period.')).not.toBeInTheDocument();
    });

    it('C1.2: triggers next chunk on internal container sentinel intersection and appends rows', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger sentinel intersection inside ledger container
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // Chunk 2 rows should be appended
      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      // Existing chunk 1 rows remain
      expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
    });

    it('C1.3: synchronizes URL parameter (?page=2 and ?page=3) via replaceState during ledger scroll', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Scroll to chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
        const calls = replaceStateSpy.mock.calls;
        const matched = calls.some((c: any[]) => {
          if (typeof c[2] !== 'string') return false;
          try {
            const url = new URL(c[2], 'http://localhost');
            const validPath = url.pathname === '/cashflow/transactions' || url.pathname === '/';
            return validPath && url.searchParams.get('page') === '2';
          } catch {
            return false;
          }
        }) || new URLSearchParams(window.location.search).get('page') === '2';
        expect(matched).toBe(true);
      });

      // Scroll to chunk 3
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 42')).toBeInTheDocument();
        const calls = replaceStateSpy.mock.calls;
        const matched = calls.some((c: any[]) => {
          if (typeof c[2] !== 'string') return false;
          try {
            const url = new URL(c[2], 'http://localhost');
            const validPath = url.pathname === '/cashflow/transactions' || url.pathname === '/';
            return validPath && url.searchParams.get('page') === '3';
          } catch {
            return false;
          }
        }) || new URLSearchParams(window.location.search).get('page') === '3';
        expect(matched).toBe(true);
      });
    });

    it('C1.4: offers a Load more action without numbered pagination controls', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) return makePaginatedCashflowResponse(1, 20, 60);
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
      expect(screen.queryByRole('navigation', { name: /pagination/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^(next|previous|prev|next page|previous page|prev page)$/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /page\s*\d+/i })).not.toBeInTheDocument();

      const buttons = screen.queryAllByRole('button');
      const numericButtons = buttons.filter((btn) => {
        const text = btn.textContent?.trim() || '';
        const label = btn.getAttribute('aria-label') || '';
        return /^\d+$/.test(text) || /page\s*\d+/i.test(label) || /^(next|prev(ious)?)$/i.test(label);
      });
      expect(numericButtons.length).toBe(0);
    });

    it('C1.5: displays inline loading indicator in ledger pane during chunk fetch', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2) return chunk2Promise;
          return makePaginatedCashflowResponse(1, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger chunk 2 load
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // In-flight loading indicator is present
      await waitFor(() => {
        const loadingEl = document.querySelector('.animate-spin') ||
          screen.queryByText(/loading/i) ||
          screen.queryByRole('status');
        expect(loadingEl).toBeInTheDocument();
      });

      // Resolve pending chunk 2
      await act(async () => {
        resolveChunk2!(makePaginatedCashflowResponse(2, 20, 60));
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });
    });

    it('C1.6: reaches end of results state when has_more is false and disables further scroll triggers', async () => {
      const fetchCalls: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        fetchCalls.push(endpoint);
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          // Total 40 items (2 pages)
          return makePaginatedCashflowResponse(page, 20, 40);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 40);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Load chunk 2 (terminal page)
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      const callsAfterPage2 = fetchCalls.filter((c) => c.startsWith('/cashflow')).length;

      // Trigger intersection again
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // No new fetch calls for cashflow
      const callsAfterPage3 = fetchCalls.filter((c) => c.startsWith('/cashflow')).length;
      expect(callsAfterPage3).toBe(callsAfterPage2);
    });
  });

  // =========================================================================
  // Tier 2: Boundary & Corner Cases (Boundary Value Analysis)
  // =========================================================================
  describe('Tier 2: Boundary & Corner Cases', () => {
    it('C2.1: single chunk cashflow data does not issue subsequent requests on scroll', async () => {
      const cfRequests: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          cfRequests.push(endpoint);
          return makePaginatedCashflowResponse(1, 20, 12); // total 12, has_more: false
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 0);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger intersection
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      expect(cfRequests.length).toBe(1);
    });

    it('C2.2: empty cashflow state displays empty indicator without infinite scroll trigger', async () => {
      const cfRequests: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          cfRequests.push(endpoint);
          return makePaginatedCashflowResponse(1, 20, 0); // 0 items
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 0);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no transactions/i)).toBeInTheDocument();
      });

      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      expect(cfRequests.length).toBe(1);
      expect(window.location.search).not.toContain('page=2');
    });

    it('C2.3: concurrency throttle prevents multiple parallel page requests on rapid scroll', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      const page2Requests: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2) {
            page2Requests.push(endpoint);
            return chunk2Promise;
          }
          return makePaginatedCashflowResponse(1, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Fire 5 rapid triggers while page 2 is in-flight
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
      });

      expect(page2Requests.length).toBe(1);

      await act(async () => {
        resolveChunk2!(makePaginatedCashflowResponse(2, 20, 60));
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });
    });

    it('C2.4: cashflow chunk fetch error preserves existing rows and allows retry', async () => {
      let failPage2 = true;
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2 && failPage2) {
            throw new Error('Transient 500 error fetching chunk 2');
          }
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger failing chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // Chunk 1 items must remain visible
      expect(screen.getByText('Income Salary 3')).toBeInTheDocument();

      // Permit retry to succeed
      failPage2 = false;

      const retryBtn = screen.queryByRole('button', { name: /retry|reload/i });
      await act(async () => {
        if (retryBtn) {
          fireEvent.click(retryBtn);
        } else {
          MockIntersectionObserver.triggerLatest(true);
        }
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });
    });

    it('C2.4b: initial cashflow load failure retry requests page 1 rather than advancing to page 2', async () => {
      let failPage1 = true;
      const requestedPages: number[] = [];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          requestedPages.push(page);
          if (page === 1 && failPage1) {
            throw new Error('Initial load network timeout');
          }
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Initial load network timeout')).toBeInTheDocument();
      });

      expect(requestedPages).toEqual([1]);

      failPage1 = false;

      const retryBtn = screen.getByRole('button', { name: /retry/i });
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      expect(requestedPages).toEqual([1, 1]);
    });

    it('C2.5: deep link cashflow ?page=2 initializes and renders page 2 transactions', async () => {
      window.history.replaceState(null, '', '/cashflow/transactions?page=2');

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 2;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 2;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      expect(window.location.search).toContain('page=2');
    });
  });

  // =========================================================================
  // Tier 3: Cross-Feature Combinations (Pairwise Interaction & Integrity)
  // =========================================================================
  describe('Tier 3: Cross-Feature Combinations', () => {
    it('C3.1: running balance continuous consistency across chunks without reset or NaN', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger chunk 2 load to combine chunk 1 and chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      // Assert running balance financial integrity:
      // Find all payment badge elements tracking account running balance
      const paymentBadges = screen.getAllByTestId('payment-badge');
      expect(paymentBadges.length).toBeGreaterThanOrEqual(20);
      const badgesWithBal = paymentBadges.filter((b) => b.hasAttribute('data-running-balance'));
      expect(badgesWithBal.length).toBeGreaterThanOrEqual(20);
      badgesWithBal.forEach((badge) => {
        const bal = parseFloat(badge.getAttribute('data-running-balance')!);
        expect(Number.isFinite(bal)).toBe(true);
        expect(Number.isNaN(bal)).toBe(false);
      });
    });

    it('C3.1b: running balance avoids IEEE-754 precision artifacts by rounding to 2 decimal places', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const items = [
            {
              cashflow_id: 991,
              transaction_date: '2026-08-01',
              title: 'Micro Expense 1',
              total_amount: 0.1,
              currency: 'EUR',
              transaction_kind: 'EXPENSE',
              notes: '',
              items: [{ item_id: 9910, category_name: 'Supplies', amount: 0.1 }],
              payments: [{ account_id: 1, account_name: 'Main Checking Bank', account_currency: 'EUR', amount: 0.1 }],
            },
            {
              cashflow_id: 992,
              transaction_date: '2026-08-02',
              title: 'Micro Expense 2',
              total_amount: 0.2,
              currency: 'EUR',
              transaction_kind: 'EXPENSE',
              notes: '',
              items: [{ item_id: 9920, category_name: 'Supplies', amount: 0.2 }],
              payments: [{ account_id: 1, account_name: 'Main Checking Bank', account_currency: 'EUR', amount: 0.2 }],
            },
          ];
          const payload = {
            items,
            total: 2,
            page: 1,
            page_size: 20,
            total_pages: 1,
            has_more: false,
          };
          return Object.assign([...items], payload);
        }
        if (endpoint.startsWith('/transactions')) return { items: [], total: 0, page: 1, page_size: 20, total_pages: 0, has_more: false };
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Micro Expense 1')).toBeInTheDocument();
        expect(screen.getByText('Micro Expense 2')).toBeInTheDocument();
      });

      const badges = screen.getAllByTestId('payment-badge');
      const balances = badges.map((b) => b.getAttribute('data-running-balance'));
      // In unrounded IEEE-754: 0.1 + 0.2 = 0.30000000000000004
      // With 2-decimal rounding: must be 0.3
      expect(balances).toContain('0.3');
      expect(balances).not.toContain('0.30000000000000004');
    });

    it('C3.2: account filter resets scroll offset, pagination, and URL query to page 1', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Scroll to chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      // User filters by "Zerodha Demat (INR)"
      const accountSelect = screen.getByDisplayValue('All accounts');
      await act(async () => {
        fireEvent.change(accountSelect, { target: { value: '2' } });
      });

      // Verifies page resets and URL removes page=2
      await waitFor(() => {
        expect(window.location.search).not.toContain('page=2');
      });
    });

    it('C3.3: label filter (Essential/Luxury) applies filter and scroll loads page 2 of filtered transactions', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Select "Essential" label filter
      const labelSelect = screen.getByLabelText('label-filter');
      await act(async () => {
        fireEvent.change(labelSelect, { target: { value: 'ESSENTIAL' } });
      });

      // Trigger scroll to load page 2 of filtered transactions
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        // Assert chunk 2 essential items render
        expect(screen.getByText('Expense Merchant 22')).toBeInTheDocument();
      });
    });

    it('C3.4: in-flight race condition guard discards late-arriving chunk data when filter changes', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          const isAccountFiltered = endpoint.includes('account_id=2') || endpoint.includes('account=2');
          if (isAccountFiltered) {
            const filteredItems = [
              makeCashflowTx(999, {
                title: 'Demat Only Dividend',
                payments: [{ account_id: 2, account_name: 'Zerodha Demat', account_currency: 'INR', amount: 500 }],
              }),
            ];
            const payload = {
              items: filteredItems,
              total: 1,
              page: 1,
              page_size: 20,
              total_pages: 1,
              has_more: false,
            };
            return Object.assign([...filteredItems], payload);
          }
          if (page === 2) {
            return chunk2Promise;
          }
          return makePaginatedCashflowResponse(1, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) return makePaginatedTradesResponse(1, 20, 60);
        return null;
      });

      render(<CashflowTransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Trigger chunk 2 load (enters in-flight state)
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // While chunk 2 is in-flight, user switches account filter to "Zerodha Demat (INR)"
      const accountSelect = screen.getByDisplayValue('All accounts');
      await act(async () => {
        fireEvent.change(accountSelect, { target: { value: '2' } });
      });

      // Filtered data renders
      await waitFor(() => {
        expect(screen.getByText('Demat Only Dividend')).toBeInTheDocument();
      });

      // Now resolve late-arriving chunk 2 from the previous unfiltered query
      await act(async () => {
        const chunk2 = makePaginatedCashflowResponse(2, 20, 60);
        chunk2[0] = makeCashflowTx(21, {
          title: 'Unfiltered Late Arrival 21',
          payments: [{ account_id: 2, account_name: 'Zerodha Demat', account_currency: 'INR', amount: 300 }],
        });
        resolveChunk2!(chunk2);
      });

      // The late-arriving chunk 2 data must NOT contaminate the new filtered result set
      expect(screen.queryByText('Unfiltered Late Arrival 21')).not.toBeInTheDocument();
      expect(screen.queryByText('Income Salary 21')).not.toBeInTheDocument();
      expect(screen.getByText('Demat Only Dividend')).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Tier 4: Real-World Scenarios (End-to-End User Workflows)
  // =========================================================================
  describe('Tier 4: Real-World Scenarios', () => {
    it('C4.1: realistic master-detail cashflow workflow with infinite scroll and transaction selection', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.startsWith('/accounts')) return mockAccounts;
        if (endpoint.startsWith('/categories')) return [];
        if (endpoint.startsWith('/settings')) return { master_currency: 'EUR' };
        if (endpoint.startsWith('/cashflow')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedCashflowResponse(page, 20, 60);
        }
        if (endpoint.startsWith('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<CashflowTransactionsPage />);

      // Step 1: Initial ledger render
      await waitFor(() => {
        expect(screen.getByText('Income Salary 3')).toBeInTheDocument();
      });

      // Step 2: User scrolls through chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });
      await waitFor(() => {
        expect(screen.getByText('Income Salary 21')).toBeInTheDocument();
      });

      // Step 3: User clicks on an item loaded in chunk 2
      const chunk2Row = screen.getByText('Income Salary 21');
      await act(async () => {
        fireEvent.click(chunk2Row);
      });

      // Step 4: Detail pane updates to display transaction details
      await waitFor(() => {
        expect(screen.getByText(/Transaction Details: Income Salary 21/i)).toBeInTheDocument();
      });

      // Step 5: User clicks Add cashflow transaction button
      const addButtons = screen.getAllByRole('button');
      const addTxBtn = addButtons.find((btn) => btn.textContent?.includes('Add transaction') || btn.textContent?.includes('Add'));
      if (addTxBtn) {
        await act(async () => {
          fireEvent.click(addTxBtn);
        });

        // Dialog/Modal opens
        await waitFor(() => {
          expect(document.querySelector('[role="dialog"]') || screen.getByText(/Cashflow/i)).toBeInTheDocument();
        });
      }
    });
  });
});
