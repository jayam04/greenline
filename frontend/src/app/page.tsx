"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  formatNum, formatMoney, getCurrencySymbol, 
  convertCurrency, convertCurrencyToEUR 
} from "@/lib/format";
import { NetWorthChart, BenchmarkSeries } from "@/components/NetWorthChart";
import { AllocationChart } from "@/components/AllocationChart";
import { 
  TrendingUp, Wallet, Landmark, Building2, Coins, Briefcase, Plus, 
  ArrowUpRight, ArrowDownRight, Eye, EyeOff, RefreshCw, Settings, 
  Calendar, DollarSign, Check, Layers, ExternalLink, ShieldCheck, 
  BarChart2, AlertCircle, ArrowLeftRight, PiggyBank, Receipt, ChevronRight,
  ArrowRight
} from "lucide-react";
import Link from "next/link";

interface Account {
  account_id: number;
  account_name: string;
  broker_name?: string;
  account_type: string;
  currency: string;
  current_balance?: number;
  created_at?: string;
}

interface HoldingSummary {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  quantity_held: number;
  total_cost: number;
  current_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
}

interface PortfolioSummary {
  net_worth: number;
  total_cost: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  total_net_worth: number;
  total_invested: number;
  total_current_value: number;
  cash_balance: number;
  top_holdings: HoldingSummary[];
  asset_allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  portfolio_xirr?: number | null;
}

interface Snapshot {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
}

interface AnnualSnapshot {
  year_label: string;
  start_date: string;
  end_date: string;
  total_income: number;
  total_expenses: number;
  investments_done: number;
  investments_closed: number;
  net_worth_delta: number;
  net_worth_delta_pct: number;
  taxes_and_fees: number;
  net_savings: number;
  currency: string;
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

export default function NetWorthDashboardPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [annualSnapshot, setAnnualSnapshot] = useState<AnnualSnapshot | null>(null);
  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");
  const [fiscalYearStart, setFiscalYearStart] = useState<string>("01-01");
  
