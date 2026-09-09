import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { Breadcrumb } from '@/components/Breadcrumb';

let mockPathname = '/investments/holdings';

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
}));

describe('Breadcrumb Component (Task 1: Redesign & Sub-Page Navigation)', () => {
  it('renders full clickable hierarchical path for nested investment routes', () => {
    mockPathname = '/investments/holdings';
    render(<Breadcrumb />);

    const nav = screen.getByRole('navigation', { name: /Breadcrumb/i });

    // Breadcrumb parent links
    const homeLink = within(nav).getByRole('link', { name: /Net worth/i });
    expect(homeLink).toHaveAttribute('href', '/');

    const invLink = within(nav).getByRole('link', { name: /Investments/i });
    expect(invLink).toHaveAttribute('href', '/investments');

    // Current page label
    expect(within(nav).getByText('Holdings')).toBeInTheDocument();

    // Sibling quick navigation pills on the right side
    expect(screen.getByRole('link', { name: /Overview/i })).toHaveAttribute('href', '/investments');
    expect(screen.getByRole('link', { name: /Transactions/i })).toHaveAttribute('href', '/investments/transactions');
  });

  it('renders hierarchical path and sub-page tabs for cashflow routes', () => {
    mockPathname = '/cashflow/transactions';
    render(<Breadcrumb />);

    const nav = screen.getByRole('navigation', { name: /Breadcrumb/i });

    const homeLink = within(nav).getByRole('link', { name: /Net worth/i });
    expect(homeLink).toHaveAttribute('href', '/');

    const cfLink = within(nav).getByRole('link', { name: /Cashflow/i });
    expect(cfLink).toHaveAttribute('href', '/cashflow');

    // Sibling quick navigation pills on the right side
    expect(screen.getByRole('link', { name: /Overview/i })).toHaveAttribute('href', '/cashflow');
    expect(screen.getByRole('link', { name: /Categories/i })).toHaveAttribute('href', '/categories');
  });
});
