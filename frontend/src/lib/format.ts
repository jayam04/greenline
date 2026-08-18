export function formatQty(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return "0";
  const num = Number(val);
  if (isNaN(num)) return "0";
  
  // Clean formatting for quantities, avoiding scientific notation e+xx
  const formatted = num.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return formatted;
}

export function formatNum(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "0.00";
  const num = Number(val);
  if (isNaN(num)) return "0.00";

  return num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function getCurrencySymbol(currency?: string): string {
  if (!currency) return "$";
  const c = currency.trim().toUpperCase();
  switch (c) {
    case "EUR":
      return "€";
    case "INR":
      return "₹";
    case "GBP":
      return "£";
    case "JPY":
      return "¥";
    case "CAD":
      return "CA$";
    case "AUD":
      return "A$";
    case "CHF":
      return "CHF ";
    case "SGD":
      return "S$";
    case "USD":
    default:
      return "$";
  }
}

/**
 * Formats a monetary number with correct sign placement:
 * Negative: -$150.00, -€150.00, -₹150.00
 * Positive with showSign: +$150.00, +€150.00, +₹150.00
 * Neutral / Standard: $150.00, €150.00, ₹150.00
 */
export function formatMoney(
  val: number | null | undefined,
  currency: string = "USD",
  decimals: number = 2,
  showSign: boolean = false
): string {
  if (val === null || val === undefined || isNaN(val)) {
    const sym = getCurrencySymbol(currency);
    return `${sym}0.00`;
  }

  const num = Number(val);
  const sym = getCurrencySymbol(currency);
  const absNum = Math.abs(num);
  const formattedNum = formatNum(absNum, decimals);

  if (num < -0.0000001) {
    return `-${sym}${formattedNum}`;
  } else if (num > 0.0000001 && showSign) {
    return `+${sym}${formattedNum}`;
  } else {
    return `${sym}${formattedNum}`;
  }
}

export const formatCurrency = formatMoney;

/**
 * Formats a monetary number WITHOUT any + or - signs:
 * e.g., $150.00, €150.00, ₹5,635.80
 */
export function formatCleanMoney(
  val: number | null | undefined,
  currency: string = "USD",
  decimals: number = 2
): string {
  if (val === null || val === undefined || isNaN(val)) {
    const sym = getCurrencySymbol(currency);
    return `${sym}0.00`;
  }

  const num = Number(val);
  const sym = getCurrencySymbol(currency);
  const absNum = Math.abs(num);
  const formattedNum = formatNum(absNum, decimals);
  return `${sym}${formattedNum}`;
}

/**
 * FX Exchange rates to EUR (Base: EUR = 1.0)
 */
export const FX_RATES_TO_EUR: Record<string, number> = {
  EUR: 1.0,
  USD: 0.92,      // 1 USD ≈ 0.92 EUR
  INR: 0.0102,    // 1 INR ≈ 0.0102 EUR (or ~98 INR / EUR)
  GBP: 1.17,      // 1 GBP ≈ 1.17 EUR
  CAD: 0.67,      // 1 CAD ≈ 0.67 EUR
  AUD: 0.60,      // 1 AUD ≈ 0.60 EUR
  JPY: 0.0059,    // 1 JPY ≈ 0.0059 EUR
  CHF: 1.06,      // 1 CHF ≈ 1.06 EUR
  SGD: 0.68,      // 1 SGD ≈ 0.68 EUR
};

export function convertCurrencyToEUR(amount: number, fromCurrency: string = "USD"): number {
  if (!amount || isNaN(amount)) return 0;
  const curr = fromCurrency.trim().toUpperCase();
  const rate = FX_RATES_TO_EUR[curr] ?? 0.92; // default USD rate fallback
  return amount * rate;
}
