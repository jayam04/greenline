import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ClientLayout } from '@/components/ClientLayout';
import { ThemeProvider } from '@/components/ThemeProvider';

let mockPathname = '/';

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/auth', () => ({
  removeAuthToken: vi.fn(),
}));

describe('ClientLayout Component', () => {
  it('renders responsive layout with flex-col on mobile and lg:flex-row on desktop', () => {
    mockPathname = '/';
    const { container } = render(
      <ThemeProvider>
        <ClientLayout>
          <div>Dashboard Content</div>
        </ClientLayout>
      </ThemeProvider>
    );

    // Root wrapper must have flex-col and lg:flex-row to properly stack mobile header above content
    const rootWrapper = container.firstElementChild as HTMLElement;
    expect(rootWrapper).toBeInTheDocument();
    expect(rootWrapper.className).toContain('min-h-screen');
    expect(rootWrapper.className).toContain('flex');
    expect(rootWrapper.className).toContain('flex-col');
    expect(rootWrapper.className).toContain('lg:flex-row');

    // Main content container has lg:pl-64 to clear the 256px fixed sidebar on desktop
    const mainWrapper = rootWrapper.querySelector('.flex-1.flex.flex-col.w-full');
    expect(mainWrapper).toBeInTheDocument();
    expect(mainWrapper?.className).toContain('lg:pl-64');

    // Main content itself is rendered
    expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  });

  it('renders login page without sidebar or desktop padding', () => {
    mockPathname = '/login';
    const { container } = render(
      <ThemeProvider>
        <ClientLayout>
          <div>Login Form</div>
        </ClientLayout>
      </ThemeProvider>
    );

    const rootWrapper = container.firstElementChild as HTMLElement;
    const mainWrapper = rootWrapper.querySelector('.flex-1.flex.flex-col.w-full');
    expect(mainWrapper?.className).not.toContain('lg:pl-64');
    expect(container.querySelector('aside')).toBeNull();
  });

  it('renders print page with print-layout class and no sidebar', () => {
    mockPathname = '/cashflow/transactions/print';
    const { container } = render(
      <ThemeProvider>
        <ClientLayout>
          <div>Print Document</div>
        </ClientLayout>
      </ThemeProvider>
    );

    const printMain = container.querySelector('main.print-layout');
    expect(printMain).toBeInTheDocument();
    expect(container.querySelector('aside')).toBeNull();
  });
});
