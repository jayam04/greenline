"use client";

import React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";

interface AllocationChartProps {
  allocation: Record<string, number>;
}

const COLORS = [
  "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", 
  "#ec4899", "#14b8a6", "#64748b", "#06b6d4"
];

export function AllocationChart({ allocation }: AllocationChartProps) {
  if (!allocation || Object.keys(allocation).length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-slate-500 text-sm">
        No asset allocation data.
      </div>
    );
  }

  const chartData = Object.entries(allocation).map(([key, value]) => ({
    name: key.toUpperCase(),
    value: Number(value.toFixed(2)),
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={4}
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              borderColor: "#334155",
              borderRadius: "0.5rem",
              color: "#f8fafc",
            }}
            formatter={(value: any) => [`$${Number(value).toLocaleString()}`, "Valuation"]}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value: string) => (
              <span className="text-xs font-medium text-slate-300">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
