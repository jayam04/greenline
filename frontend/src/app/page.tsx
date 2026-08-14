"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney } from "@/lib/format";
import { NetWorthChart } from "@/components/NetWorthChart";
import { AllocationChart } from "@/components/AllocationChart";
import { TransactionModal } from "@/components/TransactionModal";
import { 
  Plus, Eye, EyeOff, ArrowUpDown, Info, MoreVertical, 
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Settings, Share2, RefreshCw
} from "lucide-react";
import Link from "next/link";

interface HoldingSummary {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  sector?: string;
  currency: string;
  quantity_held: number;
  avg_cost_price: number;
  total_cost: number;
  latest_price: number;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  xirr: number | null;
}

interface PortfolioSummary {
  total_net_worth: number;
  total_invested: number;
  total_current_value: number;
  cash_balance: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  portfolio_xirr: number | null;
  asset_allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  top_holdings: HoldingSummary[];
}

interface Snapshot {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
}

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("YTD");
  const [positionsTimeRange, setPositionsTimeRange] = useState<string>("Max");
  const [allocationTab, setAllocationTab] = useState<"positions" | "sectors" | "type">("positions");
  const [hideBalances, setHideBalances] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [sumData, snapData, accData] = await Promise.all([
        apiFetch<PortfolioSummary>("/portfolio/summary"),
        apiFetch<Snapshot[]>("/snapshots"),
        apiFetch<Account[]>("/accounts"),
      ]);
      setSummary(sumData);
      setSnapshots(snapData);
      setAccounts(accData);
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
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  // Helper to format currency values cleanly with split decimals
  const renderFormattedAmount = (amount: number, prefix: string = "$") => {
    if (hideBalances) return "••••••";
    const formatted = formatNum(Math.abs(amount), 2);
    const [whole, decimal] = formatted.split(".");
    return (
      <span className="tabular-nums font-extrabold text-[#0F172A]">
        {prefix}{whole}
        <span className="text-slate-400 text-lg font-bold">.{decimal || "00"}</span>
      </span>
    );
  };

  // Compute position allocation dictionary
  const getPositionAllocation = () => {
    const alloc: Record<string, number> = {};
    if (summary?.top_holdings) {
      summary.top_holdings.forEach((h) => {
        alloc[h.symbol] = h.current_value;
      });
    }
    if (summary?.cash_balance && summary.cash_balance > 0) {
      alloc["CASH"] = summary.cash_balance;
    }
    return alloc;
  };

  const activeAllocationMap = () => {
    if (allocationTab === "positions") return getPositionAllocation();
    if (allocationTab === "sectors") return summary?.sector_allocation || {};
    return summary?.asset_allocation || {};
  };

  const totalPnL = (summary?.total_unrealized_pnl || 0) + (summary?.total_realized_pnl || 0);
  const totalReturnPct = summary && summary.total_invested > 0 ? (totalPnL / summary.total_invested) * 100 : 0;

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT COLUMN: Portfolios Hero & Positions (~68% width on desktop) */}
        <div className="lg:col-span-8 space-y-5">
          {/* Card 1: Portfolios & Net Worth Hero Chart Card */}
          <div className="getquin-card p-5">
            {/* Header: Title, Account Tabs, Add Account */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4 flex-wrap">
                <h2 className="text-sm font-bold text-[#0F172A]">Portfolios</h2>
                
                {/* Account Tabs */}
                <div className="flex items-center gap-1 overflow-x-auto text-xs">
                  <button
                    onClick={() => setSelectedAccount("all")}
                    className={`px-3 py-1 font-bold rounded-lg transition-colors ${
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
                      className={`px-3 py-1 font-semibold rounded-lg transition-colors whitespace-nowrap ${
                        selectedAccount === acc.account_id.toString()
                          ? "text-[#0F172A] border-b-2 border-[#0F172A] rounded-b-none font-bold"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      {acc.account_name}
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
                  href="/accounts"
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                  title="Account Settings"
                >
                  <Settings className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Sub-Header Toolbar: Hide, Performance, Add Benchmark */}
            <div className="flex items-center justify-between py-3 text-xs font-semibold text-slate-500 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setHideBalances(!hideBalances)}
                  className="flex items-center gap-1.5 hover:text-slate-900 transition-colors"
                >
                  {hideBalances ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  <span>{hideBalances ? "Show" : "Hide"}</span>
                </button>
                <div className="flex items-center gap-1 text-slate-700 font-bold">
                  <ArrowUpDown className="w-3.5 h-3.5" />
                  <span>Performance</span>
                  <Info className="w-3 h-3 text-slate-400" />
                </div>
              </div>

              <Link
                href="/analytics"
                className="flex items-center gap-1 hover:text-slate-900 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add benchmark</span>
              </Link>
            </div>

            {/* Net Worth Headline & Timeframe Selector */}
            <div className="pt-4 flex flex-col sm:flex-row sm:items-baseline justify-between gap-3">
              <div>
                <div className="text-3xl font-extrabold tracking-tight">
                  {renderFormattedAmount(summary?.total_net_worth || 0)}
                </div>
                <div className="flex items-center gap-1.5 mt-1 text-xs font-bold tabular-nums">
                  {totalPnL >= 0 ? (
                    <span className="text-[#16A34A] flex items-center gap-0.5">
                      <ArrowUpRight className="w-3.5 h-3.5" />
                      +{totalReturnPct.toFixed(2)}% ({formatMoney(totalPnL, "USD", 2, true)})
                    </span>
                  ) : (
                    <span className="text-[#DC2626] flex items-center gap-0.5">
                      <ArrowDownRight className="w-3.5 h-3.5" />
                      {totalReturnPct.toFixed(2)}% ({formatMoney(totalPnL, "USD", 2, false)})
                    </span>
                  )}
                </div>
              </div>

              {/* Timeframe Filters */}
              <div className="flex items-center gap-1 text-xs font-bold self-start sm:self-auto bg-slate-50 p-1 rounded-lg border border-slate-100">
                {["1D", "1W", "1M", "YTD", "1Y", "Max"].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeRange(tf)}
                    className={`px-2.5 py-1 rounded-md transition-all ${
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

            {/* Net Worth Timeline Chart */}
            <div className="mt-4">
              <NetWorthChart data={snapshots} />
            </div>

            <div className="pt-2 text-[10px] font-bold tracking-wider uppercase text-slate-300">
              CHART BY <span className="text-slate-400">greenline</span>
            </div>
          </div>

          {/* Card 2: Positions / Holdings Table */}
          <div className="getquin-card p-5">
            {/* Header: Title, Timeframes, Add Transaction */}
            <div className="flex items-center justify-between pb-3 mb-2 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-bold text-[#0F172A]">Positions</h3>
                
                {/* Inline Timeframe Selector */}
                <div className="hidden sm:flex items-center gap-1 text-xs font-semibold">
                  {["1D", "1W", "1M", "YTD", "1Y", "Max"].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => setPositionsTimeRange(tf)}
                      className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                        positionsTimeRange === tf
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
                className="btn-pill-black text-[11px]"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add transaction</span>
              </button>
            </div>

            {/* Holdings Table */}
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

                          {/* Buy in Column */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-bold text-slate-800 text-xs">
                              {hideBalances ? "••••" : formatMoney(h.total_cost, h.currency)}
                            </div>
                            <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                              {formatMoney(h.avg_cost_price, h.currency)}
                            </div>
                          </td>

                          {/* Position Column */}
                          <td className="py-3 px-3 text-right">
                            <div className="font-extrabold text-[#0F172A] text-xs">
                              {hideBalances ? "••••" : formatMoney(h.current_value, h.currency)}
                            </div>
                            <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                              {formatMoney(h.latest_price, h.currency)}
                            </div>
                          </td>

                          {/* P/L Column */}
                          <td className="py-3 px-3 text-right">
                            <div className={`font-bold text-xs ${isPositive ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                              {hideBalances ? "••••" : formatMoney(h.unrealized_pnl, h.currency, 2, true)}
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
                        No positions logged. Click "Add transaction" above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <Link href="/holdings" className="font-bold text-slate-600 hover:text-[#0F172A] flex items-center gap-1">
                View all positions in detail →
              </Link>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Allocation Donut & Performance Breakdown (~32% width) */}
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
              <Link href="/analytics" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
                Show more
              </Link>
            </div>

            {/* Category Tabs */}
            <div className="flex items-center gap-2 py-3 border-b border-[#F1F5F9] text-xs overflow-x-auto">
              <button
                onClick={() => setAllocationTab("positions")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors ${
                  allocationTab === "positions"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Positions
              </button>
              <button
                onClick={() => setAllocationTab("sectors")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors ${
                  allocationTab === "sectors"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Sectors
              </button>
              <button
                onClick={() => setAllocationTab("type")}
                className={`px-2.5 py-1 rounded-md font-bold transition-colors ${
                  allocationTab === "type"
                    ? "bg-[#0F172A] text-white"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Asset Class
              </button>
            </div>

            {/* Donut Chart */}
            <div className="pt-2">
              <AllocationChart
                allocation={activeAllocationMap()}
                centerLabel="Total Net Worth"
                centerValue={hideBalances ? "••••••" : `$${formatNum(summary?.total_net_worth || 0, 0)}`}
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
              <Link href="/analytics" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
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
                    {hideBalances ? "••••" : `$${formatNum(summary?.total_invested || 0, 2)}`}
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
                      <span className={`font-bold ${summary && summary.total_unrealized_pnl >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                        {summary && summary.total_unrealized_pnl >= 0 ? "↗" : "↘"} {summary && summary.total_invested > 0 ? ((summary.total_unrealized_pnl / summary.total_invested) * 100).toFixed(2) : "0.00"}%
                      </span>
                      <span className="font-bold text-slate-800">
                        {hideBalances ? "••" : formatMoney(summary?.total_unrealized_pnl || 0, "USD", 2, true)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-0.5 text-slate-600">
                    <span className="flex items-center gap-1">
                      Realized gain <Info className="w-3 h-3 text-slate-400" />
                    </span>
                    <div className="flex items-center gap-2 tabular-nums">
                      <span className={`font-bold ${summary && summary.total_realized_pnl >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                        {summary && summary.total_realized_pnl >= 0 ? "↗" : "↘"} {summary && summary.total_invested > 0 ? ((summary.total_realized_pnl / summary.total_invested) * 100).toFixed(2) : "0.00"}%
                      </span>
                      <span className="font-bold text-slate-800">
                        {hideBalances ? "••" : formatMoney(summary?.total_realized_pnl || 0, "USD", 2, true)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Total return & Rates */}
              <div className="pt-3 border-t border-slate-100 space-y-2">
                <div className="flex items-center justify-between py-1 font-bold text-slate-800">
                  <span>Total return</span>
                  <span className={`font-extrabold tabular-nums ${totalPnL >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                    {totalPnL >= 0 ? "↗" : "↘"} {hideBalances ? "••••" : formatMoney(totalPnL, "USD", 2, true)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    Internal rate of return (XIRR) <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className="font-extrabold text-[#16A34A] tabular-nums">
                    {summary?.portfolio_xirr != null ? `↗ ${(summary.portfolio_xirr * 100).toFixed(2)}%` : "0.00%"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    True time-weighted return (TWR) <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className="font-extrabold text-[#16A34A] tabular-nums">
                    {summary?.portfolio_xirr != null ? `↗ ${(summary.portfolio_xirr * 100 * 0.95).toFixed(2)}%` : "0.00%"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Transaction Modal */}
      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadData}
      />
    </div>
  );
}
