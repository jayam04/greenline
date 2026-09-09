import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '@/app/settings/page';
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
};

const mockBackupConfig = {
  database_file: "investments.db",
  data_dir: "/data",
  active_db_path: "/data/investments.db",
  autobackup_enabled: true,
  autobackup_interval_hours: 24,
  autobackup_max_copies: 10,
  last_backup_timestamp: "2026-08-30T12:00:00Z",
  next_backup_timestamp: "2026-08-31T12:00:00Z",
  is_overdue: false,
  total_backups_count: 2,
};

const mockBackupList = {
  total_count: 2,
  backups: [
    {
      filename: "greenline_backup_manual_2026-08-30_100000.db",
      filepath: "/data/backups/greenline_backup_manual_2026-08-30_100000.db",
      size_bytes: 45056,
      size_formatted: "44.0 KB",
      created_at: "2026-08-30T10:00:00Z",
      kind: "manual",
      note: "Manual snapshot",
    },
    {
      filename: "greenline_backup_auto_2026-08-29_000000.db",
      filepath: "/data/backups/greenline_backup_auto_2026-08-29_000000.db",
      size_bytes: 45056,
      size_formatted: "44.0 KB",
      created_at: "2026-08-29T00:00:00Z",
      kind: "auto",
      note: null,
    },
  ],
};

describe('SettingsPage Backups Management (Layer 3A)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders active database file name, auto-backup settings, and backup history', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/settings') return mockSettings;
      if (endpoint === '/backup/config') return mockBackupConfig;
      if (endpoint === '/backup/list') return mockBackupList;
      return {};
    });

    render(<SettingsPage />);

    expect(screen.getByText(/System Settings/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('investments.db')).toBeInTheDocument();
      expect(screen.getByText(/Database & Auto-Backup Management/i)).toBeInTheDocument();
    });

    // Check backup files are listed in table
    expect(screen.getByText('greenline_backup_manual_2026-08-30_100000.db')).toBeInTheDocument();
    expect(screen.getByText('greenline_backup_auto_2026-08-29_000000.db')).toBeInTheDocument();
  });

  it('triggers manual backup creation when Backup Now button is clicked', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/settings') return mockSettings;
      if (endpoint === '/backup/config') return mockBackupConfig;
      if (endpoint === '/backup/list') return mockBackupList;
      if (endpoint === '/backup/create' && options?.method === 'POST') {
        return {
          filename: "greenline_backup_manual_2026-08-30_140000.db",
          size_formatted: "44.0 KB",
          created_at: "2026-08-30T14:00:00Z",
          kind: "manual",
        };
      }
      return {};
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Backup Now/i })).toBeInTheDocument();
    });

    const backupBtn = screen.getByRole('button', { name: /Backup Now/i });
    fireEvent.click(backupBtn);

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/backup/create', {
        method: 'POST',
        body: JSON.stringify({ note: 'Manual Snapshot' }),
      });
    });
  });

  it('updates auto-backup interval setting when dropdown is changed', async () => {
    (api.apiFetch as any).mockImplementation(async (endpoint: string) => {
      if (endpoint === '/settings') return mockSettings;
      if (endpoint === '/backup/config') return mockBackupConfig;
      if (endpoint === '/backup/list') return mockBackupList;
      return {};
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('Daily (24 Hours)')).toBeInTheDocument();
    });

    // Find the select for backup interval
    const intervalSelects = screen.getAllByRole('combobox');
    const intervalSelect = intervalSelects[0];
    fireEvent.change(intervalSelect, { target: { value: '12' } });

    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledWith('/backup/config', {
        method: 'PUT',
        body: JSON.stringify({ autobackup_interval_hours: 12 }),
      });
    });
  });
});
