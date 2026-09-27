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
  it('renders links and sub-items for Investments and Cashflow', () => {
    currentPath = '/investments';
    render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    // Sidebar renders a link for Investments and Cashflow
    const investLink = screen.getAllByRole('link', { name: /Investments/i })[0];
    expect(investLink).toHaveAttribute('href', '/investments');

    const cashflowLink = screen.getAllByRole('link', { name: /Cashflows/i })[0];
    expect(cashflowLink).toHaveAttribute('href', '/cashflow');

    // Verify sub-navigation links are rendered permanently
    expect(screen.queryAllByRole('link', { name: /Holdings/i }).length).toBeGreaterThan(0);
    expect(screen.queryAllByRole('link', { name: /Categories/i }).length).toBeGreaterThan(0);
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
});
