"use client";

import React, { useState } from "react";
import { formatMoney } from "@/lib/format";
import { cn, money } from "@/lib/utils";

export type Slice = { label: string; value: number; color: string };

interface AllocationChartProps {
  allocation?: Record<string, number>;
  slices?: Slice[];
  centerLabel?: string;
  centerValue?: string;
  currency?: string;
  showLegend?: boolean;
  height?: number;
  compact?: boolean;
  className?: string;
}

const DEFAULT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "#6366F1",
  "#F59E0B",
  "#EC4899",
];

export function AllocationChart({
  allocation,
  slices: propSlices,
  centerLabel = "Total Net Worth",
  centerValue,
  currency = "EUR",
  showLegend = false,
  height = 224,
  compact = false,
  className,
}: AllocationChartProps) {
  const [active, setActive] = useState<number | null>(null);

  // Compute slices from propSlices or allocation Record
  const slices: Slice[] = React.useMemo(() => {
    if (propSlices && propSlices.length > 0) return propSlices;
    if (!allocation || Object.keys(allocation).length === 0) return [];
    return Object.entries(allocation)
      .filter(([_, val]) => val > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([label, value], idx) => ({
        label,
        value,
        color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length],
      }));
  }, [propSlices, allocation]);

  if (slices.length === 0) {
    return (
      <div
        data-testid="allocation-chart-wrapper"
        style={{ height: `${height}px` }}
        className="w-full flex items-center justify-center text-muted font-medium text-xs"
      >
        No allocation data available.
      </div>
    );
  }

  const total = slices.reduce((a, s) => a + s.value, 0);
  const R = 70;
  const C = 2 * Math.PI * R;
  let offset = 0;

  if (compact) {
    return (
      <div className={cn("flex items-center gap-5 w-full", className)}>
        <div className="relative shrink-0 size-36">
          <svg viewBox="0 0 180 180" className="-rotate-90">
            <circle cx="90" cy="90" r={R} fill="none" stroke="var(--surface-2)" strokeWidth="16" />
            {slices.map((s, i) => {
              const len = total > 0 ? (s.value / total) * C : 0;
              const el = (
                <circle
                  key={`compact-slice-${s.label}-${i}`}
                  cx="90"
                  cy="90"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={active === i ? 20 : 16}
                  strokeDasharray={`${Math.max(len - 3, 0)} ${C - Math.max(len - 3, 0)}`}
                  strokeDashoffset={-offset}
                  opacity={active === null || active === i ? 1 : 0.35}
                  onMouseEnter={() => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                  className="transition-all cursor-pointer"
                />
              );
              offset += len;
              return el;
            })}
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center px-1">
            <span className="eyebrow truncate max-w-[80px]">
              {active !== null ? slices[active].label : centerLabel}
            </span>
            <span className="font-semibold tnum text-body">
              {active !== null
                ? money(slices[active].value, currency, { maximumFractionDigits: 0 })
                : centerValue || money(total, currency, { maximumFractionDigits: 0 })}
            </span>
          </div>
        </div>
        <ul className="divide-y divide-border min-w-0 flex-1">
          {slices.map((s, i) => (
            <li
              key={s.label}
              className="py-2 cursor-pointer"
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
            >
              <span className="flex items-center gap-2 text-body font-medium">
                <span className="size-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
                <span className="truncate">{s.label}</span>
              </span>
              <span className="mt-0.5 block pl-[18px] text-label text-muted tnum">
                {money(s.value, currency, { maximumFractionDigits: 0 })} ·{" "}
                {total > 0 ? ((s.value / total) * 100).toFixed(1) : "0"}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className={cn("w-full flex flex-col items-center", className)}>
      <div
        data-testid="allocation-chart-wrapper"
        style={{ height: `${height}px` }}
        className="w-full relative flex items-center justify-center"
      >
        <svg viewBox="0 0 180 180" className="-rotate-90 h-full max-h-[220px]">
          <circle cx="90" cy="90" r={R} fill="none" stroke="var(--surface-2)" strokeWidth="16" />
          {slices.map((s, i) => {
            const len = total > 0 ? (s.value / total) * C : 0;
            const el = (
              <circle
                key={`slice-${s.label}-${i}`}
                cx="90"
                cy="90"
                r={R}
                fill="none"
                stroke={s.color}
                strokeWidth={active === i ? 20 : 16}
                strokeDasharray={`${Math.max(len - 3, 0)} ${C - Math.max(len - 3, 0)}`}
                strokeDashoffset={-offset}
                opacity={active === null || active === i ? 1 : 0.4}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                className="transition-all cursor-pointer"
              />
            );
            offset += len;
            return el;
          })}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4 transition-all duration-200">
          <span className="text-[10px] font-bold text-muted uppercase tracking-wider">
            {active !== null ? slices[active].label : centerLabel}
          </span>
          <span className="text-sm font-black text-foreground tabular-nums mt-0.5">
            {active !== null
              ? formatMoney(slices[active].value, currency, 0)
              : centerValue || formatMoney(total, currency, 0)}
          </span>
          {active !== null && total > 0 && (
            <span className="text-[10px] font-extrabold text-gain tabular-nums">
              {((slices[active].value / total) * 100).toFixed(1)}% allocation
            </span>
          )}
        </div>
      </div>

      {showLegend && (
        <div className="w-full mt-2 grid grid-cols-2 gap-2 text-xs">
          {slices.slice(0, 6).map((item, i) => (
            <div
              key={`legend-${item.label}-${i}`}
              className="flex items-center justify-between py-1 px-2 rounded-lg hover:bg-surface-2"
            >
              <div className="flex items-center gap-1.5 truncate">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="font-semibold text-foreground truncate">{item.label}</span>
              </div>
              <span className="font-bold text-foreground tabular-nums ml-2">
                {total > 0 ? ((item.value / total) * 100).toFixed(1) : "0"}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
