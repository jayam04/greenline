import { describe, it, expect } from 'vitest';
import { formatXirr } from '@/lib/format';

describe('formatXirr Unit Tests (Financial Format Integrity)', () => {
  it('returns "-" for null, undefined, or NaN values', () => {
    expect(formatXirr(null)).toBe('-');
    expect(formatXirr(undefined)).toBe('-');
    expect(formatXirr(NaN)).toBe('-');
  });

  it('formats normal positive XIRR values correctly', () => {
    expect(formatXirr(0.154)).toBe('15.4%');
    expect(formatXirr(0.245, 2)).toBe('24.50%');
    expect(formatXirr(0.0)).toBe('0.0%');
  });

  it('formats normal negative XIRR values without sign by default (for arrow icon UI)', () => {
    expect(formatXirr(-0.154)).toBe('15.4%');
    expect(formatXirr(-0.05, 2)).toBe('5.00%');
  });

  it('preserves negative sign when preserveSign flag is true', () => {
    expect(formatXirr(-0.154, 1, true)).toBe('-15.4%');
    expect(formatXirr(0.154, 1, true)).toBe('15.4%');
  });

  it('caps extreme positive XIRR (>= 1000% / 10.0) to "999%+"', () => {
    expect(formatXirr(10.0)).toBe('999%+');
    expect(formatXirr(15.5)).toBe('999%+');
    expect(formatXirr(50.0, 1, true)).toBe('999%+');
  });

  it('caps extreme negative XIRR (<= -1000% / -10.0) to "-999%+" when preserving sign or negative capping', () => {
    expect(formatXirr(-10.0, 1, true)).toBe('-999%+');
    expect(formatXirr(-15.5, 1, true)).toBe('-999%+');
    // When preserveSign is false (arrow UI), returns "999%+" magnitude
    expect(formatXirr(-15.5, 1, false)).toBe('999%+');
  });
});
