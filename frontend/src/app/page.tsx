"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { NetWorthChart } from "@/components/NetWorthChart";
import { AllocationChart } from "@/components/AllocationChart";
import { TransactionModal } from "@/components/TransactionModal";
import { 
  Wallet, DollarSign, ArrowUpRight, Percent, RefreshCw, Plus, PieChart as PieIcon, LineChart as LineIcon
} from "lucide-react";

interface PortfolioSummary {
  total_net_worth: number;
  total_invested: number;
  total_current_value: number;
  cash_balance: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  portfolio_xirr: number | null;
  asset_allocation: Record<string, number>;
  top_holdings: any[];
}

interface Snapshot {
  snapshot_date: string;
  net_worth: number;
  total_invested: number;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [sumData, snapData] = await Promise.all([
        apiFetch<PortfolioSummary>("/portfolio/summary"),
        apiFetch<Snapshot[]>("/snapshots"),
      ]);
      setSummary(sumData);
      setSnapshots(snapData);
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

  const formatUSD = (val: number) => `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="space-y-8">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight">Portfolio Dashboard</h1>
          <p className="text-xs text-slate-400 mt-1">Real-time valuation, net worth timeline, and XIRR return metrics</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefreshPrices}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Syncing Market Prices..." : "Sync Prices"}
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 text-xs font-bold bg-emerald-500 hover:bg-emerald-600 text-slate-950 rounded-lg transition-colors shadow-lg shadow-emerald-500/10"
          >
            <Plus className="w-4 h-4" />
            Add Transaction
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Net Worth"
          value={summary ? formatUSD(summary.total_net_worth) : "$0.00"}
          subtitle={summary ? `Invested: ${formatUSD(summary.total_invested)}` : ""}
          icon={Wallet}
        />
        <MetricCard
          title="Overall XIRR"
          value={summary?.portfolio_xirr != null ? `${(summary.portfolio_xirr * 100).toFixed(2)}%` : "N/A"}
          subtitle="Cash-flow weighted annual return"
          icon={Percent}
          trend={summary?.portfolio_xirr && summary.portfolio_xirr > 0 ? "up" : "neutral"}
          trendValue={summary?.portfolio_xirr ? `${(summary.portfolio_xirr * 100).toFixed(1)}%` : undefined}
        />
        <MetricCard
          title="Unrealized P&L"
          value={summary ? formatUSD(summary.total_unrealized_pnl) : "$0.00"}
          subtitle="Mark-to-market open lots"
          icon={ArrowUpRight}
          trend={summary && summary.total_unrealized_pnl >= 0 ? "up" : "down"}
          trendValue={
            summary && summary.total_invested > 0
              ? `${((summary.total_unrealized_pnl / summary.total_invested) * 100).toFixed(1)}%`
              : undefined
          }
        />
        <MetricCard
          title="Realized P&L"
          value={summary ? formatUSD(summary.total_realized_pnl) : "$0.00"}
          subtitle="Closed FIFO lot sales"
          icon={DollarSign}
          trend={summary && summary.total_realized_pnl >= 0 ? "up" : "down"}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <LineIcon className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-bold text-white">Net Worth Timeline</h2>
            </div>
            <span className="text-xs text-slate-400 font-mono">Daily Snapshots</span>
          </div>
          <NetWorthChart data={snapshots} />
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <PieIcon className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold text-white">Asset Allocation</h2>
          </div>
          <AllocationChart allocation={summary?.asset_allocation || {}} />
        </div>
      </div>

      {/* Top Holdings Preview */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold text-white">Top Portfolio Holdings</h2>
          <a href="/holdings" className="text-xs font-semibold text-emerald-400 hover:underline">
            View All Holdings →
          </a>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Asset</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-right">Quantity</th>
                <th className="py-3 px-4 text-right">Avg Cost</th>
                <th className="py-3 px-4 text-right">Latest Price</th>
                <th className="py-3 px-4 text-right">Current Value</th>
                <th className="py-3 px-4 text-right">Unrealized P&L</th>
                <th className="py-3 px-4 text-right">XIRR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {summary?.top_holdings && summary.top_holdings.length > 0 ? (
                summary.top_holdings.map((h) => (
                  <tr key={h.asset_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-white">
                      <div>{h.symbol}</div>
                      <div className="text-xs text-slate-400 font-normal">{h.name}</div>
                    </td>
                    <td className="py-3 px-4 text-xs font-medium text-slate-400 uppercase">{h.asset_type}</td>
                    <td className="py-3 px-4 text-right font-mono">{h.quantity_held}</td>
                    <td className="py-3 px-4 text-right font-mono">${h.avg_cost_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right font-mono">${h.latest_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-white">${h.current_value.toFixed(2)}</td>
                    <td className={`py-3 px-4 text-right font-mono font-semibold ${h.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {h.unrealized_pnl >= 0 ? "+" : ""}${h.unrealized_pnl.toFixed(2)} ({h.unrealized_pnl_pct.toFixed(1)}%)
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-emerald-400">
                      {h.xirr != null ? `${(h.xirr * 100).toFixed(1)}%` : "-"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 text-sm">
                    No active holdings. Click "Add Transaction" above to start tracking.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
