"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { money, signedMoney } from "@/lib/utils";
import { PageHeader } from "@/components/PageHeader";
import { HeroCard } from "@/components/MetricCard";
import { TrendBadge } from "@/components/ui/badge";
import { NetWorthChart, SnapshotData } from "@/components/NetWorthChart";
import { AllocationChart, Slice } from "@/components/AllocationChart";
import { CommunityPanel } from "@/components/CommunityPanel";
import { TransactionModal } from "@/components/TransactionModal";
import { getSavedCommunityPseudonym, saveCommunityPseudonymLocally } from "@/lib/community";

interface PortfolioSummary {
  net_worth?: number;
  total_net_worth?: number;
  total_invested?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  cash_balance?: number;
  asset_allocation?: Record<string, number>;
}

interface AnnualSnapshot {
  year_label: string;
  total_income: number;
  total_expenses: number;
  investments_done: number;
  investments_closed: number;
  net_worth_delta: number;
  net_worth_delta_pct: number;
  net_savings: number;
  currency: string;
}

const FALLBACK_NETWORTH_SERIES = [
  113.7, 116.2, 115.0, 118.4, 122.1, 120.8, 124.6, 127.3, 131.0, 129.5,
  134.2, 137.8, 136.0, 140.2, 143.5, 141.8, 145.0, 148.6, 147.2, 150.8,
  153.4, 151.9, 155.359,
];

