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
}: NetWorthChartProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const [range, setRange] = useState("YTD");
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

  // Normalize data into number[] and date[]
  let numericValues: number[] = [];
  let dateLabels: string[] = [];
  let startDate = propStart || "2026-01-01";

  if (typeof data[0] === "number") {
    numericValues = data as number[];
    dateLabels = numericValues.map((_, i) => {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i * 7);
      return d.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric" });
    });
  } else {
    const snapshots = data as SnapshotData[];
    startDate = snapshots[0].snapshot_date;
    numericValues = snapshots.map((s) => s.net_worth / 1000);
    dateLabels = snapshots.map((s) => {
      try {
        const d = new Date(s.snapshot_date);
        return d.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric" });
      } catch {
        return s.snapshot_date;
      }
    });
  }

  const counts: Record<string, number> = {
    "1M": 5,
    "3M": 14,
    "6M": 28,
    "1Y": 52,
    YTD: numericValues.length,
    Max: numericValues.length,
  };
  const slice = numericValues.slice(-(counts[range] ?? numericValues.length));
  const sliceDates = dateLabels.slice(-(counts[range] ?? dateLabels.length));

  const W = fill ? size.w : 800;
  const H = fill ? size.h : height;
  const padL = 44;
  const padR = 8;
  const padT = 12;
  const padB = 26;

  const rawMin = Math.min(...slice);
  const rawMax = Math.max(...slice);
  const min = Math.floor(rawMin / 25) * 25 - 10;
  const max = Math.ceil(rawMax / 25) * 25 + 10;
  const deltaSpan = Math.max(max - min, 1);

  const x = (i: number) => padL + (i / Math.max(slice.length - 1, 1)) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - min) / deltaSpan) * (H - padT - padB);
  const line = slice.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(slice.length - 1)},${H - padB} L${x(0)},${H - padB} Z`;
  const ticks = [0, 1, 2, 3].map((i) => Math.round(min + (deltaSpan * i) / 3));

  const labelAt = (i: number) => sliceDates[i] || "";

  const selector = (
    <Segmented
      size="sm"
      value={range}
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
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray="3 4" />
              <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" className="tnum">
                €{t}k
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
