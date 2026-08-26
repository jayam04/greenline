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

describe('Navbar Component (Layer 1C: Clean Direct Navigation)', () => {
  it('renders direct links for Investments and Cashflow without dropdowns', () => {
    currentPath = '/investments';
    render(
      <ThemeProvider>
        <Navbar />
      </ThemeProvider>
    );

    const investLink = screen.getByRole('link', { name: /Investments/i });
    expect(investLink).toHaveAttribute('href', '/investments');

    const cashflowLink = screen.getByRole('link', { name: /Cashflow/i });
    expect(cashflowLink).toHaveAttribute('href', '/cashflow');

    // Verify sub-navigation dropdown links are not rendered in navbar
    expect(screen.queryByRole('link', { name: /Holdings/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Categories/i })).not.toBeInTheDocument();
  });
});
