"use client";

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface SnapshotData {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
}

interface NetWorthChartProps {
  data: SnapshotData[];
}

export function NetWorthChart({ data }: NetWorthChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-60 flex items-center justify-center text-slate-400 font-medium text-xs">
        No snapshot data available yet.
      </div>
    );
  }

  const formattedData = data.map((item) => ({
    date: item.snapshot_date,
    netWorth: item.net_worth,
    invested: item.total_invested,
  }));

  const formatCurrency = (val: number) => {
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}k`;
    return `$${val}`;
  };

  return (
    <div className="h-60 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="getquinAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2563EB" stopOpacity={0.18} />
              <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke="#94A3B8" 
            fontSize={10} 
            fontWeight={600} 
            tickLine={false} 
            axisLine={{ stroke: "#E2E8F0" }}
          />
          <YAxis
            stroke="#94A3B8"
            fontSize={10}
            fontWeight={600}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatCurrency}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0F172A",
              border: "none",
              borderRadius: "0.5rem",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
              color: "#FFFFFF",
              fontSize: "12px",
              fontWeight: "600",
              padding: "8px 12px",
            }}
            formatter={(value: any) => [`$${Number(value).toLocaleString()}`, "Net Worth"]}
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
