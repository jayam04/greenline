import { describe, it, expect } from 'vitest';
import { 
  formatQty, 
  formatNum, 
  getCurrencySymbol, 
  convertCurrencyToEUR, 
  convertCurrency, 
  formatCleanMoney 
} from '@/lib/format';

describe('Format Library (src/lib/format.ts)', () => {
  it('formats quantities correctly', () => {
    expect(formatQty(186)).toBe('186');
    expect(formatQty(186.5)).toBe('186.5');
    expect(formatQty(0)).toBe('0');
    expect(formatQty(null)).toBe('0');
  });

  it('formats numbers with standard decimal places', () => {
    expect(formatNum(1234.5678, 2)).toBe('1,234.57');
    expect(formatNum(0, 2)).toBe('0.00');
    expect(formatNum(null)).toBe('0.00');
  });

  it('retrieves correct currency symbols', () => {
    expect(getCurrencySymbol('EUR')).toBe('€');
    expect(getCurrencySymbol('USD')).toBe('$');
    expect(getCurrencySymbol('INR')).toBe('₹');
    expect(getCurrencySymbol('GBP')).toBe('£');
    expect(getCurrencySymbol('JPY')).toBe('¥');
    expect(getCurrencySymbol('CHF')).toBe('CHF');
    expect(getCurrencySymbol('SGD')).toBe('S$');
  });

  it('converts currencies to EUR correctly', () => {
    expect(convertCurrencyToEUR(100, 'EUR')).toBeCloseTo(100);
    expect(convertCurrencyToEUR(100, 'USD')).toBeCloseTo(92);
    expect(convertCurrencyToEUR(10000, 'INR')).toBeCloseTo(102);
  });

  it('converts between arbitrary currencies', () => {
    const val = convertCurrency(100, 'USD', 'USD');
    expect(val).toBeCloseTo(100);
  });

  it('formats clean money strings', () => {
    const formatted = formatCleanMoney(5000, 'EUR', 2);
    expect(formatted).toContain('5,000.00');
    expect(formatted).toContain('€');
  });
});
