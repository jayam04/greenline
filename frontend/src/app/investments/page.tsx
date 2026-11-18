"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { money } from "@/lib/utils";
import { formatXirr, convertCurrency, getMasterCurrency } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { MetricCard } from "@/components/MetricCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { NetWorthChart, SnapshotData } from "@/components/NetWorthChart";
import { AllocationChart, Slice } from "@/components/AllocationChart";
import { TransactionModal } from "@/components/TransactionModal";
import { Plus, ArrowRight } from "lucide-react";

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
  unrealized_pnl_pct: number;
  realized_pnl: number;
  xirr?: number | null;
  weight_pct?: number;
}

interface PortfolioSummary {
  net_worth?: number;
  total_net_worth?: number;
  total_cost?: number;
  total_invested?: number;
  total_current_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  realized_pnl?: number;
  cash_balance?: number;
  total_fees?: number;
  total_taxes?: number;
  portfolio_xirr?: number | null;
  top_holdings?: HoldingSummary[];
  asset_allocation?: Record<string, number>;
  sector_allocation?: Record<string, number>;
}

interface Snapshot {
  snapshot_date: string;
  net_worth: number;
  total_invested?: number;
  total_current_value?: number;
  cash_balance?: number;
}

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
  account_type?: string;
}

const ALLOCATION_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

export default function InvestmentsDashboardPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");
  const [selectedAccountId, setSelectedAccountId] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);

  useEffect(() => {
    document.title = "Portfolio · greenline";
    loadData();
  }, [selectedAccountId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const accParam = selectedAccountId !== "all" ? `?account_id=${selectedAccountId}` : "";
      const [sumRes, snapRes, accRes, settingsRes] = await Promise.all([
        apiFetch<PortfolioSummary>(`/portfolio/summary${accParam}`),
        apiFetch<Snapshot[]>(`/snapshots${accParam}`),
        apiFetch<Account[]>("/accounts"),
        apiFetch<{ master_currency: string }>("/settings").catch(() => null),
      ]);

      setSummary(sumRes);
      setSnapshots(snapRes || []);
      setAccounts(accRes || []);
      if (settingsRes?.master_currency) {
        setMasterCurrency(settingsRes.master_currency.trim().toUpperCase());
      } else {
        setMasterCurrency(getMasterCurrency());
      }
    } catch (e) {
      console.error("Failed to load portfolio dashboard data:", e);
    } finally {
      setLoading(false);
    }
  };

  const dematAccounts = useMemo(() => {
    return accounts.filter((a) => a.account_type !== "bank");
  }, [accounts]);

  const portfolioValue = summary?.total_current_value ?? summary?.total_net_worth ?? summary?.net_worth ?? 0;
  const unrealizedPnl = summary?.unrealized_pnl ?? 0;
  const unrealizedPnlPct = summary?.unrealized_pnl_pct ?? 0;
  const realizedPnl = summary?.realized_pnl ?? 0;
  const totalCost = summary?.total_cost ?? summary?.total_invested ?? 0;
  const portfolioXirr = summary?.portfolio_xirr ?? null;

  // Chart data preparation
  const chartSnapshots: SnapshotData[] = useMemo(() => {
    if (!snapshots || snapshots.length === 0) {
      return [{
        snapshot_date: new Date().toISOString().split("T")[0],
        net_worth: portfolioValue,
      }];
    }
    return snapshots.map((s) => ({
      snapshot_date: s.snapshot_date,
      net_worth: s.total_current_value ?? s.net_worth,
      total_invested: s.total_invested,
    }));
  }, [snapshots, portfolioValue]);

  // Allocation slices
  const allocationSlices: Slice[] = useMemo(() => {
    if (summary?.top_holdings && summary.top_holdings.length > 0) {
      const top5 = summary.top_holdings.slice(0, 5);
      return top5.map((h, i) => ({
        label: h.symbol,
        value: h.current_value,
        color: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length],
      }));
    }
    if (summary?.asset_allocation && Object.keys(summary.asset_allocation).length > 0) {
      return Object.entries(summary.asset_allocation).map(([key, val], i) => ({
        label: key,
        value: val,
        color: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length],
      }));
    }
    return [
      { label: "Equities", value: portfolioValue || 100, color: ALLOCATION_COLORS[0] },
    ];
  }, [summary, portfolioValue]);

  return (
    <>
      <PageHeader
        title="Portfolio"
        description="How your investments are performing across all brokers."
        actions={
          <div className="flex items-center gap-2">
            {dematAccounts.length > 1 && (
              <select
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                className="h-9 rounded-control border border-border bg-surface px-3 text-label font-medium text-foreground transition-colors hover:border-border-strong focus:outline-none"
              >
                <option value="all">All Brokers ({dematAccounts.length})</option>
                {dematAccounts.map((a) => (
                  <option key={a.account_id} value={a.account_id.toString()}>
                    {a.account_name} ({a.currency})
                  </option>
                ))}
              </select>
            )}
            <Button size="sm" onClick={() => setIsTradeModalOpen(true)}>
              <Plus className="size-4" />
              <span>Add trade</span>
            </Button>
          </div>
        }
      />

      {/* 4 Financial Performance Metric Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Value"
          value={portfolioValue}
          currency={masterCurrency}
          delta={unrealizedPnlPct}
          hint={totalCost > 0 ? `Cost: ${money(totalCost, masterCurrency)}` : undefined}
        />
        <MetricCard
          label="Unrealized P&L"
          value={unrealizedPnl}
          currency={masterCurrency}
          tone={unrealizedPnl >= 0 ? "gain" : "loss"}
          delta={unrealizedPnlPct}
        />
        <MetricCard
          label="Realized P&L"
          value={realizedPnl}
          currency={masterCurrency}
          tone={realizedPnl >= 0 ? "gain" : "loss"}
          hint="Closed gains & losses"
        />
        <MetricCard
          label="Annualised return"
          value={0}
          display={portfolioXirr != null ? formatXirr(portfolioXirr) : "—"}
          tone={portfolioXirr != null && portfolioXirr >= 0 ? "gain" : "loss"}
          hint="XIRR calculation"
        />
      </div>

      {/* Side-by-side Executive Cockpit: Performance Chart + Donut Allocation */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left Column: Valuation Curve */}
        <Card>
          <CardHeader>
            <CardTitle>Portfolio value</CardTitle>
            <CardDescription>Performance timeline across connected brokers</CardDescription>
          </CardHeader>
          <CardContent>
            <NetWorthChart data={chartSnapshots} currency={masterCurrency} />
          </CardContent>
        </Card>

        {/* Right Column: Allocation Donut */}
        <Card className="flex flex-col justify-between">
          <div>
            <CardHeader>
              <CardTitle>Allocation</CardTitle>
              <CardDescription>Position distribution & weightings</CardDescription>
            </CardHeader>
            <CardContent>
              <AllocationChart
                centerLabel="Portfolio"
                slices={allocationSlices}
                currency={masterCurrency}
              />
            </CardContent>
          </div>
          <div className="border-t border-border p-4">
            <Link
              href="/investments/holdings"
              className="flex items-center justify-between text-label font-medium text-primary hover:underline"
            >
              <span>View all positions</span>
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </Card>
      </div>

      {/* Trade Modal */}
      {isTradeModalOpen && (
        <TransactionModal
          isOpen={isTradeModalOpen}
          initialData={null}
          onClose={() => setIsTradeModalOpen(false)}
          onSuccess={() => {
            setIsTradeModalOpen(false);
            loadData();
          }}
        />
      )}
    </>
  );
}
