import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { metadata } from '@/app/layout';
import LoginPage from '@/app/login/page';
import SettingsPage from '@/app/settings/page';
import CategoriesPage from '@/app/categories/page';
import * as api from '@/lib/api';

vi.mock('next/font/local', () => ({
  default: () => ({ className: 'mock-font' }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/',
}));

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  setAuthToken: vi.fn(),
}));

describe('Page Title Formatting & Metadata (Dynamic <PAGE TITLE> · greenline)', () => {
  it('configures Next.js RootLayout metadata with centered dot template and default title', () => {
    expect(metadata.title).toBeDefined();
    if (typeof metadata.title === 'object' && metadata.title !== null) {
      expect((metadata.title as any).template).toBe('%s · greenline');
      expect((metadata.title as any).default).toBe('Overview · greenline');
    }
  });

  it('updates document.title on LoginPage mount', () => {
    render(<LoginPage />);
    expect(document.title).toBe('Login · greenline');
  });

  it('updates document.title on SettingsPage mount', () => {
    (api.apiFetch as any).mockResolvedValue({ master_currency: 'EUR' });
    render(<SettingsPage />);
    expect(document.title).toBe('Settings · greenline');
  });

  it('updates document.title on CategoriesPage mount', () => {
    (api.apiFetch as any).mockResolvedValue([]);
    render(<CategoriesPage />);
    expect(document.title).toBe('Categories · greenline');
  });
});
