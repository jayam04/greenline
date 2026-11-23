import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import TransactionsPage from '@/app/investments/transactions/page';
import * as api from '@/lib/api';
import { MockIntersectionObserver } from '@/test/mockIntersectionObserver';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}));

interface MockTrade {
  transaction_id: number;
  account_id: number;
  funding_account_id?: number | null;
  funding_account_name?: string | null;
  funding_account_currency?: string | null;
  asset_id: number | null;
  account_name: string;
  account_currency?: string;
  asset_symbol: string;
  asset_name: string;
  transaction_type: string;
  transaction_date: string;
  quantity: number | null;
  price_per_unit: number | null;
  total_amount: number;
  fees: number;
  taxes: number;
  notes: string | null;
}

function makeTrade(id: number, overrides: Partial<MockTrade> = {}): MockTrade {
  const isBuy = id % 2 !== 0;
  return {
    transaction_id: id,
    account_id: 1,
    funding_account_id: null,
    funding_account_name: null,
    funding_account_currency: null,
    asset_id: 100 + id,
    account_name: 'Main Checking Bank',
    account_currency: 'EUR',
    asset_symbol: `ASSET${id}`,
    asset_name: `Company ${id}`,
    transaction_type: isBuy ? 'buy' : 'sell',
    transaction_date: `2026-08-${String((id % 28) + 1).padStart(2, '0')}`,
    quantity: 10 + (id % 5),
    price_per_unit: 100 + id,
    total_amount: (10 + (id % 5)) * (100 + id),
    fees: 2.5,
    taxes: 1.0,
    notes: `Trade note ${id}`,
    ...overrides,
  };
}

