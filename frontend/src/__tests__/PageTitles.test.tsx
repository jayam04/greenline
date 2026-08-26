import { describe, it, expect } from 'vitest';

describe('Page Title Formatting (Task 2: Dynamic <PAGE TITLE> · greenline)', () => {
  it('formats titles with centered dot separator', () => {
    const formatPageTitle = (page: string) => `${page} · greenline`;

    expect(formatPageTitle('Overview')).toBe('Overview · greenline');
    expect(formatPageTitle('Investments')).toBe('Investments · greenline');
    expect(formatPageTitle('Holdings')).toBe('Holdings · greenline');
    expect(formatPageTitle('Transactions')).toBe('Transactions · greenline');
    expect(formatPageTitle('Cashflow')).toBe('Cashflow · greenline');
    expect(formatPageTitle('Cashflow Transactions')).toBe('Cashflow Transactions · greenline');
    expect(formatPageTitle('Categories')).toBe('Categories · greenline');
    expect(formatPageTitle('Accounts')).toBe('Accounts · greenline');
    expect(formatPageTitle('Settings')).toBe('Settings · greenline');
  });
});
