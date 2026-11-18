import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NetWorthDashboardPage from '@/app/page';
import { ThemeProvider } from '@/components/ThemeProvider';
import * as api from '@/lib/api';
import * as communityApi from '@/lib/community';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getAuthToken: vi.fn(() => 'mock-token'),
}));

vi.mock('@/lib/community', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/community')>();
  return {
    ...actual,
    fetchPosts: vi.fn(),
    createPost: vi.fn(),
    fetchComments: vi.fn(),
    createComment: vi.fn(),
    fetchRandomPseudonym: vi.fn(),
  };
});

describe('Unified Home Page (src/app/page.tsx)', () => {
  const mockAccounts = [
    {
      account_id: 1,
      account_name: 'Main Checking',
      broker_name: 'Chase',
      account_type: 'bank',
      currency: 'EUR',
      current_balance: 5000,
      cash_balance: 5000,
    },
    {
      account_id: 2,
      account_name: 'Brokerage Demat',
      broker_name: 'Interactive Brokers',
      account_type: 'demat',
      currency: 'USD',
      current_balance: 20000,
      cash_balance: 1000,
      securities_value: 19000,
    },
  ];

  const mockSummary = {
    net_worth: 25000,
    total_cost: 15000,
    unrealized_pnl: 4000,
    unrealized_pnl_pct: 26.6,
    realized_pnl: 1000,
    total_net_worth: 25000,
    total_invested: 15000,
    total_current_value: 19000,
    cash_balance: 6000,
    top_holdings: [],
    asset_allocation: { Stocks: 19000, Cash: 6000 },
    sector_allocation: {},
  };

  const mockSnapshots = [
    { snapshot_date: '2026-01-01', net_worth: 20000, total_invested: 15000 },
    { snapshot_date: '2026-11-14', net_worth: 25000, total_invested: 15000 },
  ];

  const mockAnnualSnapshot = {
    year_label: '2026',
    start_date: '2026-01-01',
    end_date: '2026-11-14',
    total_income: 12000,
    total_expenses: 4000,
    investments_done: 5000,
    investments_closed: 1000,
    net_worth_delta: 5000,
    net_worth_delta_pct: 25.0,
    taxes_and_fees: 300,
    net_savings: 8000,
    currency: 'EUR',
  };

  const mockPosts = [
    {
      id: 1,
      post_id: 1,
      author_sub: 'auth0|1',
      author_pseudonym: 'Giant Elephant',
      content: 'Just rebalanced my index fund portfolio for Q4!',
      media_attachments: null,
      comments_count: 1,
      created_at: '2026-11-14T08:00:00Z',
      updated_at: '2026-11-14T08:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    (communityApi.fetchRandomPseudonym as any).mockResolvedValue({
      pseudonym: 'Crazy Dog',
    });

    (communityApi.fetchPosts as any).mockResolvedValue({
      items: mockPosts,
      total_count: 1,
      limit: 20,
      offset: 0,
    });

    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/settings') {
        return {
          master_currency: 'EUR',
          fiscal_year_start: '01-01',
          community_pseudonym: 'Crazy Dog',
        };
      }
      if (endpoint === '/accounts') {
        return mockAccounts;
      }
      if (endpoint.startsWith('/portfolio/summary')) {
        return mockSummary;
      }
      if (endpoint.startsWith('/snapshots')) {
        return mockSnapshots;
      }
      if (endpoint.startsWith('/portfolio/annual_snapshot')) {
        return mockAnnualSnapshot;
      }
      return null;
    });
  });

  it('renders both portfolio overview metrics and community feed in unified layout', async () => {
    render(
      <ThemeProvider>
        <NetWorthDashboardPage />
      </ThemeProvider>
    );

    // Verify Overview metrics cards
    await waitFor(() => {
      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.getByText('Net worth')).toBeInTheDocument();
      expect(screen.getByText('Where it sits')).toBeInTheDocument();
      expect(screen.getByText(/2026 so far|so far/i)).toBeInTheDocument();
    });

    // Verify Add transaction button has been removed from Home page
    expect(screen.queryByText(/Add transaction/i)).not.toBeInTheDocument();

    // Verify static fallback numbers are not shown
    expect(screen.queryByText(/155,359/)).not.toBeInTheDocument();

    // Verify Community Feed integration
    expect(screen.getByText('Community')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Just rebalanced my index fund portfolio for Q4!')).toBeInTheDocument();
      expect(screen.getByText('Giant Elephant')).toBeInTheDocument();
    });
  });

  it('submits a new post from the home page composer and displays it', async () => {
    const newPost = {
      id: 2,
      post_id: 2,
      author_sub: 'auth0|me',
      author_pseudonym: 'Crazy Dog',
      content: 'Bought more VUAA today!',
      media_attachments: null,
      comments_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    (communityApi.createPost as any).mockResolvedValue(newPost);

    render(
      <ThemeProvider>
        <NetWorthDashboardPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Share an idea or ask a question|What's on your mind/i);
    fireEvent.change(textarea, { target: { value: 'Bought more VUAA today!' } });

    const shareBtn = screen.getByRole('button', { name: /Post|Publish|Share/i });
    fireEvent.click(shareBtn);

    await waitFor(() => {
      expect(communityApi.createPost).toHaveBeenCalledWith(
        expect.objectContaining({
          content: 'Bought more VUAA today!',
          author_pseudonym: 'Crazy Dog',
        })
      );
      expect(screen.getByText('Bought more VUAA today!')).toBeInTheDocument();
    });
  });

  it('expands comments thread on home page when clicking comments button', async () => {
    (communityApi.fetchComments as any).mockResolvedValue([
      {
        id: 11,
        comment_id: 11,
        post_id: 1,
        parent_comment_id: null,
        author_sub: 'auth0|user2',
        author_pseudonym: 'Wise Owl',
        content: 'Solid strategy! Keeping fees low.',
        created_at: '2026-11-14T08:30:00Z',
        updated_at: '2026-11-14T08:30:00Z',
      },
    ]);

    render(
      <ThemeProvider>
        <NetWorthDashboardPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Just rebalanced my index fund portfolio for Q4!')).toBeInTheDocument();
    });

    const commentsToggle = screen.getByRole('button', { name: /1 comment|1 comments|comments/i });
    fireEvent.click(commentsToggle);

    await waitFor(() => {
      expect(screen.getByText('Solid strategy! Keeping fees low.')).toBeInTheDocument();
      expect(screen.getByText(/@Wise Owl/i)).toBeInTheDocument();
    });
  });

  it('correctly converts foreign currency holdings to master currency in "Where it sits" allocation chart', async () => {
    (api.apiFetch as any).mockImplementation((url: string) => {
      if (url.includes('/portfolio/summary')) {
        return Promise.resolve({
          net_worth: 3844,
          total_invested: 3500,
          total_current_value: 344848.15,
          cash_balance: 326.51,
          top_holdings: [
            {
              asset_id: 101,
              symbol: 'TCS.NS',
              name: 'Tata Consultancy Services',
              asset_type: 'stock',
              currency: 'INR',
              quantity_held: 100,
              total_cost: 300000,
              current_value: 344848.15,
            },
          ],
          asset_allocation: { stock: 344848.15 },
        });
      }
      if (url.includes('/snapshots')) {
        return Promise.resolve([
          { snapshot_date: '2026-11-17', net_worth: 3844, total_invested: 3500 },
        ]);
      }
      if (url.includes('/accounts')) {
        return Promise.resolve([
          {
            account_id: 1,
            account_name: 'Zerodha',
            account_type: 'demat',
            currency: 'INR',
            cash_balance: 0,
            securities_value: 344848.15,
          },
          {
            account_id: 2,
            account_name: 'Revolut',
            account_type: 'bank',
            currency: 'EUR',
            cash_balance: 327,
            current_balance: 327,
          },
        ]);
      }
      if (url.includes('/settings')) {
        return Promise.resolve({ master_currency: 'EUR', community_pseudonym: 'Solar Beaver' });
      }
      if (url.includes('/community/posts')) {
        return Promise.resolve([]);
      }
      return Promise.resolve(null);
    });

    render(
      <ThemeProvider>
        <NetWorthDashboardPage />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Where it sits')).toBeInTheDocument();
    });

    // Slices in EUR: ~3,517 EUR for Stocks & ETFs, not 344,848!
    // And Cash & banks: €327
    await waitFor(() => {
      expect(screen.getByText('Stocks & ETFs')).toBeInTheDocument();
      expect(screen.getByText(/€3,517/)).toBeInTheDocument();
      expect(screen.getByText('Cash & banks')).toBeInTheDocument();
      expect(screen.getByText(/€327/)).toBeInTheDocument();
      expect(screen.queryByText(/344,848/)).not.toBeInTheDocument();
    });
  });
});
