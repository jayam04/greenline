import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Navbar } from '@/components/Navbar';
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

describe('Navbar Smart Dropdown & Routing (Task 3 & 4)', () => {
  it('opens Investments dropdown when clicking Investments while on /investments', () => {
    currentPath = '/investments';
    render(
      <ThemeProvider>
        <Navbar />
      </ThemeProvider>
    );

    // Click "Investments" tab
    const investLink = screen.getByRole('link', { name: /Investments/i });
    fireEvent.click(investLink);

    // Dropdown should be open
    expect(screen.getByRole('link', { name: /Holdings/i })).toHaveAttribute('href', '/investments/holdings');
    expect(screen.getByRole('link', { name: /Transactions/i })).toHaveAttribute('href', '/investments/transactions');
  });

  it('opens Cashflow dropdown when clicking Cashflow while on /cashflow', () => {
    currentPath = '/cashflow';
    render(
      <ThemeProvider>
        <Navbar />
      </ThemeProvider>
    );

    // Click "Cashflow" tab
    const cashflowLink = screen.getByRole('link', { name: /Cashflow/i });
    fireEvent.click(cashflowLink);

    // Dropdown should be open
    expect(screen.getByRole('link', { name: /Transactions/i })).toHaveAttribute('href', '/cashflow/transactions');
    expect(screen.getByRole('link', { name: /Categories/i })).toHaveAttribute('href', '/categories');
  });
});
