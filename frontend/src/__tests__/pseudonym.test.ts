import { describe, it, expect } from 'vitest';
import {
  generateRandomPseudonym,
  isValidPseudonym,
  formatPseudonym,
  ADJECTIVES,
  NOUNS,
  PSEUDONYM_RULES,
  PSEUDONYM_ADJECTIVES,
  PSEUDONYM_NOUNS,
} from '@/lib/pseudonym';

describe('Pseudonym Generator Library (pseudonym.ts)', () => {
  it('exports populated adjectives and nouns list containing required keywords', () => {
    expect(ADJECTIVES.length).toBeGreaterThanOrEqual(20);
    expect(NOUNS.length).toBeGreaterThanOrEqual(20);

    // Required by user request: "Giant Elephant", "Crazy Dog"
    expect(ADJECTIVES).toContain('Giant');
    expect(ADJECTIVES).toContain('Crazy');
    expect(NOUNS).toContain('Elephant');
    expect(NOUNS).toContain('Dog');

    // Financial & market keywords
    expect(NOUNS).toContain('Bull');
    expect(NOUNS).toContain('Bear');

    // Compatibility aliases
    expect(PSEUDONYM_ADJECTIVES).toBe(ADJECTIVES);
    expect(PSEUDONYM_NOUNS).toBe(NOUNS);
  });

  it('generates whimsical pseudonyms adhering to "<Adjective> <Noun>" pattern', () => {
    for (let i = 0; i < 50; i++) {
      const name = generateRandomPseudonym();
      expect(typeof name).toBe('string');
      const parts = name.split(' ');
      expect(parts.length).toBe(2);
      expect((ADJECTIVES as readonly string[])).toContain(parts[0]);
      expect((NOUNS as readonly string[])).toContain(parts[1]);
      expect(isValidPseudonym(name)).toBe(true);
    }
  });

  it('validates pseudonyms correctly with isValidPseudonym', () => {
    expect(isValidPseudonym('Giant Elephant')).toBe(true);
    expect(isValidPseudonym('Crazy Dog')).toBe(true);
    expect(isValidPseudonym('Crypto-Whale_99')).toBe(true);
    expect(isValidPseudonym('AB')).toBe(true);

    // Invalid cases
    expect(isValidPseudonym('')).toBe(false);
    expect(isValidPseudonym('   ')).toBe(false);
    expect(isValidPseudonym('A')).toBe(false); // too short (< 2)
    expect(isValidPseudonym('A'.repeat(51))).toBe(false); // too long (> 50)
    expect(isValidPseudonym(null as any)).toBe(false);
    expect(isValidPseudonym(undefined as any)).toBe(false);
    expect(isValidPseudonym('<script>alert(1)</script>')).toBe(false); // invalid characters
  });

  it('formats and normalizes pseudonyms correctly with formatPseudonym', () => {
    expect(formatPseudonym('  Giant   Elephant  ')).toBe('Giant Elephant');
    expect(formatPseudonym('')).toBe('');
  });
});
