import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '@/app/settings/page';
import { FontProvider } from '@/components/FontProvider';
import * as api from '@/lib/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
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
  community_pseudonym: "Golden Falcon",
};

describe('Settings Page - Community Profile & Pseudonym Management', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    (api.apiFetch as any).mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/settings') {
        if (options?.method === 'PUT') {
          return JSON.parse(options.body);
        }
        return { ...mockSettings };
      }
      if (endpoint === '/backup/config') return null;
      if (endpoint === '/backup/list') return { total_count: 0, backups: [] };
      if (endpoint === '/auth/api-keys') return [];
      return null;
    });
  });

  it('renders Community Profile & Pseudonym card with loaded pseudonym', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Profile & Pseudonym')).toBeInTheDocument();
    });

    expect(screen.getByText(/Choose a custom community display name or generate a whimsical pseudonym/i)).toBeInTheDocument();
    const input = screen.getByLabelText('Community Display Name') as HTMLInputElement;
    expect(input.value).toBe('Golden Falcon');
    expect(screen.getByRole('button', { name: /Pick Random Name/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Save$/i })).toBeInTheDocument();
  });

  it('generates a random whimsical pseudonym when clicking "Pick Random Name"', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Profile & Pseudonym')).toBeInTheDocument();
    });

    const randomBtn = screen.getByRole('button', { name: /Pick Random Name/i });
    fireEvent.click(randomBtn);

    const input = screen.getByLabelText('Community Display Name') as HTMLInputElement;
    expect(input.value).not.toBe('Golden Falcon');
    expect(input.value.split(' ').length).toBe(2);
  });

  it('updates custom pseudonym and persists via PUT /settings when clicking Save', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Profile & Pseudonym')).toBeInTheDocument();
    });

    const input = screen.getByLabelText('Community Display Name');
    fireEvent.change(input, { target: { value: 'Crazy Dog' } });

    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"community_pseudonym":"Crazy Dog"'),
      }));
    });

    expect(localStorage.getItem('greenline_community_pseudonym')).toBe('Crazy Dog');
  });

  it('persists pseudonym when pressing Enter key in the input', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Profile & Pseudonym')).toBeInTheDocument();
    });

    const input = screen.getByLabelText('Community Display Name');
    fireEvent.change(input, { target: { value: 'Giant Elephant' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"community_pseudonym":"Giant Elephant"'),
      }));
    });
  });

  it('displays community alias in Current Profile summary card', async () => {
    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Alias')).toBeInTheDocument();
    });

    expect(screen.getByText('Golden Falcon')).toBeInTheDocument();
  });

  it('handles null community pseudonym gracefully', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/settings') {
        return {
          ...mockSettings,
          community_pseudonym: null,
        };
      }
      return null;
    });

    render(
      <FontProvider>
        <SettingsPage />
      </FontProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Community Profile & Pseudonym')).toBeInTheDocument();
    });

    const input = screen.getByLabelText('Community Display Name') as HTMLInputElement;
    expect(input.value).toBe('');
    expect(screen.getByText('Not set')).toBeInTheDocument();
  });
});
