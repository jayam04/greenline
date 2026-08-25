"use client";

import React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { formatMoney, getCurrencySymbol } from "@/lib/format";
import { useTheme } from "@/components/ThemeProvider";

interface AllocationChartProps {
  allocation: Record<string, number>;
  centerLabel?: string;
  centerValue?: string;
  currency?: string;
}

const GETQUIN_SPECTRUM_COLORS = [
  "#2563EB", // Royal Blue
  "#0284C7", // Sky Blue
  "#0D9488", // Teal
  "#10B981", // Emerald
  "#34D399", // Light Mint
  "#6366F1", // Indigo
  "#8B5CF6", // Violet
  "#F59E0B", // Amber
  "#EC4899", // Pink
  "#64748B", // Slate
];

export function AllocationChart({ 
  allocation, 
  centerLabel = "Total Net Worth", 
  centerValue,
  currency = "USD"
}: AllocationChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (!allocation || Object.keys(allocation).length === 0) {
    return (
      <div className="h-56 flex items-center justify-center text-slate-400 dark:text-slate-500 font-medium text-xs">
        No allocation data available.
      </div>
    );
  }

  const total = Object.values(allocation).reduce((acc, v) => acc + v, 0);

  const chartData = Object.entries(allocation)
    .filter(([_, value]) => value > 0)
    .map(([key, value]) => ({
      name: key.toUpperCase(),
      value: Number(value.toFixed(2)),
      pct: total > 0 ? (value / total) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="w-full flex flex-col items-center">
      <div className="h-56 w-full relative flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              startAngle={90}
              endAngle={-270}
              innerRadius={70}
              outerRadius={95}
              paddingAngle={2}
              dataKey="value"
              stroke={isDark ? "#121824" : "#FFFFFF"}
              strokeWidth={2}
            >
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={GETQUIN_SPECTRUM_COLORS[index % GETQUIN_SPECTRUM_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "#0F172A",
                border: isDark ? "1px solid #1E293B" : "none",
                borderRadius: "0.5rem",
                color: "#FFFFFF",
                fontSize: "12px",
                fontWeight: "600",
                padding: "8px 12px",
              }}
              formatter={(value: any, name: any) => [formatMoney(Number(value), currency), name]}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Center Donut Text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4">
          <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{centerLabel}</span>
          <span className="text-sm font-extrabold text-[#0F172A] dark:text-white tabular-nums mt-0.5">
            {centerValue || formatMoney(total, currency, 0)}
          </span>
        </div>
      </div>

      {/* Sleek Legend List */}
      <div className="w-full mt-2 grid grid-cols-2 gap-2 text-xs">
        {chartData.slice(0, 6).map((item, idx) => (
          <div key={item.name} className="flex items-center justify-between py-1 px-2 rounded-lg hover:bg-slate-50">
            <div className="flex items-center gap-1.5 truncate">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: GETQUIN_SPECTRUM_COLORS[idx % GETQUIN_SPECTRUM_COLORS.length] }}
              />
              <span className="font-semibold text-slate-700 truncate">{item.name}</span>
            </div>
            <span className="font-bold text-slate-900 tabular-nums ml-2">{item.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
