import * as React from "react";
import { TrendBadge } from "@/components/ui/badge";
import { cn, money } from "@/lib/utils";

/** KPI card. Label (eyebrow) -> value -> delta + timeframe. One pattern for every number summary. */
export function MetricCard({
  label,
  value,
  display,
  currency = "EUR",
  delta,
  tone,
  hint,
  className,
}: {
  label: string;
  value?: number;
  /** Pre-formatted value (e.g. "27.4%"). Overrides money formatting. */
  display?: string;
  currency?: string;
  delta?: number;
  tone?: "gain" | "loss";
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("rounded-card border border-border bg-surface p-4 shadow-card", className)}>
      <div className="eyebrow">{label}</div>
      <div className={cn("mt-1.5 text-heading font-semibold tnum", tone === "gain" && "text-gain", tone === "loss" && "text-loss")}>
        {display ?? (value !== undefined ? money(value, currency) : "—")}
      </div>
      {(delta !== undefined || hint) && (
        <div className="mt-2 flex items-center gap-2">
          {delta !== undefined && <TrendBadge value={delta} />}
          {hint && <span className="text-micro text-muted">{hint}</span>}
        </div>
      )}
    </div>
  );
}

/** Hero card for the primary balance. */
export function HeroCard({
  label,
  value,
  delta,
  deltaAmount,
  currency = "EUR",
  deltaLabel = "YTD baseline",
  children,
}: {
  label: string;
  value: number;
  delta?: number;
  deltaAmount?: number;
  currency?: string;
  deltaLabel?: string;
  children?: React.ReactNode;
}) {
  const parts = Math.abs(value).toFixed(2).split(".");
  const whole = parts[0];
  const cents = parts[1];
  const isNeg = value < 0;
  const sym = currency === "USD" ? "$" : currency === "INR" ? "₹" : currency === "GBP" ? "£" : "€";

  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="mt-1 flex items-baseline gap-1 tnum">
        <span className="text-display font-semibold tracking-tight">
          {isNeg ? "−" : ""}{sym}{Number(whole).toLocaleString("en-IE")}
        </span>
        <span className="text-title text-subtle">.{cents}</span>
      </div>
      {(delta !== undefined || deltaAmount !== undefined) && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {delta !== undefined && <TrendBadge value={delta} />}
          {deltaAmount !== undefined && (
            <span className={cn("text-label tnum", deltaAmount >= 0 ? "text-gain" : "text-loss")}>
              {deltaAmount >= 0 ? "+" : "−"}{money(Math.abs(deltaAmount), currency)}
            </span>
          )}
          <span className="text-label text-muted">{deltaLabel || "YTD baseline"}</span>
        </div>
      )}
      {children}
    </div>
  );
}
