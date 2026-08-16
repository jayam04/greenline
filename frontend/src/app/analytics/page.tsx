"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatNum } from "@/lib/format";
import { BarChart2, TrendingUp, Info } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface BenchmarkData {
  benchmark_name: string;
  data: { price_date: string; close_value: number }[];
}

export default function AnalyticsPage() {
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null);
  const [symbol, setSymbol] = useState("^GSPC");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBenchmark();
  }, [symbol]);

  const loadBenchmark = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<BenchmarkData>(`/benchmarks?symbol=${encodeURIComponent(symbol)}`);
      setBenchmark(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Performance & Benchmarks
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Compare historical asset price trends against major index benchmarks
          </p>
        </div>

        {/* Benchmark Pill Tabs */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => setSymbol("^GSPC")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${
              symbol === "^GSPC"
                ? "bg-[#0F172A] text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            S&P 500 (^GSPC)
          </button>
          <button
            onClick={() => setSymbol("^NSEI")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${
              symbol === "^NSEI"
                ? "bg-[#0F172A] text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Nifty 50 (^NSEI)
          </button>
        </div>
      </div>

      {/* Chart Container */}
      <div className="getquin-card p-5 space-y-3">
        <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
          <h2 className="text-sm font-bold text-[#0F172A]">
            {benchmark?.benchmark_name || "Benchmark"} Index Historical Trend
          </h2>
          <span className="text-[11px] font-semibold text-slate-400">
            1 Year Daily Close
          </span>
        </div>

        <div className="h-72 w-full">
          {benchmark?.data && benchmark.data.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmark.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis 
                  dataKey="price_date" 
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
                  domain={["auto", "auto"]} 
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    border: "none",
                    borderRadius: "0.5rem",
                    color: "#FFFFFF",
                    fontSize: "12px",
                    fontWeight: "600",
                    padding: "8px 12px",
                  }}
                  formatter={(value: any) => [`${formatNum(Number(value))}`, "Index Value"]}
                />
                <Line
                  type="monotone"
                  dataKey="close_value"
                  name={benchmark.benchmark_name}
                  stroke="#2563EB"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 font-medium text-xs">
              Loading benchmark data...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
