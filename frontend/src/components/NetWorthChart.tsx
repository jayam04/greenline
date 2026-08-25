"use client";

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  LineChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { formatMoney, getCurrencySymbol } from "@/lib/format";
import { useTheme } from "@/components/ThemeProvider";

export interface BenchmarkSeries {
  id: string;
  name: string;
  color: string;
  data: { date: string; value: number }[]; // normalized %
}

interface SnapshotData {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
}

interface NetWorthChartProps {
  data: SnapshotData[];
  mode?: "value" | "performance";
  currency?: string;
  benchmarks?: BenchmarkSeries[];
}

export function NetWorthChart({ 
  data, 
  mode = "value", 
  currency = "EUR", 
  benchmarks = []
}: NetWorthChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const gridStroke = isDark ? "#1E293B" : "#F1F5F9";
  const axisLineStroke = isDark ? "#334155" : "#E2E8F0";
  const tickTextStroke = isDark ? "#64748B" : "#94A3B8";
  const refLineStroke = isDark ? "#475569" : "#CBD5E1";
  const tooltipBg = "#0F172A";
  const tooltipBorder = isDark ? "1px solid #1E293B" : "none";

  if (!data || data.length === 0) {
    return (
      <div className="h-60 flex items-center justify-center text-slate-400 font-medium text-xs">
        No timeline data available for this selection.
      </div>
    );
  }

  const sym = getCurrencySymbol(currency);

  const formatCurrencyTick = (val: number) => {
    const absVal = Math.abs(val);
    const prefix = val < 0 ? `-${sym}` : sym;
    if (absVal >= 10000000) return `${prefix}${(absVal / 10000000).toFixed(1)}Cr`;
    if (absVal >= 100000) return `${prefix}${(absVal / 100000).toFixed(1)}L`;
    if (absVal >= 1000000) return `${prefix}${(absVal / 1000000).toFixed(1)}M`;
    if (absVal >= 1000) return `${prefix}${(absVal / 1000).toFixed(0)}k`;
    return `${prefix}${absVal}`;
  };

  const formatPercentTick = (val: number) => {
    return `${val >= 0 ? "+" : ""}${val.toFixed(1)}%`;
  };

  // Build unified date points merging snapshot data and benchmarks
  const dateSet = new Set<string>();
  data.forEach((d) => dateSet.add(d.snapshot_date));
  benchmarks.forEach((bm) => bm.data.forEach((p) => dateSet.add(p.date)));
  const sortedDates = Array.from(dateSet).sort();

  // Create lookup maps for benchmarks
  const bmMap: Record<string, Record<string, number>> = {};
  benchmarks.forEach((bm) => {
    bmMap[bm.id] = {};
    bm.data.forEach((p) => {
      bmMap[bm.id][p.date] = p.value;
    });
  });

  const snapshotMap: Record<string, SnapshotData> = {};
  data.forEach((d) => {
    snapshotMap[d.snapshot_date] = d;
  });

  // Interpolate forward for smooth lines
  let lastNetWorth = data[0]?.net_worth || 0;
  let lastInvested = data[0]?.total_invested || 0;

  const mergedChartData = sortedDates.map((date) => {
    if (snapshotMap[date]) {
      lastNetWorth = snapshotMap[date].net_worth;
      lastInvested = snapshotMap[date].total_invested;
    }

    // Profit & Loss %: (Net Worth - Invested) / Invested * 100
    const pnl = lastNetWorth - lastInvested;
    const pnlPct = lastInvested > 0 ? (pnl / lastInvested) * 100 : 0;

    const row: Record<string, any> = {
      date,
      netWorth: lastNetWorth,
      invested: lastInvested,
      portfolioReturn: Number(pnlPct.toFixed(2)),
    };

    benchmarks.forEach((bm) => {
      if (bmMap[bm.id] && bmMap[bm.id][date] !== undefined) {
        row[bm.id] = bmMap[bm.id][date];
      }
    });

    return row;
  });

  // In Performance Mode (P&L %)
  // In Performance Mode (P&L %)
  if (mode === "performance") {
    return (
      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={mergedChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <ReferenceLine y={0} stroke={refLineStroke} strokeDasharray="2 2" />
            <XAxis 
              dataKey="date" 
              stroke={tickTextStroke} 
              fontSize={10} 
              fontWeight={600} 
              tickLine={false} 
              axisLine={{ stroke: axisLineStroke }}
            />
            <YAxis
              stroke={tickTextStroke}
              fontSize={10}
              fontWeight={600}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatPercentTick}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: tooltipBg,
                border: tooltipBorder,
                borderRadius: "0.5rem",
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.2)",
                color: "#FFFFFF",
                fontSize: "12px",
                fontWeight: "600",
                padding: "8px 12px",
              }}
              formatter={(value: any, name: any) => {
                const num = Number(value);
                const prefix = num >= 0 ? "+" : "";
                let label = "Portfolio P&L %";
                if (name !== "portfolioReturn") {
                  const foundBm = benchmarks.find((b) => b.id === name);
                  if (foundBm) label = foundBm.name;
                }
                return [`${prefix}${num.toFixed(2)}%`, label];
              }}
            />
            
            {/* Primary Portfolio P&L % Line */}
            <Line
              type="monotone"
              dataKey="portfolioReturn"
              name="portfolioReturn"
              stroke="#2563EB"
              strokeWidth={2.5}
              dot={false}
            />

            {/* Benchmark Comparison Lines */}
            {benchmarks.map((bm) => (
              <Line
                key={bm.id}
                type="monotone"
                dataKey={bm.id}
                name={bm.name}
                stroke={bm.color}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // In Value Mode (Area Chart in EUR)
  return (
    <div className="h-60 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={mergedChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="getquinAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2563EB" stopOpacity={0.18} />
              <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke={tickTextStroke} 
            fontSize={10} 
            fontWeight={600} 
            tickLine={false} 
            axisLine={{ stroke: axisLineStroke }}
          />
          <YAxis
            stroke={tickTextStroke}
            fontSize={10}
            fontWeight={600}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatCurrencyTick}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: tooltipBg,
              border: tooltipBorder,
              borderRadius: "0.5rem",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.2)",
              color: "#FFFFFF",
              fontSize: "12px",
              fontWeight: "600",
              padding: "8px 12px",
            }}
            formatter={(value: any) => [formatMoney(Number(value), currency), "Net Worth"]}
          />
          <Area
            type="monotone"
            dataKey="netWorth"
            stroke="#2563EB"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#getquinAreaGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
