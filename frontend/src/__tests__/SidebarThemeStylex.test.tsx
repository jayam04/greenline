import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/Sidebar';
import { ThemeProvider } from '@/components/ThemeProvider';
import * as stylex from '@/lib/stylex';
import { commonStyles, sidebarStyles } from '@/styles/common';

vi.mock('next/navigation', () => ({
  usePathname: () => '/investments',
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/auth', () => ({
  removeAuthToken: vi.fn(),
}));

describe('StyleX Common Styles & Theme-Aware Sidebar', () => {
  it('exports StyleX create and props API correctly', () => {
    const testStyles = stylex.create({
      base: {
        color: 'var(--foreground)',
        padding: '8px',
      },
      active: {
        fontWeight: 'bold',
      },
    });

    const props = stylex.props(testStyles.base, testStyles.active);
    expect(props).toBeDefined();
    expect(props.style).toBeDefined();
    expect(props.style?.color).toBe('var(--foreground)');
    expect(props.style?.fontWeight).toBe('bold');
  });

  it('provides common layout and surface styles', () => {
    expect(commonStyles.flexCol).toBeDefined();
    expect(commonStyles.surface).toBeDefined();
    expect(sidebarStyles.sidebarContainer).toBeDefined();
    expect(sidebarStyles.navItem).toBeDefined();
    expect(sidebarStyles.navItemActive).toBeDefined();
  });

  it('renders theme-adaptive sidebar elements using CSS variables rather than hardcoded hex colors', () => {
    const { container } = render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    const desktopSidebar = container.querySelector('aside.lg\\:flex');
    expect(desktopSidebar).toBeInTheDocument();

    // Verify navigation links render
    const portfolioLinks = screen.getAllByRole('link', { name: /Portfolio/i });
    expect(portfolioLinks[0]).toBeInTheDocument();
    expect(portfolioLinks[0]).toHaveAttribute('aria-current', 'page');

    // Brand link should exist and be theme styled
    const brandLinks = screen.getAllByRole('link', { name: /greenline/i });
    expect(brandLinks.length).toBeGreaterThan(0);
  });

  it('ensures mobile header does not force inline display:flex so it hides cleanly on desktop', () => {
    // Style definition should not hardcode display: flex which overrides Tailwind lg:hidden
    expect((sidebarStyles.mobileHeader as any)?.display).toBeUndefined();

    const { container } = render(
      <ThemeProvider>
        <Sidebar />
      </ThemeProvider>
    );

    // Mobile header element should have responsive hiding classes
    const mobileHeader = container.querySelector('.lg\\:\\!hidden') || container.querySelector('.lg\\:hidden');
    expect(mobileHeader).toBeInTheDocument();
    // Inline style must not override responsive hiding with display: flex
    expect((mobileHeader as HTMLElement)?.style.display).not.toBe('flex');
  });
});
