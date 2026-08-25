import { describe, it, expect } from 'vitest';
import { convertCurrency, getCurrencySymbol } from '@/lib/format';

describe('Cashflow Multi-Currency Conversions & Display', () => {
  it('correctly retrieves specific account currency symbols', () => {
    expect(getCurrencySymbol('USD')).toBe('$');
    expect(getCurrencySymbol('EUR')).toBe('€');
    expect(getCurrencySymbol('INR')).toBe('₹');
    expect(getCurrencySymbol('GBP')).toBe('£');
    expect(getCurrencySymbol('JPY')).toBe('¥');
    expect(getCurrencySymbol('CHF')).toBe('CHF');
  });

  it('accurately computes multi-currency account movement values in transaction currency', () => {
    // Account A: -1000 INR, Account B: +10.2 EUR in a EUR transaction
    const inrOutflow = -1000;
    const inrInEur = convertCurrency(inrOutflow, 'INR', 'EUR'); // 1000 * 0.0102 = 10.2 EUR
    expect(inrInEur).toBeCloseTo(-10.2, 2);

    const eurInflow = 10.2;
    const netEur = inrInEur + eurInflow;
    expect(Math.abs(netEur)).toBeLessThan(0.01);
  });
});
