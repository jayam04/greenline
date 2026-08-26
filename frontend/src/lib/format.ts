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

export interface CurrencyOption {
  code: string;
  symbol: string;
  label: string;
  country: string;
}

export const SUPPORTED_CURRENCIES: CurrencyOption[] = [
  { code: "EUR", symbol: "€", label: "Euro (EUR)", country: "European Union" },
  { code: "USD", symbol: "$", label: "US Dollar (USD)", country: "United States" },
  { code: "INR", symbol: "₹", label: "Indian Rupee (INR)", country: "India" },
  { code: "GBP", symbol: "£", label: "British Pound (GBP)", country: "United Kingdom" },
  { code: "CAD", symbol: "CA$", label: "Canadian Dollar (CAD)", country: "Canada" },
  { code: "AUD", symbol: "A$", label: "Australian Dollar (AUD)", country: "Australia" },
  { code: "JPY", symbol: "¥", label: "Japanese Yen (JPY)", country: "Japan" },
  { code: "CHF", symbol: "CHF", label: "Swiss Franc (CHF)", country: "Switzerland" },
  { code: "SGD", symbol: "S$", label: "Singapore Dollar (SGD)", country: "Singapore" },
];

export function getCurrencySymbol(currency?: string): string {
  if (!currency) return "$";
  const c = currency.trim().toUpperCase();
  const match = SUPPORTED_CURRENCIES.find((opt) => opt.code === c);
  if (match) return match.symbol;

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

/**
 * Bidirectional currency conversion helper
 */
export function convertCurrency(
  amount: number,
  fromCurrency: string = "USD",
  toCurrency: string = "EUR"
): number {
  if (!amount || isNaN(amount)) return 0;
  const src = (fromCurrency || "USD").trim().toUpperCase();
  const dst = (toCurrency || "EUR").trim().toUpperCase();
  if (src === dst) return amount;

  const rateFrom = FX_RATES_TO_EUR[src] ?? 1.0;
  const rateTo = FX_RATES_TO_EUR[dst] ?? 1.0;

  const inEUR = amount * rateFrom;
  return inEUR / rateTo;
}

export function convertCurrencyToEUR(amount: number, fromCurrency: string = "USD"): number {
  return convertCurrency(amount, fromCurrency, "EUR");
}

export function getMasterCurrency(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("greenline_master_currency");
    if (saved) return saved.trim().toUpperCase();
  }
  return "EUR";
}

/**
 * Formats annualized XIRR percentage:
 * - If XIRR > 10.0 (1000%), capped to "999%+"
 * - If XIRR < -10.0 (-1000%), capped to "-999%+"
 * - Otherwise formatted to specified decimals with % suffix
 */
export function formatXirr(val: number | null | undefined, decimals: number = 1): string {
  if (val === null || val === undefined || isNaN(val)) return "-";
  const num = Number(val);
  const pct = Math.abs(num) * 100;
  if (pct > 999.0 || Math.abs(num) >= 10.0) {
    return "999%+";
  }
  return `${pct.toFixed(decimals)}%`;
}
