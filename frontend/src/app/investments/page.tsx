"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney, getCurrencySymbol, convertCurrencyToEUR, convertCurrency } from "@/lib/format";
import { NetWorthChart, BenchmarkSeries } from "@/components/NetWorthChart";
import { AllocationChart } from "@/components/AllocationChart";
import { TransactionModal } from "@/components/TransactionModal";
import { 
  Plus, Eye, EyeOff, MoreVertical, 
  ArrowUpRight, ArrowDownRight, 
  Settings, RefreshCw, X, Check, BarChart2, AlertCircle, Info, Briefcase
} from "lucide-react";
import Link from "next/link";

interface HoldingSummary {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  quantity_held: number;
  avg_cost_price: number;
  total_cost: number;
  latest_price: number;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  xirr?: number | null;
  weight_pct: number;
}

interface PortfolioSummary {
  net_worth: number;
  total_cost: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  cash_balance: number;
  total_fees: number;
  total_taxes: number;
  top_holdings: HoldingSummary[];
  asset_allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  portfolio_xirr?: number | null;
}

interface Snapshot {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
  total_current_value?: number;
  cash_balance?: number;
}

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
  account_type?: string;
}

interface BenchmarkRawData {
  benchmark_name: string;
  data: { price_date: string; close_value: number }[];
}

const AVAILABLE_BENCHMARKS = [
  { id: "^GSPC", name: "S&P 500", color: "#64748B" },
  { id: "BTC-USD", name: "Bitcoin", color: "#F59E0B" },
  { id: "^NSEI", name: "Nifty 50", color: "#10B981" },
];

