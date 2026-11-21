import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * tailwind-merge must know our custom font-size tokens (text-micro, text-label, ...).
 * Otherwise it treats them as text COLORS and silently drops e.g. text-primary-foreground
 * when both appear in one class list.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["micro", "label", "body", "title", "heading", "display"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function money(n: number, currency = "EUR", opts: Intl.NumberFormatOptions = {}) {
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
    ...opts,
  }).format(n);
}

export function signedMoney(n: number, currency = "EUR") {
  return (n > 0 ? "+" : n < 0 ? "−" : "") + money(Math.abs(n), currency);
}

export function pct(n: number, digits = 2) {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}%`;
}

