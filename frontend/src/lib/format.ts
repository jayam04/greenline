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
