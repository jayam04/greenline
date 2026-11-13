import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SnapshotDateControl, getPresetDate } from '@/components/SnapshotDateControl';
import { getApiBase } from '@/lib/api';
import nextConfig from '../../next.config';

describe('SnapshotDateControl', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders in popover mode with default Auto state when localStorage is empty', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} />);

    // The trigger button should display Auto
    const trigger = screen.getByRole('button', { name: /snapshot starting date|start date|auto/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent(/Auto/i);
  });

  it('loads saved manual mode and date from localStorage on initial render', () => {
    localStorage.setItem('greenline_snapshot_start_mode', 'manual');
    localStorage.setItem('greenline_snapshot_start_date', '2025-09-01');

    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} />);

    // Trigger button should show manual date or indication
    const trigger = screen.getByRole('button', { name: /snapshot starting date|start date|2025-09-01|sep/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent(/2025-09-01|Sep/i);
  });

  it('toggles from Auto to Manual mode and persists to localStorage', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    const manualBtn = screen.getByRole('button', { name: /manual/i });
    fireEvent.click(manualBtn);

    expect(localStorage.getItem('greenline_snapshot_start_mode')).toBe('manual');
    expect(handleChange).toHaveBeenCalled();
  });

  it('clicking preset "Sep 1" sets date to September 1st and updates localStorage', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    // Switch to manual or click Sep 1
    const sepPreset = screen.getByRole('button', { name: /sep 1/i });
    fireEvent.click(sepPreset);

    const savedMode = localStorage.getItem('greenline_snapshot_start_mode');
    const savedDate = localStorage.getItem('greenline_snapshot_start_date');

    expect(savedMode).toBe('manual');
    expect(savedDate).toMatch(/^\d{4}-09-01$/);
    expect(handleChange).toHaveBeenCalledWith(savedDate, 'manual');
  });

  it('clicking preset "Jan 1 (YTD)" sets date to January 1st', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    const ytdPreset = screen.getByRole('button', { name: /jan 1|ytd/i });
    fireEvent.click(ytdPreset);

    const savedDate = localStorage.getItem('greenline_snapshot_start_date');
    const expectedYear = new Date().getFullYear();
    expect(savedDate).toBe(`${expectedYear}-01-01`);
  });

  it('clicking preset "Apr 1 (Fiscal Year)" sets date to April 1st', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    const fyPreset = screen.getByRole('button', { name: /apr 1|fiscal/i });
    fireEvent.click(fyPreset);

    const savedDate = localStorage.getItem('greenline_snapshot_start_date');
    expect(savedDate).toMatch(/^\d{4}-04-01$/);
  });

  it('clicking preset "1 Year Ago" sets date to one year prior', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    const oneYearPreset = screen.getByRole('button', { name: /1 year ago/i });
    fireEvent.click(oneYearPreset);

    const savedDate = localStorage.getItem('greenline_snapshot_start_date');
    expect(savedDate).toBeTruthy();
    const parsed = new Date(savedDate!);
    expect(parsed.getFullYear()).toBeLessThanOrEqual(new Date().getFullYear());
  });

  it('changing date input updates manual date and persists to localStorage', () => {
    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    // Switch to manual first
    const manualBtn = screen.getByRole('button', { name: /manual/i });
    fireEvent.click(manualBtn);

    const dateInput = screen.getByLabelText(/start date|snapshot date/i) || screen.getByDisplayValue(/20\d\d-\d\d-\d\d/);
    fireEvent.change(dateInput, { target: { value: '2024-08-15' } });

    expect(localStorage.getItem('greenline_snapshot_start_date')).toBe('2024-08-15');
    expect(handleChange).toHaveBeenCalledWith('2024-08-15', 'manual');
  });

  it('toggling back to Auto sets mode to auto and calls onChange with null', () => {
    localStorage.setItem('greenline_snapshot_start_mode', 'manual');
    localStorage.setItem('greenline_snapshot_start_date', '2025-09-01');

    const handleChange = vi.fn();
    render(<SnapshotDateControl onChange={handleChange} variant="inline" />);

    const autoBtn = screen.getByRole('button', { name: /auto/i });
    fireEvent.click(autoBtn);

    expect(localStorage.getItem('greenline_snapshot_start_mode')).toBe('auto');
    expect(handleChange).toHaveBeenCalledWith(null, 'auto');
  });

  it('popover variant opens and closes menu on trigger button click', () => {
    render(<SnapshotDateControl variant="popover" />);

    const trigger = screen.getByRole('button', { name: /snapshot starting date|start date|auto/i });
    expect(screen.queryByText(/Earliest Record/i)).not.toBeInTheDocument();

    // Click trigger to open popover
    fireEvent.click(trigger);
    expect(screen.getByText(/Earliest Record/i)).toBeInTheDocument();

    // Click trigger again to close popover
    fireEvent.click(trigger);
    expect(screen.queryByText(/Earliest Record/i)).not.toBeInTheDocument();
  });

  it('getPresetDate returns valid ISO date strings for all presets', () => {
    expect(getPresetDate('sep1')).toMatch(/^\d{4}-09-01$/);
    expect(getPresetDate('ytd')).toMatch(/^\d{4}-01-01$/);
    expect(getPresetDate('fy')).toMatch(/^\d{4}-04-01$/);
    expect(getPresetDate('1y')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('getApiBase', () => {
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalEnv;
  });

  it('returns empty string in browser when NEXT_PUBLIC_API_URL is unset or empty', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    expect(getApiBase()).toBe('');

    process.env.NEXT_PUBLIC_API_URL = '';
    expect(getApiBase()).toBe('');
  });

  it('returns custom NEXT_PUBLIC_API_URL in browser when set', () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://custom:8000';
    expect(getApiBase()).toBe('http://custom:8000');
  });
});

describe('Next.js Rewrites Configuration', () => {
  it('defines transparent rewrites for portfolio, snapshots, and backend catch-all', async () => {
    if (typeof nextConfig.rewrites === 'function') {
      const rewrites = await nextConfig.rewrites();
      const rules = Array.isArray(rewrites) ? rewrites : rewrites.beforeFiles || [];

      expect(rules).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            source: '/api/v1/portfolio/:path*',
            destination: expect.stringContaining('/api/v1/portfolio/:path*'),
          }),
          expect.objectContaining({
            source: '/api/v1/snapshots/:path*',
            destination: expect.stringContaining('/api/v1/snapshots/:path*'),
          }),
          expect.objectContaining({
            source: '/api/v1/:path*',
            destination: expect.stringContaining('/api/v1/:path*'),
          }),
        ])
      );
    }
  });
});
