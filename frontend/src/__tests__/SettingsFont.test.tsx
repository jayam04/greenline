import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '@/app/settings/page';
import { FontProvider } from '@/components/FontProvider';
import * as api from '@/lib/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  removeAuthToken: vi.fn(),
}));

const mockSettings = {
  link_brokerage_with_bank: false,
  master_currency: "EUR",
  fiscal_year_start: "01-01",
  app_font: "general-sans",
};

describe('Settings Page - Interface Typography Selection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/settings') return { ...mockSettings };
      if (endpoint === '/backup/config') return null;
      if (endpoint === '/backup/list') return { total_count: 0, backups: [] };
      if (endpoint === '/auth/api-keys') return [];
      return null;
    });
  });

  it('renders Interface Typography card with General Sans and Inter options', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Interface Typography')).toBeInTheDocument();
    });

    expect(screen.getByText(/Select between the default geometric font/i)).toBeInTheDocument();
    expect(screen.getAllByText('General Sans').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Inter').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Default')).toBeInTheDocument();
    expect(screen.getByText('Clean UI')).toBeInTheDocument();
  });

  it('switches font to Inter when Inter card is clicked and persists to backend', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Interface Typography')).toBeInTheDocument();
    });

    const interButton = screen.getByRole('button', { name: /Inter.*Clean UI/i });
    fireEvent.click(interButton);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"app_font":"inter"')
      }));
    });

    expect(document.documentElement.getAttribute('data-font')).toBe('inter');
    expect(localStorage.getItem('greenline_font')).toBe('inter');
  });

  it('switches font back to General Sans when clicked', async () => {
    localStorage.setItem('greenline_font', 'inter');

    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Interface Typography')).toBeInTheDocument();
    });

    const generalSansButton = screen.getByRole('button', { name: /General Sans.*Default/i });
    fireEvent.click(generalSansButton);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"app_font":"general-sans"')
      }));
    });

    expect(document.documentElement.getAttribute('data-font')).toBe('general-sans');
    expect(localStorage.getItem('greenline_font')).toBe('general-sans');
  });
});