  const [selectedAccount, setSelectedAccount] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("YTD");
  const [chartMode, setChartMode] = useState<"value" | "performance">("value");
  const [accountTypeFilter, setAccountTypeFilter] = useState<"all" | "bank" | "demat">("all");
  const [hideBalances, setHideBalances] = useState(false);
  const [isBenchmarkModalOpen, setIsBenchmarkModalOpen] = useState(false);
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([]);
  const [benchmarksDataMap, setBenchmarksDataMap] = useState<Record<string, BenchmarkRawData>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadSettingsAndAccounts();
  }, []);

  useEffect(() => {
    loadData(selectedAccount, fiscalYearStart, masterCurrency);
  }, [selectedAccount, fiscalYearStart, masterCurrency]);

  const loadSettingsAndAccounts = async () => {
    try {
      const [settingsRes, accRes] = await Promise.all([
        apiFetch<{ master_currency?: string; fiscal_year_start?: string }>("/settings").catch(() => null),
        apiFetch<Account[]>("/accounts").catch(() => []),
      ]);

      if (settingsRes) {
        if (settingsRes.master_currency) {
          const curr = settingsRes.master_currency.trim().toUpperCase();
          setMasterCurrency(curr);
        }
        if (settingsRes.fiscal_year_start) {
          setFiscalYearStart(settingsRes.fiscal_year_start.trim());
        }
      }

      setAccounts(accRes || []);
    } catch (e) {
      console.error(e);
    }
  };

  const loadData = async (accId: string, fyStart: string, mCurr: string) => {
    try {
      setLoading(true);
      const queryParam = accId === "all" ? "" : `?account_id=${accId}`;
      const annualQuery = `?fiscal_year_start=${fyStart}&master_currency=${mCurr}`;

      const [sumData, snapData, annualData, accData] = await Promise.all([
        apiFetch<PortfolioSummary>(`/portfolio/summary${queryParam}`),
        apiFetch<Snapshot[]>(`/snapshots${queryParam}`),
        apiFetch<AnnualSnapshot>(`/portfolio/annual_snapshot${annualQuery}`),
        apiFetch<Account[]>("/accounts"),
      ]);

      setSummary(sumData);
      setSnapshots(snapData || []);
      setAnnualSnapshot(annualData);
      if (accData) setAccounts(accData);
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
      await loadData(selectedAccount, fiscalYearStart, masterCurrency);
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  // Toggle benchmark selection
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

  // 1. Calculate Bank Balances & Securities Valuation in Master Currency
  const bankAccounts = useMemo(() => accounts.filter((a) => a.account_type === "bank"), [accounts]);
  const dematAccounts = useMemo(() => accounts.filter((a) => a.account_type !== "bank"), [accounts]);

  // Total Cash in Bank/Wallet accounts converted to masterCurrency
  const totalBankCashMaster = useMemo(() => {
    return bankAccounts.reduce((acc, a) => {
      const bal = a.current_balance || 0;
      return acc + convertCurrency(bal, a.currency || "EUR", masterCurrency);
    }, 0);
  }, [bankAccounts, masterCurrency]);

  // Total Stocks & Securities valuation in masterCurrency
  const totalStocksValuationMaster = useMemo(() => {
    return (summary?.top_holdings || []).reduce((acc, h) => {
      return acc + convertCurrency(h.current_value, h.currency || "USD", masterCurrency);
    }, 0);
  }, [summary, masterCurrency]);

  // Total Demat cash (if any uninvested cash in demat accounts)
  const totalDematCashMaster = useMemo(() => {
    return dematAccounts.reduce((acc, a) => {
      const bal = Math.max(0, a.current_balance || 0);
      return acc + convertCurrency(bal, a.currency || "INR", masterCurrency);
    }, 0);
  }, [dematAccounts, masterCurrency]);

  // Global Total Net Worth
  const totalNetWorthMaster = totalBankCashMaster + totalStocksValuationMaster + totalDematCashMaster;
  const totalCashMaster = totalBankCashMaster + totalDematCashMaster;

  // Percentage splits
  const stockSharePct = totalNetWorthMaster > 0 ? (totalStocksValuationMaster / totalNetWorthMaster) * 100 : 0;
  const cashSharePct = totalNetWorthMaster > 0 ? (totalCashMaster / totalNetWorthMaster) * 100 : 0;

  // Convert Snapshots to active master currency for chart
  const snapshotsInMaster: Snapshot[] = useMemo(() => {
    if (!snapshots || snapshots.length === 0) return [];
    
    if (selectedAccount === "all") {
      return snapshots.map((s) => ({
        snapshot_date: s.snapshot_date,
        net_worth: convertCurrency(s.net_worth, "EUR", masterCurrency) + totalBankCashMaster,
        total_invested: convertCurrency(s.total_invested, "EUR", masterCurrency),
      }));
    }

    const a = accounts.find((acc) => acc.account_id.toString() === selectedAccount);
    const repCurrency = a?.currency || "INR";

    return snapshots.map((s) => ({
      snapshot_date: s.snapshot_date,
      net_worth: convertCurrency(s.net_worth, repCurrency, masterCurrency),
      total_invested: convertCurrency(s.total_invested, repCurrency, masterCurrency),
    }));
  }, [snapshots, selectedAccount, accounts, masterCurrency, totalBankCashMaster]);

  // Filter snapshots based on selected timeframe
  const filteredSnapshots = useMemo(() => {
    if (!snapshotsInMaster || snapshotsInMaster.length === 0) return [];
    const sorted = [...snapshotsInMaster].sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
    
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
  }, [snapshotsInMaster, timeRange]);

  // Timeframe return
  const timeframeReturn = useMemo(() => {
    if (!filteredSnapshots || filteredSnapshots.length === 0) {
      return { gain: 0, gainPct: 0 };
    }
    const start = filteredSnapshots[0];
    const end = filteredSnapshots[filteredSnapshots.length - 1];
    const gain = end.net_worth - start.net_worth;
    const gainPct = start.net_worth > 0 ? (gain / start.net_worth) * 100 : 0;
    return { gain, gainPct };
  }, [filteredSnapshots]);

  // Normalized benchmarks
  const normalizedBenchmarks: BenchmarkSeries[] = useMemo(() => {
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

  // Helper to render Master Currency formatted headline
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

  // 2. Entities Net Worth Map for Donut Chart
  const entitiesAllocationMap = useMemo(() => {
    const map: Record<string, number> = {};
    if (totalCashMaster > 0) {
      map["Cash & Bank Accounts"] = totalCashMaster;
    }
    if (totalStocksValuationMaster > 0) {
      map["Stocks & ETFs (Securities)"] = totalStocksValuationMaster;
    }
    return map;
  }, [totalCashMaster, totalStocksValuationMaster]);

  // Filtered accounts list for the table
  const filteredAccounts = useMemo(() => {
    if (accountTypeFilter === "bank") return bankAccounts;
    if (accountTypeFilter === "demat") return dematAccounts;
    return accounts;
  }, [accounts, bankAccounts, dematAccounts, accountTypeFilter]);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT COLUMN: Net Worth Hero & Accounts/Balances Table (~68% width) */}
        <div className="lg:col-span-8 space-y-5">
          {/* Card 1: Global Net Worth Hero Card */}
          <div className="getquin-card p-5">
            {/* Header: Title, Account Tabs, Action Buttons */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 bg-[#0F172A] text-white rounded-lg">
                    <TrendingUp className="w-4 h-4" />
                  </span>
                  <h2 className="text-sm font-bold text-[#0F172A]">Full Net Worth</h2>
                </div>
                
                {/* Account Tabs */}
                <div className="flex items-center gap-1 overflow-x-auto text-xs">
                  <button
                    onClick={() => setSelectedAccount("all")}
                    className={`px-3 py-1 font-bold rounded-lg transition-colors cursor-pointer ${
                      selectedAccount === "all"
                        ? "text-[#0F172A] border-b-2 border-[#0F172A] rounded-b-none"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    Aggregated
                  </button>
                  {accounts.map((acc) => (
                    <button
                      key={acc.account_id}
                      onClick={() => setSelectedAccount(acc.account_id.toString())}
                      className={`px-2.5 py-1 font-semibold rounded-lg transition-colors whitespace-nowrap cursor-pointer flex items-center gap-1.5 ${
                        selectedAccount === acc.account_id.toString()
                          ? "text-[#0F172A] border-b-2 border-[#0F172A] rounded-b-none font-bold"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      <span>{acc.account_name}</span>
                      <span className="text-[9px] font-bold uppercase px-1 rounded bg-slate-100 text-slate-500">
                        {acc.account_type === "bank" ? "Bank" : "Demat"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 self-end sm:self-auto">
                <Link href="/accounts" className="btn-pill-black text-[11px]">
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add account</span>
                </Link>
                <button
                  onClick={handleRefreshPrices}
                  disabled={refreshing}
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                  title="Sync Market Prices"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-blue-600" : ""}`} />
                </button>
                <Link
                  href="/settings"
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                  title="App Settings"
                >
                  <Settings className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Sub-Header Toolbar */}
            <div className="flex items-center justify-between py-3 text-xs font-semibold text-slate-500 border-b border-[#F1F5F9] flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setHideBalances(!hideBalances)}
                  className="flex items-center gap-1.5 hover:text-slate-900 transition-colors cursor-pointer"
                >
                  {hideBalances ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  <span>{hideBalances ? "Show" : "Hide"}</span>
                </button>

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

            {/* Headline Valuation */}
            <div className="pt-4 flex flex-col sm:flex-row sm:items-baseline justify-between gap-3">
              <div>
                <div className="text-3xl font-extrabold tracking-tight">
                  {renderFormattedMaster(totalNetWorthMaster)}
                </div>
                
                {/* Timeframe Return / Change */}
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
                  <span className="text-slate-400 font-semibold">• {timeRange} Baseline</span>
                </div>

                {/* Primary Entity Summary Strip */}
                <div className="flex items-center gap-3 mt-2 text-xs font-bold flex-wrap">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-800 border border-blue-100">
                    <Briefcase className="w-3.5 h-3.5 text-blue-600" />
                    <span>Stocks & ETFs:</span>
                    <span className="font-extrabold tabular-nums">
                      {hideBalances ? "••••" : formatMoney(totalStocksValuationMaster, masterCurrency, 0)} ({stockSharePct.toFixed(1)}%)
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-100">
                    <Landmark className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Cash & Banks:</span>
                    <span className="font-extrabold tabular-nums">
                      {hideBalances ? "••••" : formatMoney(totalCashMaster, masterCurrency, 0)} ({cashSharePct.toFixed(1)}%)
                    </span>
                  </div>
                </div>
              </div>

              {/* Timeframe Filters */}
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

            {/* Timeline Chart */}
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

          {/* Card 2: Accounts & Balances Table (Replaced Holdings) */}
          <div className="getquin-card p-5">
            {/* Header: Title, Type Tabs, Action Button */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-2 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4 flex-wrap">
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Accounts & Balances</h3>
                  <p className="text-[11px] font-medium text-slate-400">
                    Live balance across all bank accounts, wallets, and investment brokers
                  </p>
                </div>

                {/* Account Type Filter Pills */}
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/70 text-xs">
                  <button
                    onClick={() => setAccountTypeFilter("all")}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                      accountTypeFilter === "all" ? "bg-white text-[#0F172A] shadow-xs" : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    All ({accounts.length})
                  </button>
                  <button
                    onClick={() => setAccountTypeFilter("bank")}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                      accountTypeFilter === "bank" ? "bg-white text-[#0F172A] shadow-xs" : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    Bank & Cash ({bankAccounts.length})
                  </button>
                  <button
                    onClick={() => setAccountTypeFilter("demat")}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                      accountTypeFilter === "demat" ? "bg-white text-[#0F172A] shadow-xs" : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    Brokerage ({dematAccounts.length})
                  </button>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <Link
                  href="/cashflow"
                  className="btn-pill-black text-[11px] cursor-pointer"
                >
                  <ArrowLeftRight className="w-3.5 h-3.5" />
                  <span>Record Spend / Income</span>
                </Link>
                <Link
                  href="/accounts"
                  className="px-2.5 py-1 text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 font-bold rounded-lg text-xs transition-colors flex items-center gap-1"
                >
                  <Building2 className="w-3.5 h-3.5" />
                  <span>Manage</span>
                </Link>
              </div>
            </div>

            {/* Accounts Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-[11px] font-bold text-slate-400 border-b border-slate-100">
                    <th className="py-2.5 px-2 font-semibold">Account & Institution</th>
                    <th className="py-2.5 px-3 font-semibold">Entity Type</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Native Balance</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Valuation ({masterCurrency})</th>
                    <th className="py-2.5 px-3 text-right font-semibold">% Net Worth</th>
                    <th className="py-2.5 px-2 w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {filteredAccounts.length > 0 ? (
                    filteredAccounts.map((acc) => {
                      const isBank = acc.account_type === "bank";
                      const nativeBal = acc.current_balance || 0;
                      const masterBal = convertCurrency(nativeBal, acc.currency || "EUR", masterCurrency);
                      const sharePct = totalNetWorthMaster > 0 ? (masterBal / totalNetWorthMaster) * 100 : 0;

                      return (
                        <tr key={acc.account_id} className="hover:bg-slate-50/80 transition-colors group">
                          {/* Account & Institution */}
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-3">
                              <div className={`w-8 h-8 rounded-lg font-extrabold text-[10px] flex items-center justify-center border shrink-0 ${
                                isBank 
                                  ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                                  : "bg-blue-50 text-blue-800 border-blue-200"
                              }`}>
                                {isBank ? <Landmark className="w-4 h-4" /> : <Building2 className="w-4 h-4" />}
                              </div>
                              <div className="truncate max-w-[200px] sm:max-w-xs">
                                <div className="font-bold text-[#0F172A] text-xs truncate">
                                  {acc.account_name}
                                </div>
                                <div className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 mt-0.5">
                                  <span>{acc.broker_name || (isBank ? "Bank / Cash" : "Broker")}</span>
                                  <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-1.5 py-0.2 rounded">
                                    {acc.currency}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Entity Type Badge */}
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 text-[10px] font-extrabold uppercase rounded ${
                              isBank 
                                ? "bg-emerald-100 text-emerald-800" 
                                : "bg-blue-100 text-blue-800"
                            }`}>
                              {isBank ? "Cash & Bank" : "Securities & Stocks"}
                            </span>
                          </td>

                          {/* Native Balance */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-bold text-slate-800 text-xs">
                              {hideBalances ? "••••" : formatMoney(nativeBal, acc.currency || "EUR", 2)}
                            </div>
                            <div className="text-[10px] font-medium text-slate-400">
                              {acc.currency}
                            </div>
                          </td>

                          {/* Valuation in Master Currency */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-extrabold text-[#0F172A] text-xs">
                              {hideBalances ? "••••" : formatMoney(masterBal, masterCurrency, 2)}
                            </div>
                          </td>

                          {/* Share of Net Worth */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-bold text-xs text-slate-700">
                              {sharePct.toFixed(1)}%
                            </div>
                            <div className="w-16 h-1.5 bg-slate-100 rounded-full ml-auto mt-1 overflow-hidden">
                              <div 
                                className={`h-full rounded-full ${isBank ? "bg-emerald-500" : "bg-blue-500"}`}
                                style={{ width: `${Math.min(100, Math.max(0, sharePct))}%` }}
                              />
                            </div>
                          </td>

                          {/* Action Link */}
                          <td className="py-3 px-2 text-right">
                            <Link 
                              href={isBank ? "/cashflow" : "/investments"}
                              className="p-1 text-slate-400 hover:text-[#0F172A] rounded transition-colors inline-block"
                              title={isBank ? "View in Cashflow" : "View in Investments"}
                            >
                              <ChevronRight className="w-4 h-4" />
                            </Link>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400 font-medium">
                        {loading ? "Loading accounts..." : "No accounts found."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <Link href="/accounts" className="font-bold text-slate-600 hover:text-[#0F172A] flex items-center gap-1">
                Configure accounts & brokers in Accounts Master →
              </Link>
              <Link href="/investments" className="font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1">
                Open Full Investment Portfolio Dashboard →
              </Link>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Net Worth Across Entities Donut & Full Year Snapshot (~32% width) */}
        <div className="lg:col-span-4 space-y-5">
          {/* Card 1: Net Worth Across Entities Donut Chart (Replaced Allocation) */}
          <div className="getquin-card p-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">Net Worth Across Entities</h3>
                <span className="text-[9px] font-extrabold uppercase bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">
                  ASSETS
                </span>
              </div>
              <Link href="/investments" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
                Holdings
              </Link>
            </div>

            {/* Donut Chart */}
            <div className="pt-3">
              <AllocationChart
                allocation={entitiesAllocationMap}
                centerLabel="Total Net Worth"
                centerValue={hideBalances ? "••••••" : formatMoney(totalNetWorthMaster, masterCurrency, 0)}
                currency={masterCurrency}
              />
            </div>

            {/* Entities Breakdown Summary */}
            <div className="space-y-2 pt-3 border-t border-slate-100 text-xs">
              <div className="flex items-center justify-between py-1 text-slate-700">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
                  <span className="font-bold">Stocks & ETFs</span>
                </div>
                <div className="font-extrabold tabular-nums text-[#0F172A]">
                  {hideBalances ? "••••" : formatMoney(totalStocksValuationMaster, masterCurrency, 0)} ({stockSharePct.toFixed(1)}%)
                </div>
              </div>

              <div className="flex items-center justify-between py-1 text-slate-700">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]" />
                  <span className="font-bold">Cash & Bank Accounts</span>
                </div>
                <div className="font-extrabold tabular-nums text-[#0F172A]">
                  {hideBalances ? "••••" : formatMoney(totalCashMaster, masterCurrency, 0)} ({cashSharePct.toFixed(1)}%)
                </div>
              </div>

              <div className="flex items-center justify-between py-1 text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-300" />
                  <span>Precious Metals / Real Estate</span>
                </div>
                <span className="text-[10px] font-semibold uppercase bg-slate-100 text-slate-500 px-1 py-0.2 rounded">
                  Extensible
                </span>
              </div>
            </div>
          </div>

          {/* Card 2: Full Year Snapshot (Replaced Performance) */}
          <div className="getquin-card p-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-bold text-[#0F172A]">
                  {annualSnapshot?.year_label || "Annual"} Snapshot
                </h3>
              </div>
              <Link href="/settings" className="text-xs font-semibold text-slate-500 hover:text-slate-900" title="Change Year Start Date">
                Settings
              </Link>
            </div>

            <div className="pt-2 text-[11px] font-medium text-slate-400 mb-3 flex items-center justify-between">
              <span>Baseline: {annualSnapshot?.start_date || "Year start"} – Present</span>
              <span className="font-bold text-purple-700 bg-purple-50 px-1.5 py-0.2 rounded text-[10px]">
                {fiscalYearStart} Start
              </span>
            </div>

            {/* Annual Snapshot Metrics List */}
            <div className="space-y-3 text-xs">
              {/* Income */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600 flex items-center gap-1.5">
                  <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
                  Total Income (Inflow)
                </span>
                <span className="font-extrabold text-emerald-700 tabular-nums">
                  {hideBalances ? "••••" : `+${formatMoney(annualSnapshot?.total_income || 0, masterCurrency, 2)}`}
                </span>
              </div>

              {/* Expense */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600 flex items-center gap-1.5">
                  <ArrowDownRight className="w-3.5 h-3.5 text-rose-600" />
                  Total Expenses (Outflow)
                </span>
                <span className="font-extrabold text-rose-700 tabular-nums">
                  {hideBalances ? "••••" : `-${formatMoney(annualSnapshot?.total_expenses || 0, masterCurrency, 2)}`}
                </span>
              </div>

              {/* Net Retained Cash / Savings */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600 flex items-center gap-1.5">
                  <PiggyBank className="w-3.5 h-3.5 text-blue-600" />
                  Net Retained Savings
                </span>
                <span className={`font-extrabold tabular-nums ${
                  (annualSnapshot?.net_savings || 0) >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"
                }`}>
                  {hideBalances ? "••••" : formatMoney(annualSnapshot?.net_savings || 0, masterCurrency, 2, true)}
                </span>
              </div>

              {/* Investments Done */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600 flex items-center gap-1.5">
                  <Briefcase className="w-3.5 h-3.5 text-slate-500" />
                  Investments Done (Capital)
                </span>
                <span className="font-bold text-slate-800 tabular-nums">
                  {hideBalances ? "••••" : formatMoney(annualSnapshot?.investments_done || 0, masterCurrency, 2)}
                </span>
              </div>

              {/* Investments Closed */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600 flex items-center gap-1.5">
                  <Receipt className="w-3.5 h-3.5 text-slate-500" />
                  Investments Closed
                </span>
                <span className="font-bold text-slate-800 tabular-nums">
                  {hideBalances ? "••••" : formatMoney(annualSnapshot?.investments_closed || 0, masterCurrency, 2)}
                </span>
              </div>

              {/* Taxes & Fees */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-600">Taxes & Fees Incurred</span>
                <span className="font-bold text-slate-700 tabular-nums">
                  {hideBalances ? "••••" : formatMoney(annualSnapshot?.taxes_and_fees || 0, masterCurrency, 2)}
                </span>
              </div>

              {/* Net Worth Change */}
              <div className="pt-2 flex items-center justify-between text-xs">
                <span className="font-bold text-[#0F172A]">Change in Net Worth</span>
                <div className="text-right">
                  <div className={`font-extrabold text-sm tabular-nums ${
                    (annualSnapshot?.net_worth_delta || 0) >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"
                  }`}>
                    {(annualSnapshot?.net_worth_delta || 0) >= 0 ? "+" : ""}
                    {hideBalances ? "••••" : formatMoney(annualSnapshot?.net_worth_delta || 0, masterCurrency, 2)}
                  </div>
                  <div className={`text-[10px] font-bold ${
                    (annualSnapshot?.net_worth_delta_pct || 0) >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"
                  }`}>
                    {(annualSnapshot?.net_worth_delta_pct || 0) >= 0 ? "+" : ""}
                    {(annualSnapshot?.net_worth_delta_pct || 0).toFixed(2)}%
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100">
              <Link 
                href="/cashflow"
                className="w-full py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>View Complete Cashflow & Sankey</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
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
    </div>
  );
}