export default function Home() {
  const [expanded, setExpanded] = React.useState(false);
  const [summary, setSummary] = React.useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = React.useState<SnapshotData[]>([]);
  const [annualSnapshot, setAnnualSnapshot] = React.useState<AnnualSnapshot | null>(null);
  const [alias, setAlias] = React.useState<string>("Solar Beaver");
  const [isAddTransactionOpen, setIsAddTransactionOpen] = React.useState(false);

  const loadData = React.useCallback(async () => {
    try {
      const [sumRes, snapRes, annualRes, settingsRes] = await Promise.allSettled([
        apiFetch<PortfolioSummary>("/portfolio/summary"),
        apiFetch<SnapshotData[]>("/snapshots?limit=52"),
        apiFetch<AnnualSnapshot>("/portfolio/annual_snapshot"),
        apiFetch<{ community_pseudonym?: string; master_currency?: string }>("/settings"),
      ]);

      if (sumRes.status === "fulfilled" && sumRes.value) {
        setSummary(sumRes.value);
      }
      if (snapRes.status === "fulfilled" && Array.isArray(snapRes.value)) {
        setSnapshots(snapRes.value);
      }
      if (annualRes.status === "fulfilled" && annualRes.value) {
        setAnnualSnapshot(annualRes.value);
      }
      if (settingsRes.status === "fulfilled" && settingsRes.value?.community_pseudonym) {
        const remoteAlias = settingsRes.value.community_pseudonym;
        setAlias(remoteAlias);
        saveCommunityPseudonymLocally(remoteAlias);
      } else {
        const saved = getSavedCommunityPseudonym();
        if (saved) setAlias(saved);
      }
    } catch (e) {
      console.error("Failed to load home page data:", e);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Derived metrics
  const netWorthValue = summary?.total_net_worth ?? summary?.net_worth ?? 155359.24;
  const deltaPct = annualSnapshot?.net_worth_delta_pct ?? 36.55;
  const deltaAmt = annualSnapshot?.net_worth_delta ?? 41585.0;

  // Chart data
  const chartData = snapshots.length > 0 ? snapshots : FALLBACK_NETWORTH_SERIES;

  // Allocation slices
  const sliceColors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
  const allocationSlices: Slice[] =
    summary?.asset_allocation && Object.keys(summary.asset_allocation).length > 0
      ? Object.entries(summary.asset_allocation)
          .filter(([_, v]) => v > 0)
          .sort((a, b) => b[1] - a[1])
          .map(([label, value], i) => ({
            label,
            value,
            color: sliceColors[i % sliceColors.length],
          }))
      : [
          { label: "Stocks & ETFs", value: 135000, color: "var(--chart-1)" },
          { label: "Cash & banks", value: 20359, color: "var(--chart-2)" },
        ];

  // Annual snapshot rows
  const currentYear = new Date().getFullYear();
  const yearLabel = annualSnapshot?.year_label || `${currentYear}`;
  const incomeVal = annualSnapshot ? `+${money(annualSnapshot.total_income)}` : "+€104,924.96";
  const expensesVal = annualSnapshot ? `−${money(annualSnapshot.total_expenses)}` : "−€69,146.48";
  const savedVal = annualSnapshot ? signedMoney(annualSnapshot.net_savings) : "+€35,778.48";
  const investedVal = annualSnapshot ? money(annualSnapshot.investments_done) : "€65,578.00";
  const soldVal = annualSnapshot ? money(annualSnapshot.investments_closed) : "€41,262.40";

  const snapshotRows = [
    ["Income", incomeVal, "text-gain"],
    ["Expenses", expensesVal, "text-loss"],
    ["Saved", savedVal, "text-gain"],
    ["Invested", investedVal, ""],
    ["Sold", soldVal, ""],
  ];

  return (
    <>
      <PageHeader
        className="mb-4"
        title="Home"
        description="Your net worth at a glance."
        actions={
          <button
            type="button"
            onClick={() => setIsAddTransactionOpen(true)}
            className="inline-flex items-center gap-2 rounded-control bg-primary px-4 py-2 text-body font-medium text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs"
          >
            <Plus className="size-4" /> Add transaction
          </button>
        }
      />

      {expanded ? (
        /* Community takes the page. Net worth collapses to one compact strip. */
        <div className="space-y-4">
          <div className="rounded-card border border-border bg-surface shadow-card flex flex-wrap items-center justify-between gap-4 px-5 py-3">
            <div className="flex items-baseline gap-3">
              <span className="eyebrow">Net worth</span>
              <span className="text-title font-semibold tnum">{money(netWorthValue)}</span>
              <TrendBadge value={deltaPct} />
            </div>
            <span className="text-label text-muted">
              YTD {deltaAmt >= 0 ? "+" : "−"}{money(Math.abs(deltaAmt))}
            </span>
          </div>
          <CommunityPanel expanded onToggle={() => setExpanded(false)} alias={alias} />
        </div>
      ) : (
        /* Everything fits one 1440x900 screen: compact chart, donut beside its legend, tight stat rows. */
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="flex flex-col gap-4 lg:min-h-[calc(100vh-8.5rem)]">
            <div className="rounded-card border border-border bg-surface shadow-card flex flex-1 flex-col">
              <div className="flex min-h-0 flex-1 flex-col p-5">
                <NetWorthChart
                  data={chartData}
                  height={250}
                  compact
                  fill
                  header={
                    <HeroCard
                      label="Net worth"
                      value={netWorthValue}
                      delta={deltaPct}
                      deltaAmount={deltaAmt}
                    />
                  }
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-card border border-border bg-surface shadow-card flex flex-col">
                <div className="px-5 pt-4">
                  <h3 className="text-title font-semibold">Where it sits</h3>
                </div>
                <div className="flex flex-1 items-center px-5 pb-4 pt-2">
                  <AllocationChart
                    className="w-full"
                    compact
                    centerLabel="Total"
                    slices={allocationSlices}
                  />
                </div>
              </div>

              <div className="rounded-card border border-border bg-surface shadow-card">
                <div className="px-5 pt-4">
                  <h3 className="text-title font-semibold">{yearLabel} so far</h3>
                </div>
                <div className="px-5 pb-3 pt-1">
                  <dl className="divide-y divide-border text-body">
                    {snapshotRows.map(([k, v, c]) => (
                      <div key={k} className="flex items-center justify-between py-2">
                        <dt className="text-muted">{k}</dt>
                        <dd className={`tnum font-medium ${c}`}>{v}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <CommunityPanel expanded={false} onToggle={() => setExpanded(true)} alias={alias} />
        </div>
      )}

      {/* Transaction Modal */}
      <TransactionModal
        isOpen={isAddTransactionOpen}
        onClose={() => setIsAddTransactionOpen(false)}
        onSuccess={() => {
          setIsAddTransactionOpen(false);
          loadData();
        }}
      />
    </>
  );
}
