"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { BarChart2, TrendingUp, Compass } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-emerald-400" />
            Performance & Benchmark Comparisons
          </h1>
          <p className="text-xs text-slate-400 mt-1">Compare portfolio XIRR against major market indices (S&P 500, Nifty 50)</p>
        </div>

        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-xs">
          <button
            onClick={() => setSymbol("^GSPC")}
            className={`px-3 py-1.5 rounded-md font-semibold transition-colors ${
              symbol === "^GSPC" ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-white"
            }`}
          >
            S&P 500 (^GSPC)
          </button>
          <button
            onClick={() => setSymbol("^NSEI")}
            className={`px-3 py-1.5 rounded-md font-semibold transition-colors ${
              symbol === "^NSEI" ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-white"
            }`}
          >
            Nifty 50 (^NSEI)
          </button>
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white">
            {benchmark?.benchmark_name || "Benchmark"} Index Price Movement
          </h2>
          <span className="text-xs font-mono text-emerald-400">1 Year Historical</span>
        </div>

        <div className="h-80 w-full">
          {benchmark?.data && benchmark.data.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmark.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="price_date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={["auto", "auto"]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    borderRadius: "0.5rem",
                    color: "#f8fafc",
                  }}
                  formatter={(value: any) => [`${Number(value).toFixed(2)}`, "Index Close"]}
                />
                <Line
                  type="monotone"
                  dataKey="close_value"
                  name={benchmark.benchmark_name}
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm">
              Loading benchmark data...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