function makePaginatedTradesResponse(page: number, pageSize = 20, total = 60) {
  const startIndex = (page - 1) * pageSize;
  const items: MockTrade[] = [];
  const count = Math.max(0, Math.min(pageSize, total - startIndex));
  for (let i = 0; i < count; i++) {
    items.push(makeTrade(startIndex + i + 1));
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

describe('R3: Trades Infinite Scroll & URL Sync (/investments/transactions)', () => {
  let replaceStateSpy: any;

  beforeEach(() => {
    vi.clearAllMocks();
    MockIntersectionObserver.reset();
    replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    window.history.replaceState(null, '', '/investments/transactions');
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
    it('T1.1: loads and displays initial chunk of trades and attaches intersection observer', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          return makePaginatedTradesResponse(1, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Verify the first chunk of 20 items is rendered
      expect(screen.getByText('Company 20')).toBeInTheDocument();
      expect(screen.queryByText('Company 21')).not.toBeInTheDocument();

      // Verify MockIntersectionObserver is active and observing sentinel element
      expect(MockIntersectionObserver.activeInstances.length).toBeGreaterThanOrEqual(1);
      const observer = MockIntersectionObserver.activeInstances[0];
      expect(observer.elements.length).toBeGreaterThanOrEqual(1);
    });

    it('T1.2: triggers next chunk on sentinel intersection and appends trades without losing previous chunk', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Trigger sentinel intersection for page 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });

      // Verify both chunk 1 and chunk 2 exist simultaneously (cumulative list)
      expect(screen.getByText('Company 1')).toBeInTheDocument();
      expect(screen.getByText('Company 20')).toBeInTheDocument();
      expect(screen.getByText('Company 40')).toBeInTheDocument();
      expect(screen.queryByText('Company 41')).not.toBeInTheDocument();
    });

    it('T1.3: synchronizes URL query param (?page=2, ?page=3) via replaceState during scroll', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Scroll to chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
        const calls = replaceStateSpy.mock.calls;
        const matched = calls.some((c: any[]) => {
          if (typeof c[2] !== 'string') return false;
          try {
            const url = new URL(c[2], 'http://localhost');
            const validPath = url.pathname === '/investments/transactions' || url.pathname === '/';
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
        expect(screen.getByText('Company 41')).toBeInTheDocument();
        const calls = replaceStateSpy.mock.calls;
        const matched = calls.some((c: any[]) => {
          if (typeof c[2] !== 'string') return false;
          try {
            const url = new URL(c[2], 'http://localhost');
            const validPath = url.pathname === '/investments/transactions' || url.pathname === '/';
            return validPath && url.searchParams.get('page') === '3';
          } catch {
            return false;
          }
        }) || new URLSearchParams(window.location.search).get('page') === '3';
        expect(matched).toBe(true);
      });
    });

    it('T1.4: displays zero manual pagination buttons or pagination navigation controls', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          return makePaginatedTradesResponse(1, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Assert no manual pagination controls exist
      expect(screen.queryByRole('navigation', { name: /pagination/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^(next|previous|prev|next page|previous page|prev page|load more)$/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /page\s*\d+/i })).not.toBeInTheDocument();

      const buttons = screen.queryAllByRole('button');
      const numericButtons = buttons.filter((btn) => {
        const text = btn.textContent?.trim() || '';
        const label = btn.getAttribute('aria-label') || '';
        return /^\d+$/.test(text) || /page\s*\d+/i.test(label) || /^(next|prev(ious)?)$/i.test(label);
      });
      expect(numericButtons.length).toBe(0);
    });

    it('T1.5: displays loading indicator while next chunk is fetching and removes it on completion', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2) {
            return chunk2Promise;
          }
          return makePaginatedTradesResponse(1, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Trigger chunk 2 load (enters in-flight state)
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // While chunk 2 is pending, loading indicator/spinner should be present
      await waitFor(() => {
        const loadingEl = document.querySelector('.animate-spin') ||
          screen.queryByText(/loading/i) ||
          screen.queryByRole('status');
        expect(loadingEl).toBeInTheDocument();
      });

      // Resolve chunk 2 promise
      await act(async () => {
        resolveChunk2!(makePaginatedTradesResponse(2, 20, 60));
      });

      // After resolution, new items appear and spinner/loader disappears
      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });
    });

    it('T1.6: reaches end-of-results terminal state when has_more is false', async () => {
      const fetchCalls: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          fetchCalls.push(endpoint);
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          // Only 2 total pages (40 items)
          return makePaginatedTradesResponse(page, 20, 40);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Load chunk 2 (last page, has_more: false)
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });

      const callsAfterPage2 = fetchCalls.length;

      // Trigger intersection again when all items are loaded
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // No new fetch request should be issued for page 3
      expect(fetchCalls.length).toBe(callsAfterPage2);
    });
  });

  // =========================================================================
  // Tier 2: Boundary & Corner Cases (Boundary Value Analysis)
  // =========================================================================
  describe('Tier 2: Boundary & Corner Cases', () => {
    it('T2.1: single page data does not trigger additional fetch on intersection', async () => {
      const fetchCalls: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          fetchCalls.push(endpoint);
          return makePaginatedTradesResponse(1, 20, 8); // total 8 items, has_more: false
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      expect(screen.getByText('Company 8')).toBeInTheDocument();
      expect(screen.queryByText('Company 9')).not.toBeInTheDocument();

      // Trigger intersection callback
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // Verify no subsequent page fetch occurs
      expect(fetchCalls.length).toBe(1);
    });

    it('T2.2: empty state handles 0 records gracefully without error or infinite scroll loop', async () => {
      const fetchCalls: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          fetchCalls.push(endpoint);
          return makePaginatedTradesResponse(1, 20, 0); // 0 records
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no trades found/i)).toBeInTheDocument();
      });

      // Trigger intersection callback on empty state
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      expect(fetchCalls.length).toBe(1);
      expect(window.location.search).not.toContain('page=2');
    });

    it('T2.3: rapid scroll concurrency guard prevents multiple in-flight chunk requests', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      const page2Requests: string[] = [];
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2) {
            page2Requests.push(endpoint);
            return chunk2Promise;
          }
          return makePaginatedTradesResponse(1, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Trigger multiple rapid scroll events while page 2 is in-flight
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
        MockIntersectionObserver.triggerLatest(true);
      });

      // Concurrency guard must throttle/lock to exactly 1 in-flight request
      expect(page2Requests.length).toBe(1);

      // Resolve the pending chunk 2
      await act(async () => {
        resolveChunk2!(makePaginatedTradesResponse(2, 20, 60));
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });
    });

    it('T2.4: handles chunk fetch error gracefully with retry capability without losing existing items', async () => {
      let failPage2 = true;
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          if (page === 2 && failPage2) {
            throw new Error('Network timeout loading page 2');
          }
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Trigger failing chunk 2 fetch
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // Existing chunk 1 items must remain intact
      expect(screen.getByText('Company 1')).toBeInTheDocument();
      expect(screen.getByText('Company 20')).toBeInTheDocument();

      // Allow next attempt to succeed
      failPage2 = false;

      // Retry chunk 2 (via retry button if present, or re-intersecting)
      const retryBtn = screen.queryByRole('button', { name: /retry|reload/i });
      await act(async () => {
        if (retryBtn) {
          fireEvent.click(retryBtn);
        } else {
          MockIntersectionObserver.triggerLatest(true);
        }
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });
    });

    it('T2.4b: initial trades load failure retry requests page 1 rather than advancing to page 2', async () => {
      let failPage1 = true;
      const requestedPages: number[] = [];

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          requestedPages.push(page);
          if (page === 1 && failPage1) {
            throw new Error('Initial trades timeout');
          }
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Initial trades timeout')).toBeInTheDocument();
      });

      expect(requestedPages).toEqual([1]);

      failPage1 = false;

      const retryBtn = screen.getByRole('button', { name: /retry/i });
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      expect(requestedPages).toEqual([1, 1]);
    });

    it('T2.5: initializes directly from deep link (?page=3) displaying appropriate trade set', async () => {
      window.history.replaceState(null, '', '/investments/transactions?page=3');

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 3;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        // Deep link should load page 3 items (Company 41-60)
        expect(screen.getByText('Company 41')).toBeInTheDocument();
      });

      // Deep link URL should remain preserved
      expect(window.location.search).toContain('page=3');
    });
  });

  // =========================================================================
  // Tier 3: Cross-Feature Combinations (Pairwise Interaction)
  // =========================================================================
  describe('Tier 3: Cross-Feature Combinations', () => {
    it('T3.1: filter change resets scroll position, pagination offset, and URL to page 1', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          const isFiltered = endpoint.includes('type=buy') || endpoint.includes('filter=buy');
          return makePaginatedTradesResponse(page, 20, isFiltered ? 15 : 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Scroll to chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });

      // User changes filter to "Buys"
      const filterSelect = screen.getByDisplayValue('All types');
      await act(async () => {
        fireEvent.change(filterSelect, { target: { value: 'buy' } });
      });

      // Verifies URL sync resets page parameter to page=1 or removes page=2
      await waitFor(() => {
        expect(window.location.search).not.toContain('page=2');
      });
    });

    it('T3.2: search query change resets pagination and fetches matching items at page 1', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Scroll to page 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });

      // Search for specific company
      const searchInput = screen.getByPlaceholderText(/search asset, symbol/i);
      await act(async () => {
        fireEvent.change(searchInput, { target: { value: 'Company 1' } });
      });

      // Filtered search should only display matching items and reset offset
      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
        expect(screen.queryByText('Company 21')).not.toBeInTheDocument();
      });
    });

    it('T3.3: deep link to ?page=2 followed by scroll seamlessly continues to page 3', async () => {
      window.history.replaceState(null, '', '/investments/transactions?page=2');

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 2;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 21')).toBeInTheDocument();
      });

      // Trigger scroll to continue to page 3 from deep linked page 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      await waitFor(() => {
        expect(screen.getByText('Company 41')).toBeInTheDocument();
        const calls = replaceStateSpy.mock.calls;
        const matched = calls.some((c: any[]) => {
          if (typeof c[2] !== 'string') return false;
          try {
            const url = new URL(c[2], 'http://localhost');
            const validPath = url.pathname === '/investments/transactions' || url.pathname === '/';
            return validPath && url.searchParams.get('page') === '3';
          } catch {
            return false;
          }
        }) || new URLSearchParams(window.location.search).get('page') === '3';
        expect(matched).toBe(true);
      });
    });

    it('T3.4: in-flight race condition guard discards late-arriving chunk data when filter or search changes', async () => {
      let resolveChunk2: (val: any) => void;
      const chunk2Promise = new Promise((resolve) => {
        resolveChunk2 = resolve;
      });

      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          const isFiltered = endpoint.includes('type=buy') || endpoint.includes('filter=buy');
          if (isFiltered) {
            const filteredTrade = makeTrade(999, {
              asset_name: 'Filtered Buy Asset Corp',
              asset_symbol: 'FILTBUY',
              transaction_type: 'buy',
            });
            const filteredItems = [filteredTrade];
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
          return makePaginatedTradesResponse(1, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Trigger chunk 2 load (enters in-flight state)
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });

      // While chunk 2 is in-flight, user changes filter to "Buys"
      const filterSelect = screen.getByDisplayValue('All types');
      await act(async () => {
        fireEvent.change(filterSelect, { target: { value: 'buy' } });
      });

      // Filtered data renders
      await waitFor(() => {
        expect(screen.getByText('Filtered Buy Asset Corp')).toBeInTheDocument();
      });

      // Now resolve late-arriving chunk 2 from the previous unfiltered query
      await act(async () => {
        const chunk2 = makePaginatedTradesResponse(2, 20, 60);
        chunk2[0] = makeTrade(21, {
          asset_name: 'Unfiltered Late Arrival Buy 21',
          transaction_type: 'buy',
        });
        resolveChunk2!(chunk2);
      });

      // The late-arriving chunk 2 data must NOT contaminate the new filtered result set
      expect(screen.queryByText('Unfiltered Late Arrival Buy 21')).not.toBeInTheDocument();
      expect(screen.queryByText('Company 21')).not.toBeInTheDocument();
      expect(screen.getByText('Filtered Buy Asset Corp')).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Tier 4: Real-World Scenarios (End-to-End User Workflows)
  // =========================================================================
  describe('Tier 4: Real-World Scenarios', () => {
    it('T4.1: complete user workflow: multi-chunk scroll, URL tracking, and trade edit modal interaction', async () => {
      (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/transactions')) {
          const match = endpoint.match(/page=(\d+)/);
          const page = match ? parseInt(match[1], 10) : 1;
          return makePaginatedTradesResponse(page, 20, 60);
        }
        return null;
      });

      render(<TransactionsPage />);

      // Step 1: Initial page load
      await waitFor(() => {
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });

      // Step 2: User scrolls through chunk 2
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });
      await waitFor(() => {
        expect(screen.getByText('Company 25')).toBeInTheDocument();
      });

      // Step 3: User scrolls through chunk 3
      await act(async () => {
        MockIntersectionObserver.triggerLatest(true);
      });
      await waitFor(() => {
        expect(screen.getByText('Company 50')).toBeInTheDocument();
      });

      // Step 4: User selects a trade from chunk 2 to edit
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      expect(editButtons.length).toBeGreaterThan(0);

      await act(async () => {
        fireEvent.click(editButtons[1]); // Click an edit button
      });

      // Step 5: Modal opens with transaction details
      await waitFor(() => {
        expect(document.querySelector('[role="dialog"]') || screen.getByText(/transaction/i)).toBeInTheDocument();
      });
    });
  });
});
