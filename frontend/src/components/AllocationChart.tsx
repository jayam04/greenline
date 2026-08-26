"use client";

import React, { useState } from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { formatMoney } from "@/lib/format";
import { useTheme } from "@/components/ThemeProvider";

interface AllocationChartProps {
  allocation: Record<string, number>;
  centerLabel?: string;
  centerValue?: string;
  currency?: string;
  showLegend?: boolean;
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

interface ChartItem {
  name: string;
  value: number;
  pct: number;
  color: string;
}

export function AllocationChart({ 
  allocation, 
  centerLabel = "Total Net Worth", 
  centerValue,
  currency = "USD",
  showLegend = false,
}: AllocationChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const [hoveredItem, setHoveredItem] = useState<ChartItem | null>(null);

  if (!allocation || Object.keys(allocation).length === 0) {
    return (
      <div className="h-56 flex items-center justify-center text-slate-400 dark:text-slate-500 font-medium text-xs">
        No allocation data available.
      </div>
    );
  }

  const total = Object.values(allocation).reduce((acc, v) => acc + v, 0);

  const chartData: ChartItem[] = Object.entries(allocation)
    .filter(([_, value]) => value > 0)
    .map(([key, value], idx) => ({
      name: key.toUpperCase(),
      value: Number(value.toFixed(2)),
      pct: total > 0 ? (value / total) * 100 : 0,
      color: GETQUIN_SPECTRUM_COLORS[idx % GETQUIN_SPECTRUM_COLORS.length],
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
              outerRadius={hoveredItem ? 98 : 95}
              paddingAngle={2}
              dataKey="value"
              stroke={isDark ? "#121824" : "#FFFFFF"}
              strokeWidth={2}
              onMouseEnter={(_, index) => {
                if (chartData[index]) {
                  setHoveredItem(chartData[index]);
                }
              }}
              onMouseLeave={() => {
                setHoveredItem(null);
              }}
            >
              {chartData.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.color} 
                  opacity={hoveredItem ? (hoveredItem.name === entry.name ? 1 : 0.45) : 1}
                  className="transition-opacity duration-200 cursor-pointer"
                />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload as ChartItem;
                  return (
                    <div className="bg-[#0F172A] dark:bg-slate-900 border border-slate-700/50 rounded-xl px-3 py-2 text-white shadow-xl text-xs space-y-0.5">
                      <div className="flex items-center gap-1.5 font-bold">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: data.color }} />
                        <span>{data.name}</span>
                      </div>
                      <div className="text-slate-300 font-semibold tabular-nums">
                        {formatMoney(data.value, currency)}
                      </div>
                      <div className="text-emerald-400 text-[10px] font-extrabold">
                        {data.pct.toFixed(1)}% of portfolio
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Dynamic Center Donut Content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4 transition-all duration-200">
          {hoveredItem ? (
            <>
              <div className="flex items-center gap-1 max-w-[130px] truncate">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: hoveredItem.color }} />
                <span className="text-[11px] font-bold text-slate-800 dark:text-slate-100 truncate">
                  {hoveredItem.name}
                </span>
              </div>
              <span className="text-sm font-black text-[#0F172A] dark:text-white tabular-nums mt-0.5">
                {formatMoney(hoveredItem.value, currency)}
              </span>
              <span className="text-[10px] font-extrabold text-emerald-600 dark:text-emerald-400 tabular-nums">
                {hoveredItem.pct.toFixed(1)}% allocation
              </span>
            </>
          ) : (
            <>
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                {centerLabel}
              </span>
              <span className="text-sm font-black text-[#0F172A] dark:text-white tabular-nums mt-0.5">
                {centerValue || formatMoney(total, currency, 0)}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Optional Sleek Legend List */}
      {showLegend && (
        <div className="w-full mt-2 grid grid-cols-2 gap-2 text-xs">
          {chartData.slice(0, 6).map((item) => (
            <div key={item.name} className="flex items-center justify-between py-1 px-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <div className="flex items-center gap-1.5 truncate">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="font-semibold text-slate-700 dark:text-slate-300 truncate">{item.name}</span>
              </div>
              <span className="font-bold text-slate-900 dark:text-white tabular-nums ml-2">{item.pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
