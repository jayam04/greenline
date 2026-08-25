import { describe, it, expect } from 'vitest';
import { 
  formatQty, 
  formatNum, 
  getCurrencySymbol, 
  formatMoney,
  formatCurrency,
  formatCleanMoney,
  convertCurrencyToEUR, 
  convertCurrency, 
  getMasterCurrency,
  SUPPORTED_CURRENCIES
} from '@/lib/format';

describe('Format Library (src/lib/format.ts)', () => {
  describe('formatQty', () => {
    it('formats quantities correctly', () => {
      expect(formatQty(186)).toBe('186');
      expect(formatQty(186.5)).toBe('186.5');
      expect(formatQty(0)).toBe('0');
      expect(formatQty(null)).toBe('0');
      expect(formatQty(undefined)).toBe('0');
      expect(formatQty(NaN)).toBe('0');
    });
  });

  describe('formatNum', () => {
    it('formats numbers with standard decimal places', () => {
      expect(formatNum(1234.5678, 2)).toBe('1,234.57');
      expect(formatNum(1234.5678, 0)).toBe('1,235');
      expect(formatNum(0, 2)).toBe('0.00');
      expect(formatNum(null)).toBe('0.00');
      expect(formatNum(undefined)).toBe('0.00');
      expect(formatNum(NaN)).toBe('0.00');
    });
  });

  describe('getCurrencySymbol', () => {
    it('retrieves correct currency symbols for supported codes', () => {
      expect(getCurrencySymbol('EUR')).toBe('€');
      expect(getCurrencySymbol('USD')).toBe('$');
      expect(getCurrencySymbol('INR')).toBe('₹');
      expect(getCurrencySymbol('GBP')).toBe('£');
      expect(getCurrencySymbol('JPY')).toBe('¥');
      expect(getCurrencySymbol('CAD')).toBe('CA$');
      expect(getCurrencySymbol('AUD')).toBe('A$');
      expect(getCurrencySymbol('CHF')).toBe('CHF');
      expect(getCurrencySymbol('SGD')).toBe('S$');
    });

    it('defaults to $ for empty or unknown currencies', () => {
      expect(getCurrencySymbol('')).toBe('$');
      expect(getCurrencySymbol(undefined)).toBe('$');
      expect(getCurrencySymbol('UNKNOWN')).toBe('$');
    });

    it('has all SUPPORTED_CURRENCIES configured with symbols and labels', () => {
      expect(SUPPORTED_CURRENCIES.length).toBeGreaterThanOrEqual(9);
      expect(SUPPORTED_CURRENCIES.find(c => c.code === 'EUR')?.symbol).toBe('€');
      expect(SUPPORTED_CURRENCIES.find(c => c.code === 'INR')?.symbol).toBe('₹');
    });
  });

  describe('formatMoney and formatCurrency', () => {
    it('formats positive numbers without sign by default', () => {
      expect(formatMoney(1234.56, 'USD', 2)).toBe('$1,234.56');
      expect(formatMoney(1234.56, 'EUR', 2)).toBe('€1,234.56');
      expect(formatMoney(37823.1, 'INR', 2)).toBe('₹37,823.10');
    });

    it('formats positive numbers with sign when showSign=true', () => {
      expect(formatMoney(1234.56, 'USD', 2, true)).toBe('+$1,234.56');
      expect(formatMoney(1234.56, 'EUR', 2, true)).toBe('+€1,234.56');
      expect(formatMoney(37823.1, 'INR', 2, true)).toBe('+₹37,823.10');
    });

    it('formats negative numbers with leading minus sign before currency symbol', () => {
      expect(formatMoney(-150.00, 'USD', 2)).toBe('-$150.00');
      expect(formatMoney(-150.00, 'EUR', 2)).toBe('-€150.00');
      expect(formatMoney(-30132.00, 'INR', 2)).toBe('-₹30,132.00');
    });

    it('handles zero, null, undefined, and NaN values safely', () => {
      expect(formatMoney(0, 'EUR', 2)).toBe('€0.00');
      expect(formatMoney(null, 'EUR', 2)).toBe('€0.00');
      expect(formatMoney(undefined, 'USD', 2)).toBe('$0.00');
      expect(formatMoney(NaN, 'INR', 2)).toBe('₹0.00');
    });

    it('formatCurrency is an alias of formatMoney', () => {
      expect(formatCurrency(500, 'EUR', 2)).toBe(formatMoney(500, 'EUR', 2));
    });
  });

  describe('formatCleanMoney', () => {
    it('formats numbers strictly without plus or minus signs', () => {
      expect(formatCleanMoney(5000, 'EUR', 2)).toBe('€5,000.00');
      expect(formatCleanMoney(-5000, 'EUR', 2)).toBe('€5,000.00');
      expect(formatCleanMoney(null, 'USD', 2)).toBe('$0.00');
      expect(formatCleanMoney(undefined, 'INR', 2)).toBe('₹0.00');
      expect(formatCleanMoney(NaN, 'GBP', 2)).toBe('£0.00');
    });
  });

  describe('Currency conversion helpers', () => {
    it('converts currencies to EUR correctly', () => {
      expect(convertCurrencyToEUR(100, 'EUR')).toBeCloseTo(100);
      expect(convertCurrencyToEUR(100, 'USD')).toBeCloseTo(92);
      expect(convertCurrencyToEUR(10000, 'INR')).toBeCloseTo(102);
    });

    it('converts between arbitrary currencies', () => {
      expect(convertCurrency(100, 'USD', 'USD')).toBeCloseTo(100);
      expect(convertCurrency(0, 'USD', 'EUR')).toBe(0);
      expect(convertCurrency(NaN, 'USD', 'EUR')).toBe(0);
    });

    it('retrieves default master currency when localStorage is empty', () => {
      expect(getMasterCurrency()).toBe('EUR');
    });
  });
});
