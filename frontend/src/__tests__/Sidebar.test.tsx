import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/Sidebar';
import { ThemeProvider } from '@/components/ThemeProvider';

let currentPath = '/investments';

vi.mock('next/navigation', () => ({
  usePathname: () => currentPath,
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock('@/lib/auth', () => ({
  removeAuthToken: vi.fn(),
}));

describe('Sidebar Component', () => {
  it('renders flat grouped navigation: Home, Investing, Cashflow, Manage', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    // Section group headers
    expect(screen.getByText('Investing')).toBeInTheDocument();
    expect(screen.getByText('Cashflow')).toBeInTheDocument();
    expect(screen.getByText('Manage')).toBeInTheDocument();

    // Home link
    const homeLinks = screen.getAllByRole('link', { name: /Home/i });
    expect(homeLinks[0]).toHaveAttribute('href', '/');

    // Investing items: Portfolio, Holdings, Trades, Valuations, Reconcile
    const portfolioLinks = screen.getAllByRole('link', { name: /Portfolio/i });
    expect(portfolioLinks[0]).toHaveAttribute('href', '/investments');

    const holdingsLinks = screen.getAllByRole('link', { name: /Holdings/i });
    expect(holdingsLinks[0]).toHaveAttribute('href', '/investments/holdings');

    const tradesLinks = screen.getAllByRole('link', { name: /Trades/i });
    expect(tradesLinks[0]).toHaveAttribute('href', '/investments/transactions');

    const valuationsLinks = screen.getAllByRole('link', { name: /Valuations/i });
    expect(valuationsLinks[0]).toHaveAttribute('href', '/investments/valuations');

    const reconcileLinks = screen.getAllByRole('link', { name: /Reconcile/i });
    expect(reconcileLinks[0]).toHaveAttribute('href', '/investments/discrepancies');

    // Cashflow items: Income & spend, Transactions, Categories
    const cashflowOverviewLinks = screen.getAllByRole('link', { name: /Income & spend/i });
    expect(cashflowOverviewLinks[0]).toHaveAttribute('href', '/cashflow');

    const cashflowTxLinks = screen.getAllByRole('link', { name: /Transactions/i });
    expect(cashflowTxLinks[0]).toHaveAttribute('href', '/cashflow/transactions');

    const categoriesLinks = screen.getAllByRole('link', { name: /Categories/i });
    expect(categoriesLinks[0]).toHaveAttribute('href', '/categories');

    // Manage items: Accounts
    const accountsLinks = screen.getAllByRole('link', { name: /Accounts/i });
    expect(accountsLinks[0]).toHaveAttribute('href', '/accounts');

    // Settings icon link in user profile row
    const settingsLink = screen.getByRole('link', { name: /Settings/i });
    expect(settingsLink).toHaveAttribute('href', '/settings');
  });

  it('renders settings icon in user profile row and removes large settings button', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    // Should have exactly 1 settings link (the icon button in user profile row)
    const settingsLinks = screen.getAllByRole('link', { name: /Settings/i });
    expect(settingsLinks.length).toBe(1);
    expect(settingsLinks[0]).toHaveAttribute('aria-label', 'Settings');
  });

  it('renders logout button next to theme toggle in same row with red styling', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    const logoutBtn = screen.getByRole('button', { name: /log out/i });
    expect(logoutBtn).toBeInTheDocument();
    // Must have red styling
    expect(logoutBtn.className).toMatch(/rose|red/);
  });

  it('marks active link matching pathname with active indicator', () => {
    currentPath = '/investments/holdings';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    const holdingsLink = screen.getAllByRole('link', { name: /Holdings/i })[0];
    expect(holdingsLink).toHaveAttribute('aria-current', 'page');

    const portfolioLink = screen.getAllByRole('link', { name: /Portfolio/i })[0];
    expect(portfolioLink).not.toHaveAttribute('aria-current', 'page');
  });

  it('removes non-functional search box per design-1 specification', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    expect(screen.queryByPlaceholderText(/Search\.\.\./i)).not.toBeInTheDocument();
  });

  it('renders user profile section and logout button in footer', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
  });

  it('renders theme mode controls', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    expect(screen.getByRole('button', { name: /light mode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /dark mode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /system mode/i })).toBeInTheDocument();
  });

  it('does not violate hook order when navigating to /login', () => {
    currentPath = '/investments';
    const { rerender } = render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    // Change path to /login, which previously caused a hook order violation
    // because of an early return before a useEffect.
    currentPath = '/login';
    
    expect(() => {
      rerender(
        <ThemeProvider>
          <Sidebar />
        </ThemeProvider>
      );
    }).not.toThrow();
  });

  it('does not render AI Import link', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    expect(screen.queryByText(/AI Import/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /AI Import/i })).not.toBeInTheDocument();
  });

  it('renders Home navigation link pointing to /', () => {
    currentPath = '/';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    const homeLinks = screen.getAllByRole('link', { name: /Home/i });
    expect(homeLinks.length).toBeGreaterThan(0);
    expect(homeLinks[0]).toHaveAttribute('href', '/');
  });
});