export default function InvestmentsDashboardPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");
  const [selectedAccount, setSelectedAccount] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("YTD");
  const [holdingsTimeRange, setHoldingsTimeRange] = useState<string>("Max");
  const [chartMode, setChartMode] = useState<"value" | "performance">("value");
  const [allocationTab, setAllocationTab] = useState<"positions" | "sectors" | "type">("positions");
  const [hideBalances, setHideBalances] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isBenchmarkModalOpen, setIsBenchmarkModalOpen] = useState(false);
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([]);
  const [benchmarksDataMap, setBenchmarksDataMap] = useState<Record<string, BenchmarkRawData>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Load Accounts and Master Currency on mount
  useEffect(() => {
    loadAccounts();
    apiFetch<{ master_currency: string }>("/settings")
      .then((res) => {
        if (res?.master_currency) {
          setMasterCurrency(res.master_currency.trim().toUpperCase());
        }
      })
      .catch(() => {
        const local = (typeof window !== "undefined" && localStorage.getItem("greenline_master_currency")) || "EUR";
        setMasterCurrency(local);
      });
  }, []);

  // Reload Summary & Snapshots whenever selectedAccount changes
  useEffect(() => {
    loadAccountData(selectedAccount);
  }, [selectedAccount]);

  const loadAccounts = async () => {
    try {
      const accData = await apiFetch<Account[]>("/accounts");
      setAccounts(accData || []);
    } catch (e) {
      console.error(e);
    }
  };

  const loadAccountData = async (accId: string) => {
    try {
      setLoading(true);
      const queryParam = accId === "all" ? "" : `?account_id=${accId}`;
      const [sumData, snapData] = await Promise.all([
        apiFetch<PortfolioSummary>(`/portfolio/summary${queryParam}`),
        apiFetch<Snapshot[]>(`/snapshots${queryParam}`),
      ]);
      setSummary(sumData);
      setSnapshots(snapData || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshPrices = async () => {
    try {
      setRefreshing(true);
      await apiFetch("/prices/refresh", { method: "POST" });
      await loadAccountData(selectedAccount);
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  // Toggle benchmark selection & fetch series
  const toggleBenchmark = async (bmId: string) => {
    if (selectedBenchmarks.includes(bmId)) {
      setSelectedBenchmarks(selectedBenchmarks.filter((id) => id !== bmId));
    } else {
      setSelectedBenchmarks([...selectedBenchmarks, bmId]);
      if (!benchmarksDataMap[bmId]) {
        try {
          const res = await apiFetch<BenchmarkRawData>(`/benchmarks?symbol=${encodeURIComponent(bmId)}`);
          if (res) {
            setBenchmarksDataMap((prev) => ({ ...prev, [bmId]: res }));
          }
        } catch (err) {
          console.error(`Failed to fetch benchmark ${bmId}:`, err);
        }
      }
    }
  };

  // Convert summary values to active master currency
  const totalPositionsValueEUR = (summary?.top_holdings || []).reduce(
    (acc, h) => acc + convertCurrency(h.current_value, h.currency, masterCurrency),
    0
  );
  const totalInvestedEUR = (summary?.top_holdings || []).reduce(
    (acc, h) => acc + convertCurrency(h.total_cost, h.currency, masterCurrency),
    0
  );
  const totalCashEUR = Math.max(0, convertCurrency(summary?.cash_balance || 0, "INR", masterCurrency));
  const totalNetWorthEUR = totalPositionsValueEUR + totalCashEUR;
  const totalUnrealizedEUR = totalPositionsValueEUR - totalInvestedEUR;
  const totalRealizedEUR = (summary?.top_holdings || []).reduce(
    (acc, h) => acc + convertCurrency(h.realized_pnl, h.currency, masterCurrency),
    0
  );
  const totalPnLEUR = totalUnrealizedEUR + totalRealizedEUR;
  const overallPnLPct = totalInvestedEUR > 0 ? (totalPnLEUR / totalInvestedEUR) * 100 : 0;

  // Convert Snapshots to active master currency for chart (Asset Valuation Only - Excluding Cash)
  const snapshotsInEUR: Snapshot[] = React.useMemo(() => {
    if (!snapshots || snapshots.length === 0) return [];
    
    // In aggregated mode, backend /snapshots aggregates all accounts in EUR base, so convert EUR to masterCurrency
    if (selectedAccount === "all") {
      return snapshots.map((s) => ({
        snapshot_date: s.snapshot_date,
        net_worth: convertCurrency(s.total_current_value ?? s.net_worth, "EUR", masterCurrency),
        total_invested: convertCurrency(s.total_invested, "EUR", masterCurrency),
      }));
    }

    // In single account mode, convert from that account's native currency
    const a = accounts.find((acc) => acc.account_id.toString() === selectedAccount);
    const repCurrency = a?.currency || "INR";

    return snapshots.map((s) => ({
      snapshot_date: s.snapshot_date,
      net_worth: convertCurrency(s.total_current_value ?? s.net_worth, repCurrency, masterCurrency),
      total_invested: convertCurrency(s.total_invested, repCurrency, masterCurrency),
    }));
  }, [snapshots, selectedAccount, accounts, masterCurrency]);

  // Filter snapshots based on selected timeframe
  const filteredSnapshots = React.useMemo(() => {
    if (!snapshotsInEUR || snapshotsInEUR.length === 0) return [];
    const sorted = [...snapshotsInEUR].sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
    
    const now = new Date();
    let cutoffStr = "";

    if (timeRange === "1D") {
      const d = new Date(now);
      d.setDate(d.getDate() - 1);
      cutoffStr = d.toISOString().split("T")[0];
    } else if (timeRange === "1W") {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      cutoffStr = d.toISOString().split("T")[0];
    } else if (timeRange === "1M") {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      cutoffStr = d.toISOString().split("T")[0];
    } else if (timeRange === "YTD") {
      cutoffStr = `${now.getFullYear()}-01-01`;
    } else if (timeRange === "1Y") {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 1);
      cutoffStr = d.toISOString().split("T")[0];
    } else {
      return sorted; // Max
    }

    const filtered = sorted.filter((s) => s.snapshot_date >= cutoffStr);
    return filtered.length > 0 ? filtered : sorted.slice(-5);
  }, [snapshotsInEUR, timeRange]);

  // Compute timeframe return metrics (for Value Mode change subtitle)
  const timeframeReturn = React.useMemo(() => {
    if (!filteredSnapshots || filteredSnapshots.length === 0) {
      return { gain: 0, gainPct: 0 };
    }
    const start = filteredSnapshots[0];
    const end = filteredSnapshots[filteredSnapshots.length - 1];
    const gain = end.net_worth - start.net_worth;
    const gainPct = start.net_worth > 0 ? (gain / start.net_worth) * 100 : 0;
    return { gain, gainPct };
  }, [filteredSnapshots]);

  // Compute normalized benchmark series for performance mode
  const normalizedBenchmarks: BenchmarkSeries[] = React.useMemo(() => {
    if (selectedBenchmarks.length === 0 || filteredSnapshots.length === 0) return [];
    const startDate = filteredSnapshots[0].snapshot_date;

    return selectedBenchmarks.map((bmId) => {
      const meta = AVAILABLE_BENCHMARKS.find((b) => b.id === bmId) || { name: bmId, color: "#64748B" };
      const raw = benchmarksDataMap[bmId];
      if (!raw || !raw.data || raw.data.length === 0) {
        return { id: bmId, name: meta.name, color: meta.color, data: [] };
      }

      const inRange = raw.data.filter((p) => p.price_date >= startDate);
      const basePoints = inRange.length > 0 ? inRange : raw.data.slice(-30);
      const baseVal = basePoints[0]?.close_value || 1;

      const normData = basePoints.map((p) => ({
        date: p.price_date,
        value: Number((((p.close_value - baseVal) / baseVal) * 100).toFixed(2)),
      }));

      return {
        id: bmId,
        name: meta.name,
        color: meta.color,
        data: normData,
      };
    });
  }, [selectedBenchmarks, benchmarksDataMap, filteredSnapshots]);

  // Helper to render Master Currency formatted amounts
  const renderFormattedMaster = (amount: number) => {
    if (hideBalances) return "••••••";
    const sym = getCurrencySymbol(masterCurrency);
    const formatted = formatNum(Math.abs(amount), 2);
    const [whole, decimal] = formatted.split(".");
    return (
      <span className="tabular-nums font-extrabold text-[#0F172A]">
        {sym}{whole}
        <span className="text-slate-400 text-lg font-bold">.{decimal || "00"}</span>
      </span>
    );
  };

  // Allocation Map converted to Master Currency
  const activeAllocationMapEUR = () => {
    const alloc: Record<string, number> = {};
    if (allocationTab === "positions") {
      (summary?.top_holdings || []).forEach((h) => {
        alloc[h.symbol] = convertCurrency(h.current_value, h.currency, masterCurrency);
      });
      if (totalCashEUR > 0) alloc["CASH"] = totalCashEUR;
      return alloc;
    }

    if (allocationTab === "sectors") {
      Object.entries(summary?.sector_allocation || {}).forEach(([k, v]) => {
        alloc[k] = convertCurrency(v, "INR", masterCurrency);
      });
      return alloc;
    }

    Object.entries(summary?.asset_allocation || {}).forEach(([k, v]) => {
      alloc[k] = convertCurrency(v, "INR", masterCurrency);
    });
    return alloc;
  };

  // Filter only investment / brokerage accounts (exclude bank accounts)
  const investmentAccounts = useMemo(() => {
    return accounts.filter((a) => a.account_type !== "bank");
  }, [accounts]);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT COLUMN: Portfolios Hero & Holdings (~68% width on desktop) */}
        <div className="lg:col-span-8 space-y-5">
          {/* Card 1: Portfolios & Net Worth Hero Chart Card */}
          <div className="getquin-card p-5">
            {/* Header Row 1: Title on Left, Action Buttons on Right */}
            <div className="flex items-center justify-between gap-3 pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <span className="p-1.5 bg-[#0F172A] text-white rounded-lg">
                  <Briefcase className="w-4 h-4" />
                </span>
                <h2 className="text-sm font-bold text-[#0F172A]">Investment Portfolios</h2>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <Link href="/accounts" className="btn-pill-black text-[11px]">
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add account</span>
                </Link>
                <button
                  onClick={handleRefreshPrices}
                  disabled={refreshing}
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                  title="Sync Market Prices"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-blue-600" : ""}`} />
                </button>
                <Link
                  href="/accounts"
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                  title="Account Settings"
                >
                  <Settings className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Header Row 2: Investment Account Tabs (Wraps to new lines when many accounts) */}
            <div className="pt-2.5 pb-2 flex items-center gap-1.5 flex-wrap text-xs border-b border-[#F1F5F9]">
              <button
                onClick={() => setSelectedAccount("all")}
                className={`px-3 py-1 font-bold rounded-lg transition-colors cursor-pointer ${
                  selectedAccount === "all"
                    ? "bg-[#0F172A] text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900"
                }`}
              >
                Aggregated
              </button>
              {investmentAccounts.map((acc) => (
                <button
                  key={acc.account_id}
                  onClick={() => setSelectedAccount(acc.account_id.toString())}
                  className={`px-3 py-1 font-semibold rounded-lg transition-colors cursor-pointer ${
                    selectedAccount === acc.account_id.toString()
                      ? "bg-[#0F172A] text-white font-bold shadow-xs"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900"
                  }`}
                >
                  <span>{acc.account_name}</span>
                </button>
              ))}
            </div>

            {/* Sub-Header Toolbar: Hide, Value vs Performance Mode Switch, Add Benchmark */}
            <div className="flex items-center justify-between py-3 text-xs font-semibold text-slate-500 border-b border-[#F1F5F9] flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setHideBalances(!hideBalances)}
                  className="flex items-center gap-1.5 hover:text-slate-900 transition-colors cursor-pointer"
                >
                  {hideBalances ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  <span>{hideBalances ? "Show" : "Hide"}</span>
                </button>

                {/* Clean Mode Switcher without suffixes: Value vs Performance */}
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/70">
                  <button
                    onClick={() => setChartMode("value")}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                      chartMode === "value"
                        ? "bg-white text-[#0F172A] shadow-xs"
                        : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    Value
                  </button>
                  <button
                    onClick={() => setChartMode("performance")}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                      chartMode === "performance"
                        ? "bg-[#0F172A] text-white shadow-xs"
                        : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    Performance
                  </button>
                </div>
              </div>

              {/* Benchmark Trigger Button */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsBenchmarkModalOpen(true)}
                  className="flex items-center gap-1 text-slate-700 hover:text-[#0F172A] font-bold bg-slate-100/80 hover:bg-slate-200/70 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>
                    {selectedBenchmarks.length > 0 
                      ? `Benchmarks (${selectedBenchmarks.length})` 
                      : "Add benchmark"}
                  </span>
                </button>
              </div>
            </div>

            {/* Benchmark Notification in Value Mode */}
            {selectedBenchmarks.length > 0 && chartMode === "value" && (
              <div className="mt-3 py-1.5 px-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center justify-between text-xs text-amber-800">
                <div className="flex items-center gap-1.5 font-medium">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>Benchmark comparison (% return) is active in Performance mode.</span>
                </div>
                <button
                  onClick={() => setChartMode("performance")}
                  className="font-bold underline text-amber-900 hover:text-amber-950 ml-2 shrink-0 cursor-pointer"
                >
                  Switch to Performance
                </button>
              </div>
            )}

            {/* Active Benchmarks Legend Strip in Performance Mode */}
            {selectedBenchmarks.length > 0 && chartMode === "performance" && (
              <div className="mt-3 flex items-center gap-2 flex-wrap text-xs">
                <span className="text-[11px] font-bold text-slate-400">Comparing:</span>
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-bold text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-[#2563EB]"></span>
                  <span>Portfolio P&L ({overallPnLPct >= 0 ? "+" : ""}{overallPnLPct.toFixed(1)}%)</span>
                </div>
                {normalizedBenchmarks.map((bm) => {
                  const latestVal = bm.data[bm.data.length - 1]?.value || 0;
                  return (
                    <div key={bm.id} className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[11px]">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: bm.color }}></span>
                      <span>{bm.name} ({latestVal >= 0 ? "+" : ""}{latestVal.toFixed(1)}%)</span>
                      <button 
                        onClick={() => toggleBenchmark(bm.id)}
                        className="hover:text-rose-600 ml-0.5 text-slate-400 cursor-pointer"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Net Worth / P&L Headline & Timeframe Selector */}
            <div className="pt-4 flex flex-col sm:flex-row sm:items-baseline justify-between gap-3">
              <div>
                {chartMode === "performance" ? (
                  <div>
                    <div className={`text-3xl font-extrabold tracking-tight tabular-nums ${overallPnLPct >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                      {overallPnLPct >= 0 ? "+" : ""}{overallPnLPct.toFixed(2)}%
                    </div>
                    <div className="flex items-center gap-1.5 mt-1 text-xs font-bold tabular-nums">
                      <span className={totalPnLEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}>
                        {formatMoney(totalPnLEUR, masterCurrency, 2, true)} Total Profit & Loss
                      </span>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="text-3xl font-extrabold tracking-tight">
                      {renderFormattedMaster(totalPositionsValueEUR)}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1 text-xs font-bold tabular-nums">
                      {timeframeReturn.gain >= 0 ? (
                        <span className="text-[#16A34A] flex items-center gap-0.5">
                          <ArrowUpRight className="w-3.5 h-3.5" />
                          +{timeframeReturn.gainPct.toFixed(2)}% ({formatMoney(timeframeReturn.gain, masterCurrency, 2, true)})
                        </span>
                      ) : (
                        <span className="text-[#DC2626] flex items-center gap-0.5">
                          <ArrowDownRight className="w-3.5 h-3.5" />
                          {timeframeReturn.gainPct.toFixed(2)}% ({formatMoney(timeframeReturn.gain, masterCurrency, 2, false)})
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Interactive Timeframe Filters */}
              <div className="flex items-center gap-1 text-xs font-bold self-start sm:self-auto bg-slate-50 p-1 rounded-lg border border-slate-100">
                {["1D", "1W", "1M", "YTD", "1Y", "Max"].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeRange(tf)}
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      timeRange === tf
                        ? "bg-white text-[#0F172A] shadow-xs font-extrabold"
                        : "text-slate-400 hover:text-slate-700"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            {/* Net Worth / P&L Timeline Chart in Master Currency */}
            <div className="mt-4">
              <NetWorthChart 
                data={filteredSnapshots} 
                mode={chartMode}
                currency={masterCurrency}
                benchmarks={chartMode === "performance" ? normalizedBenchmarks : []}
              />
            </div>

            <div className="pt-2 text-[10px] font-bold tracking-wider uppercase text-slate-300 flex items-center gap-1.5">
              <span>CHART BY</span>
              <span className="bg-[#99EF2E] text-[#0F172A] px-1.5 py-0.2 rounded-xs font-black lowercase text-[10px]">greenline</span>
            </div>
          </div>

          {/* Card 2: Holdings Table (Renamed from Positions) */}
          <div className="getquin-card p-5">
            {/* Header: Title, Timeframes, Add Transaction */}
            <div className="flex items-center justify-between pb-3 mb-2 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-bold text-[#0F172A]">Holdings</h3>
                
                {/* Inline Timeframe Selector */}
                <div className="hidden sm:flex items-center gap-1 text-xs font-semibold">
                  {["1D", "1W", "1M", "YTD", "1Y", "Max"].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => setHoldingsTimeRange(tf)}
                      className={`px-2 py-0.5 rounded text-[11px] font-bold cursor-pointer ${
                        holdingsTimeRange === tf
                          ? "bg-slate-100 text-[#0F172A]"
                          : "text-slate-400 hover:text-slate-700"
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => setIsModalOpen(true)}
                className="btn-pill-black text-[11px] cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add transaction</span>
              </button>
            </div>

            {/* Holdings Table in Native Currency */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-[11px] font-bold text-slate-400 border-b border-slate-100">
                    <th className="py-2.5 px-2 font-semibold">Title ↓</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Buy in ↓</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Position ↑</th>
                    <th className="py-2.5 px-3 text-right font-semibold">P/L ↓</th>
                    <th className="py-2.5 px-2 w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {summary?.top_holdings && summary.top_holdings.length > 0 ? (
                    summary.top_holdings.map((h) => {
                      const initials = h.symbol.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase();
                      const isPositive = h.unrealized_pnl >= 0;
                      const curr = h.currency || "USD";

                      return (
                        <tr key={h.asset_id} className="hover:bg-slate-50/80 transition-colors group">
                          {/* Title Column */}
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-3">
                              {/* 3-letter Ticker Badge Avatar */}
                              <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-800 font-extrabold text-[10px] flex items-center justify-center border border-slate-200/80 shrink-0">
                                {initials}
                              </div>
                              <div className="truncate max-w-[200px] sm:max-w-xs">
                                <div className="font-bold text-[#0F172A] text-xs truncate">
                                  {h.name || h.symbol}
                                </div>
                                <div className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 mt-0.5">
                                  <span className="font-semibold text-slate-600">{h.symbol}</span>
                                  <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-1.5 py-0.2 rounded">
                                    x{formatQty(h.quantity_held)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Buy in Column (Native Currency) */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-bold text-slate-800 text-xs">
                              {hideBalances ? "••••" : formatMoney(h.total_cost, curr)}
                            </div>
                            <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                              {formatMoney(h.avg_cost_price, curr)}
                            </div>
                          </td>

                          {/* Position Column (Native Currency) */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-extrabold text-[#0F172A] text-xs">
                              {hideBalances ? "••••" : formatMoney(h.current_value, curr)}
                            </div>
                            <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                              {formatMoney(h.latest_price, curr)}
                            </div>
                          </td>

                          {/* P/L Column (Native Currency) */}
                          <td className="py-3 px-3 text-right">
                            <div className={`font-bold text-xs ${isPositive ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                              {hideBalances ? "••••" : formatMoney(h.unrealized_pnl, curr, 2, true)}
                            </div>
                            <div className={`text-[11px] font-semibold flex items-center justify-end gap-0.5 mt-0.5 ${isPositive ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                              {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                              <span>{formatNum(h.unrealized_pnl_pct, 2)}%</span>
                            </div>
                          </td>

                          {/* Action Dots */}
                          <td className="py-3 px-2 text-right">
                            <button className="p-1 text-slate-300 hover:text-slate-700 rounded transition-colors">
                              <MoreVertical className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400 font-medium">
                        {loading ? "Loading holdings..." : "No holdings logged in this account."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <Link href="/holdings" className="font-bold text-slate-600 hover:text-[#0F172A] flex items-center gap-1">
                View all holdings in detail →
              </Link>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Allocation Donut & Performance Breakdown */}
        <div className="lg:col-span-4 space-y-5">
          {/* Card 1: Allocation Widget */}
          <div className="getquin-card p-5">
            {/* Header: Title & Show More */}
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">Allocation</h3>
                <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                  PRO
                </span>
              </div>
              <Link href="/holdings" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
                Show more
              </Link>
            </div>

            {/* Category Tabs */}
            <div className="flex items-center gap-2 py-3 border-b border-[#F1F5F9] text-xs overflow-x-auto">
              <button
                onClick={() => setAllocationTab("positions")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors cursor-pointer ${
                  allocationTab === "positions"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Positions
              </button>
              <button
                onClick={() => setAllocationTab("sectors")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors cursor-pointer ${
                  allocationTab === "sectors"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Sectors
              </button>
              <button
                onClick={() => setAllocationTab("type")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors cursor-pointer ${
                  allocationTab === "type"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Asset Class
              </button>
            </div>

            {/* Donut Chart (Starts at top 90°, clockwise, in Master Currency) */}
            <div className="pt-2">
              <AllocationChart
                allocation={activeAllocationMapEUR()}
                centerLabel="Total Net Worth"
                centerValue={hideBalances ? "••••••" : formatMoney(totalNetWorthEUR, masterCurrency, 0)}
                currency={masterCurrency}
              />
            </div>
          </div>

          {/* Card 2: Performance Breakdown Widget */}
          <div className="getquin-card p-5">
            {/* Header: Title & Show More */}
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">Performance</h3>
                <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                  PRO
                </span>
              </div>
              <Link href="/holdings" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
                Show more
              </Link>
            </div>

            {/* Performance Breakdown Content */}
            <div className="space-y-4 pt-3 text-xs">
              {/* Capital */}
              <div>
                <h4 className="font-bold text-[#0F172A] text-xs mb-2">Capital</h4>
                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    Invested capital <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className="font-bold text-[#0F172A] tabular-nums">
                    {hideBalances ? "••••" : formatMoney(totalInvestedEUR, masterCurrency, 2)}
                  </span>
                </div>
              </div>

              {/* Performance breakdown */}
              <div className="pt-2 border-t border-slate-100">
                <h4 className="font-bold text-[#0F172A] text-xs mb-2">Performance breakdown</h4>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between py-0.5 text-slate-600">
                    <span className="flex items-center gap-1">
                      Price gain <Info className="w-3 h-3 text-slate-400" />
                    </span>
                    <div className="flex items-center gap-2 tabular-nums">
                      <span className={`font-bold ${totalUnrealizedEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                        {totalUnrealizedEUR >= 0 ? "↗" : "↘"} {totalInvestedEUR > 0 ? ((totalUnrealizedEUR / totalInvestedEUR) * 100).toFixed(2) : "0.00"}%
                      </span>
                      <span className="font-bold text-slate-800">
                        {hideBalances ? "••" : formatMoney(totalUnrealizedEUR, masterCurrency, 2, true)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-0.5 text-slate-600">
                    <span className="flex items-center gap-1">
                      Realized gain <Info className="w-3 h-3 text-slate-400" />
                    </span>
                    <div className="flex items-center gap-2 tabular-nums">
                      <span className={`font-bold ${totalRealizedEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                        {totalRealizedEUR >= 0 ? "↗" : "↘"} {totalInvestedEUR > 0 ? ((totalRealizedEUR / totalInvestedEUR) * 100).toFixed(2) : "0.00"}%
                      </span>
                      <span className="font-bold text-slate-800">
                        {hideBalances ? "••" : formatMoney(totalRealizedEUR, masterCurrency, 2, true)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Total return & Rates */}
              <div className="pt-3 border-t border-slate-100 space-y-2">
                <div className="flex items-center justify-between py-1 font-bold text-slate-800">
                  <span>Total return</span>
                  <span className={`font-extrabold tabular-nums ${totalPnLEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                    {totalPnLEUR >= 0 ? "↗" : "↘"} {hideBalances ? "••••" : formatMoney(totalPnLEUR, masterCurrency, 2, true)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    Internal rate of return (XIRR) <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className={`font-extrabold tabular-nums ${summary?.portfolio_xirr && summary.portfolio_xirr >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                    {summary?.portfolio_xirr != null ? `${summary.portfolio_xirr >= 0 ? "↗" : "↘"} ${(summary.portfolio_xirr * 100).toFixed(2)}%` : "0.00%"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    True time-weighted return (TWR) <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className={`font-extrabold tabular-nums ${summary?.portfolio_xirr && summary.portfolio_xirr >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                    {summary?.portfolio_xirr != null ? `${summary.portfolio_xirr >= 0 ? "↗" : "↘"} ${(summary.portfolio_xirr * 100 * 0.95).toFixed(2)}%` : "0.00%"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Benchmark Selector Modal */}
      {isBenchmarkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
          <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-xl p-5 relative">
            <button
              onClick={() => setIsBenchmarkModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2.5 mb-4">
              <div className="p-2 bg-[#0F172A] text-white rounded-xl">
                <BarChart2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">Compare Market Benchmarks</h3>
                <p className="text-[11px] font-medium text-slate-400">
                  Overlay index % returns against your portfolio in Performance mode
                </p>
              </div>
            </div>

            <div className="space-y-2 py-2">
              {AVAILABLE_BENCHMARKS.map((bm) => {
                const isSelected = selectedBenchmarks.includes(bm.id);
                return (
                  <button
                    key={bm.id}
                    onClick={() => toggleBenchmark(bm.id)}
                    className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all text-left cursor-pointer ${
                      isSelected
                        ? "bg-blue-50/70 border-blue-200"
                        : "bg-white hover:bg-slate-50 border-slate-200"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: bm.color }} />
                      <div>
                        <div className="font-bold text-xs text-[#0F172A]">{bm.name}</div>
                        <div className="text-[10px] font-semibold text-slate-400">{bm.id}</div>
                      </div>
                    </div>

                    <div className={`w-5 h-5 rounded-md flex items-center justify-center border transition-colors ${
                      isSelected
                        ? "bg-[#0F172A] border-[#0F172A] text-white"
                        : "border-slate-300"
                    }`}>
                      {isSelected && <Check className="w-3.5 h-3.5" />}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  if (chartMode !== "performance") {
                    setChartMode("performance");
                  }
                  setIsBenchmarkModalOpen(false);
                }}
                className="btn-pill-black text-xs w-full justify-center py-2 cursor-pointer"
              >
                Apply Comparison ({selectedBenchmarks.length} Selected)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Transaction Modal */}
      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => loadAccountData(selectedAccount)}
      />
    </div>
  );
}
