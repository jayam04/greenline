"use client";

import React, { useRef, useState, useEffect } from "react";
import { Segmented } from "@/components/ui/tabs";
import { cn, money } from "@/lib/utils";

export interface BenchmarkSeries {
  id: string;
  name: string;
  color: string;
  data: { date: string; value: number }[];
}

export interface SnapshotData {
  snapshot_date: string;
  net_worth: number;
  total_invested?: number;
  total_current_value?: number;
  cash_balance?: number;
}

interface NetWorthChartProps {
  data: (SnapshotData | number)[];
  start?: string;
  height?: number;
  compact?: boolean;
  fill?: boolean;
  header?: React.ReactNode;
  className?: string;
  mode?: "value" | "performance";
  currency?: string;
  benchmarks?: BenchmarkSeries[];
  range?: string;
  onRangeChange?: (range: string) => void;
}

function parseDateParts(str?: string) {
  if (!str || typeof str !== "string") {
    const today = new Date();
    return { year: today.getFullYear(), month: today.getMonth(), day: today.getDate() };
  }
  const parts = str.split("-");
  return {
    year: parseInt(parts[0], 10),
    month: parseInt(parts[1] || "1", 10) - 1,
    day: parseInt(parts[2] || "1", 10),
  };
}

function formatDateISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function NetWorthChart({
  data,
  start: propStart,
  height = 260,
  compact = false,
  fill = false,
  header,
  className,
  currency = "EUR",
  range: propRange,
  onRangeChange: propOnRangeChange,
}: NetWorthChartProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const [internalRange, setInternalRange] = useState("YTD");
  const activeRange = propRange !== undefined ? propRange : internalRange;
  const setRange = (newRange: string) => {
    if (propOnRangeChange) propOnRangeChange(newRange);
    else setInternalRange(newRange);
  };
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    if (!fill || !boxRef.current || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height: hh } = e.contentRect;
      if (width > 0 && hh > 0) setSize({ w: Math.round(width), h: Math.round(hh) });
    });
    ro.observe(boxRef.current);
    return () => ro.disconnect();
  }, [fill]);

  if (!data || data.length === 0) {
    return (
      <div className="h-60 flex items-center justify-center text-muted font-medium text-xs">
        No timeline data available for this selection.
      </div>
    );
  }

  // Normalize data into uniform points
  interface NormalizedPoint {
    val: number;
    rawDate: string;
    label: string;
  }

  let normalized: NormalizedPoint[] = [];
  const defaultStart = propStart || "2026-01-01";

  if (typeof data[0] === "number") {
    const { year: sY, month: sM, day: sD } = parseDateParts(defaultStart);
    const baseD = new Date(sY, sM, sD);
    normalized = (data as number[]).map((v, i) => {
      const d = new Date(baseD);
      d.setDate(d.getDate() + i * 7);
      return {
        val: v,
        rawDate: formatDateISO(d),
        label: d.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric" }),
      };
    });
  } else {
    const snapshots = [...(data as (SnapshotData | any)[])].sort((a, b) => {
      const dateA = a.snapshot_date || a.date || "";
      const dateB = b.snapshot_date || b.date || "";
      return dateA.localeCompare(dateB);
    });
    normalized = snapshots.map((s) => {
      const dateStr = s.snapshot_date || s.date || formatDateISO(new Date());
      let label = dateStr;
      try {
        const { year, month, day } = parseDateParts(dateStr);
        const d = new Date(year, month, day);
        label = d.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric" });
      } catch {
        // fallback
      }
      return {
        val: (s.net_worth ?? s.netWorth ?? 0) / 1000,
        rawDate: dateStr,
        label,
      };
    });
  }

  // Calculate cutoff date string based on activeRange
  const latestDateStr = normalized[normalized.length - 1].rawDate;
  const { year: lYear, month: lMonth, day: lDay } = parseDateParts(latestDateStr);

  let cutoffStr = "";
  if (activeRange === "1M") {
    const d = new Date(lYear, lMonth - 1, lDay);
    cutoffStr = formatDateISO(d);
  } else if (activeRange === "3M") {
    const d = new Date(lYear, lMonth - 3, lDay);
    cutoffStr = formatDateISO(d);
  } else if (activeRange === "6M") {
    const d = new Date(lYear, lMonth - 6, lDay);
    cutoffStr = formatDateISO(d);
  } else if (activeRange === "YTD") {
    cutoffStr = `${lYear}-01-01`;
  } else if (activeRange === "1Y") {
    const d = new Date(lYear - 1, lMonth, lDay);
    cutoffStr = formatDateISO(d);
  } else {
    cutoffStr = ""; // Max
  }

  let filtered = cutoffStr ? normalized.filter((p) => p.rawDate >= cutoffStr) : normalized;

  // Anchor with prior baseline point if filtered only has 1 point, so chart draws line
  if (cutoffStr && filtered.length < 2) {
    const priorIdx = normalized.findIndex((p) => p.rawDate >= cutoffStr) - 1;
    if (priorIdx >= 0) {
      filtered = [normalized[priorIdx], ...filtered];
    } else if (filtered.length === 0) {
      filtered = normalized.slice(-2);
    }
  }

  const slice = filtered.map((p) => p.val);
  const sliceDates = filtered.map((p) => p.label);

  const W = fill ? size.w : 800;
  const H = fill ? size.h : height;
  const padL = 44;
  const padR = 8;
  const padT = 12;
  const padB = 26;

  const rawMin = Math.min(...slice);
  const rawMax = Math.max(...slice);

  // Dynamic bounds calculation
  let min: number;
  let max: number;

  if (rawMin >= 0) {
    min = 0;
    if (rawMax <= 1) {
      max = 1;
    } else if (rawMax <= 6) {
      max = 6;
    } else if (rawMax <= 12) {
      max = 12;
    } else if (rawMax <= 25) {
      max = Math.max(Math.ceil((rawMax * 1.15) / 5) * 5, 5);
    } else if (rawMax <= 60) {
      max = Math.max(Math.ceil((rawMax * 1.15) / 10) * 10, 10);
    } else {
      max = Math.max(Math.ceil((rawMax * 1.12) / 25) * 25, 25);
    }
  } else {
    const span = rawMax - rawMin;
    const step = span <= 10 ? 2 : span <= 50 ? 5 : span <= 200 ? 25 : 50;
    min = Math.floor(rawMin / step) * step;
    max = Math.ceil(rawMax / step) * step;
  }
  const deltaSpan = Math.max(max - min, 1);

  const x = (i: number) => padL + (i / Math.max(slice.length - 1, 1)) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - min) / deltaSpan) * (H - padT - padB);
  const line = slice.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(slice.length - 1)},${H - padB} L${x(0)},${H - padB} Z`;
  const ticks = [0, 1, 2, 3].map((i) => Math.round(min + (deltaSpan * i) / 3));

  const sym = currency === "USD" ? "$" : currency === "INR" ? "₹" : currency === "GBP" ? "£" : "€";

  const labelAt = (i: number) => sliceDates[i] || "";

  const selector = (
    <Segmented
      size="sm"
      value={activeRange}
      onChange={setRange}
      options={["1M", "3M", "6M", "YTD", "1Y", "Max"].map((r) => ({ value: r, label: r }))}
    />
  );

  return (
    <div className={cn(fill && "flex min-h-0 flex-1 flex-col", className)}>
      {header ? (
        <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
          <div>{header}</div>
          {selector}
        </div>
      ) : (
        <div className="mb-3 flex justify-end">{selector}</div>
      )}
      <div ref={boxRef} className={cn("relative", fill && "min-h-[200px] flex-1")}>
        {compact && hover !== null && (
          <div className="pointer-events-none absolute left-12 top-0 rounded-control border border-border bg-surface px-2 py-1 text-label tnum shadow-card z-10">
            <span className="font-medium">{money(slice[hover] * 1000, currency)}</span>
            <span className="ml-2 text-muted">{labelAt(hover)}</span>
          </div>
        )}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className={fill ? "absolute inset-0 size-full" : "w-full"}
          role="img"
          aria-label="Net worth over time"
          onMouseLeave={() => setHover(null)}
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - r.left) / r.width) * W;
            const i = Math.round(((px - padL) / (W - padL - padR)) * (slice.length - 1));
            setHover(Math.max(0, Math.min(slice.length - 1, i)));
          }}
        >
          <defs>
            <linearGradient id="nw-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.22" />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {ticks.map((t, idx) => (
            <g key={`tick-${t}-${idx}`}>
              <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray="3 4" />
              <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" className="tnum">
                {t === 0 ? `${sym}0` : `${sym}${t}k`}
              </text>
            </g>
          ))}
          <path d={area} fill="url(#nw-fill)" />
          <path d={line} fill="none" stroke="var(--chart-1)" strokeWidth="2" strokeLinejoin="round" />
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={padT} y2={H - padB} stroke="var(--border-strong)" />
              <circle
                cx={x(hover)}
                cy={y(slice[hover])}
                r="4.5"
                fill="var(--surface)"
                stroke="var(--chart-1)"
                strokeWidth="2"
              />
            </g>
          )}
          <text x={padL} y={H - 6} fontSize="11" fill="var(--muted)">
            {labelAt(0)}
          </text>
          <text x={W - padR} y={H - 6} fontSize="11" fill="var(--muted)" textAnchor="end">
            {labelAt(slice.length - 1)}
          </text>
        </svg>
      </div>
      {!compact && (
        <div className="mt-1 h-5 text-label text-muted tnum">
          {hover !== null ? (
            <>
              <span className="text-foreground font-medium">{money(slice[hover] * 1000, currency)}</span>
              <span className="ml-2">{labelAt(hover)}</span>
            </>
          ) : (
            <span>Hover the chart to inspect a week</span>
          )}
        </div>
      )}
    </div>
  );
}
