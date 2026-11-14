/**
 * Whimsical Pseudonym Generator for Greenline Community
 * Combines vivid adjectives with animal and financial/market nouns
 * to create recognizable, whimsical pseudonyms (e.g. "Giant Elephant", "Crazy Dog").
 */

export const ADJECTIVES = [
  "Giant",
  "Crazy",
  "Golden",
  "Brave",
  "Silent",
  "Swift",
  "Wise",
  "Clever",
  "Mystic",
  "Stellar",
  "Bullish",
  "Bearish",
  "Lucky",
  "Noble",
  "Cosmic",
  "Jolly",
  "Fierce",
  "Calm",
  "Mighty",
  "Agile",
  "Electric",
  "Solar",
  "Lunar",
  "Emerald",
  "Ruby",
  "Sapphire",
  "Diamond",
  "Radiant",
  "Witty",
  "Vibrant",
  "Fearless",
  "Curious",
  "Daring",
  "Serene",
  "Gallant",
  "Eager",
  "Zealous",
  "Dynamic",
  "Shining",
  "Bold",
] as const;

export const NOUNS = [
  "Elephant",
  "Dog",
  "Falcon",
  "Otter",
  "Panda",
  "Bull",
  "Bear",
  "Eagle",
  "Fox",
  "Wolf",
  "Lynx",
  "Dolphin",
  "Whale",
  "Shark",
  "Hawk",
  "Badger",
  "Tiger",
  "Lion",
  "Cheetah",
  "Owl",
  "Bison",
  "Jaguar",
  "Leopard",
  "Gazelle",
  "Koala",
  "Hedgehog",
  "Stag",
  "Phoenix",
  "Dragon",
  "Raven",
  "Beaver",
  "Moose",
  "Panther",
  "Chameleon",
  "Pelican",
  "Robin",
  "Sparrow",
  "Stallion",
  "Condor",
  "Seal",
] as const;

// Compatibility aliases
export const PSEUDONYM_ADJECTIVES = ADJECTIVES;
export const PSEUDONYM_NOUNS = NOUNS;

export const PSEUDONYM_RULES = {
  MIN_LENGTH: 2,
  MAX_LENGTH: 50,
  ALLOWED_CHARACTERS_REGEX: /^[a-zA-Z0-9_\-\s]+$/,
} as const;

/**
 * Generates a whimsical two-word pseudonym combining an adjective and a noun.
 * Example outputs: "Giant Elephant", "Crazy Dog", "Golden Bull", "Brave Otter".
 */
export function generateRandomPseudonym(): string {
  const adjective = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)];
  return `${adjective} ${noun}`;
}

/**
 * Validates whether a given pseudonym meets length and character criteria.
 * @param name The pseudonym string to test
 * @returns boolean indicating validity
 */
export function isValidPseudonym(name: string | null | undefined): boolean {
  if (!name || typeof name !== "string") {
    return false;
  }
  const trimmed = name.trim();
  if (
    trimmed.length < PSEUDONYM_RULES.MIN_LENGTH ||
    trimmed.length > PSEUDONYM_RULES.MAX_LENGTH
  ) {
    return false;
  }
  return PSEUDONYM_RULES.ALLOWED_CHARACTERS_REGEX.test(trimmed);
}

/**
 * Normalizes pseudonym by trimming leading/trailing whitespace and collapsing multiple spaces.
 */
export function formatPseudonym(name: string): string {
  if (!name) return "";
  return name.trim().replace(/\s+/g, " ");
}
