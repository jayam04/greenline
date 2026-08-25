import { describe, it, expect } from 'vitest';

export function formatMoney(amount: number, currency: string = "EUR", decimals: number = 2): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "EUR",
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount);
  } catch {
    return `${amount.toFixed(decimals)} ${currency}`;
  }
}

describe('Currency Formatting Helper', () => {
  it('formats EUR amounts with correct symbol and precision', () => {
    const result = formatMoney(1234.56, 'EUR', 2);
    expect(result).toContain('1,234.56');
    expect(result).toContain('€');
  });

  it('formats INR amounts with correct precision', () => {
    const result = formatMoney(37823.10, 'INR', 2);
    expect(result).toContain('37,823.10');
    expect(result).toContain('₹');
  });

  it('formats USD amounts with correct precision', () => {
    const result = formatMoney(5000.0, 'USD', 2);
    expect(result).toContain('$5,000.00');
  });

  it('handles 0 decimals cleanly', () => {
    const result = formatMoney(5000.75, 'USD', 0);
    expect(result).toContain('$5,001');
  });

  it('gracefully handles unknown currency codes', () => {
    const result = formatMoney(100.0, 'INVALID_CURR', 2);
    expect(result).toBe('100.00 INVALID_CURR');
  });
});
