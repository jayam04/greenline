"use client";

import * as React from "react";
import { apiFetch } from "@/lib/api";
import { money, signedMoney } from "@/lib/utils";
import { convertCurrency } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { HeroCard } from "@/components/MetricCard";
import { TrendBadge } from "@/components/ui/badge";
import { NetWorthChart, SnapshotData } from "@/components/NetWorthChart";
import { AllocationChart, Slice } from "@/components/AllocationChart";
import { CommunityPanel } from "@/components/CommunityPanel";
import { getSavedCommunityPseudonym, saveCommunityPseudonymLocally } from "@/lib/community";

interface Account {
  account_id: number;
  account_name: string;
  broker_name?: string;
  account_type: string;
  currency: string;
  current_balance?: number;
  cash_balance?: number;
  securities_value?: number;
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
}

interface PortfolioSummary {
  net_worth?: number;
  total_net_worth?: number;
  total_invested?: number;
  total_current_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  cash_balance?: number;
  asset_allocation?: Record<string, number>;
  top_holdings?: HoldingSummary[];
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

export default function Home() {
  const [loading, setLoading] = React.useState(true);
  const [expanded, setExpanded] = React.useState(false);
  const [summary, setSummary] = React.useState<PortfolioSummary | null>(null);
  const [snapshots, setSnapshots] = React.useState<SnapshotData[]>([]);
  const [annualSnapshot, setAnnualSnapshot] = React.useState<AnnualSnapshot | null>(null);
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [masterCurrency, setMasterCurrency] = React.useState<string>("EUR");
  const [alias, setAlias] = React.useState<string>("Solar Beaver");

  const loadData = React.useCallback(async () => {
    try {
      setLoading(true);
      const [sumRes, snapRes, annualRes, settingsRes, accRes] = await Promise.allSettled([
        apiFetch<PortfolioSummary>("/portfolio/summary"),
        apiFetch<SnapshotData[]>("/snapshots?limit=52"),
        apiFetch<AnnualSnapshot>("/portfolio/annual_snapshot"),
        apiFetch<{ community_pseudonym?: string; master_currency?: string }>("/settings"),
        apiFetch<Account[]>("/accounts"),
      ]);

      if (settingsRes.status === "fulfilled" && settingsRes.value) {
        if (settingsRes.value.master_currency) {
          setMasterCurrency(settingsRes.value.master_currency);
        }
        if (settingsRes.value.community_pseudonym) {
          const remoteAlias = settingsRes.value.community_pseudonym;
          setAlias(remoteAlias);
          saveCommunityPseudonymLocally(remoteAlias);
        } else {
          const saved = getSavedCommunityPseudonym();
          if (saved) setAlias(saved);
        }
      }

      if (sumRes.status === "fulfilled" && sumRes.value) {
        setSummary(sumRes.value);
      }
      if (snapRes.status === "fulfilled" && Array.isArray(snapRes.value)) {
        setSnapshots(snapRes.value);
      }
      if (annualRes.status === "fulfilled" && annualRes.value) {
        setAnnualSnapshot(annualRes.value);
      }
      if (accRes.status === "fulfilled" && Array.isArray(accRes.value)) {
        setAccounts(accRes.value);
      }
    } catch (e) {
      console.error("Failed to load home page data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Derived Account and Portfolio Balances
  const bankAccounts = React.useMemo(() => accounts.filter((a) => a.account_type === "bank"), [accounts]);
  const dematAccounts = React.useMemo(() => accounts.filter((a) => a.account_type !== "bank"), [accounts]);

  const totalBankCash = React.useMemo(() => {
    return bankAccounts.reduce((acc, a) => {
      const bal = a.cash_balance !== undefined ? a.cash_balance : (a.current_balance || 0);
      return acc + convertCurrency(bal, a.currency || "EUR", masterCurrency);
    }, 0);
  }, [bankAccounts, masterCurrency]);

  const totalDematCash = React.useMemo(() => {
    return dematAccounts.reduce((acc, a) => {
      const bal = a.cash_balance !== undefined ? a.cash_balance : 0;
      return acc + convertCurrency(bal, a.currency || "INR", masterCurrency);
    }, 0);
  }, [dematAccounts, masterCurrency]);

  const totalCash = totalBankCash + totalDematCash;

  const totalSecurities = React.useMemo(() => {
    if (summary?.top_holdings && summary.top_holdings.length > 0) {
      return summary.top_holdings.reduce((acc, h) => {
        return acc + convertCurrency(h.current_value, h.currency || "USD", masterCurrency);
      }, 0);
    }
    return dematAccounts.reduce((acc, a) => {
      return acc + convertCurrency(a.securities_value || 0, a.currency || "EUR", masterCurrency);
    }, 0);
  }, [summary, dematAccounts, masterCurrency]);

  const computedNetWorth = totalCash + totalSecurities;
  const latestSnapshot = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  const netWorthValue = latestSnapshot
    ? latestSnapshot.net_worth
    : computedNetWorth > 0
    ? computedNetWorth
    : (summary?.total_net_worth ?? summary?.net_worth ?? 0);

  const firstSnapshot = snapshots.length > 0 ? snapshots[0] : null;
  const deltaAmt = annualSnapshot?.net_worth_delta ?? (latestSnapshot && firstSnapshot ? latestSnapshot.net_worth - firstSnapshot.net_worth : 0);
  const deltaPct = annualSnapshot?.net_worth_delta_pct ?? (firstSnapshot && firstSnapshot.net_worth > 0 ? (deltaAmt / firstSnapshot.net_worth) * 100 : 0);

  // Allocation slices ("Where it sits")
  const allocationSlices: Slice[] = React.useMemo(() => {
    const slices: Slice[] = [];
    const colors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

    if (summary?.asset_allocation && Object.keys(summary.asset_allocation).length > 0) {
      const entries = Object.entries(summary.asset_allocation).filter(([_, v]) => v > 0);
      let colorIdx = 0;
      for (const [rawLabel, val] of entries) {
        if (rawLabel.toLowerCase().includes("cash") || rawLabel.toLowerCase().includes("bank")) {
          continue;
        }
        const label = rawLabel.charAt(0).toUpperCase() + rawLabel.slice(1);
        slices.push({
          label,
          value: Math.round(val),
          color: colors[colorIdx % colors.length],
        });
        colorIdx++;
      }
      if (totalCash > 0) {
        slices.push({
          label: "Cash & banks",
          value: Math.round(totalCash),
          color: colors[colorIdx % colors.length],
        });
      }
    } else {
      if (totalSecurities > 0) {
        slices.push({
          label: "Stocks & ETFs",
          value: Math.round(totalSecurities),
          color: colors[0],
        });
      }
      if (totalCash > 0) {
        slices.push({
          label: "Cash & banks",
          value: Math.round(totalCash),
          color: colors[1],
        });
      }
    }

    if (slices.length === 0 && netWorthValue > 0) {
      slices.push({
        label: "Securities",
        value: Math.round(netWorthValue),
        color: colors[0],
      });
    }

    return slices.sort((a, b) => b.value - a.value);
  }, [summary, totalCash, totalSecurities, netWorthValue]);

  // Annual snapshot rows
  const currentYear = new Date().getFullYear();
  const yearLabel = annualSnapshot?.year_label || `${currentYear}`;
  const incomeVal = annualSnapshot ? `+${money(annualSnapshot.total_income, masterCurrency)}` : `+${money(0, masterCurrency)}`;
  const expensesVal = annualSnapshot ? `−${money(annualSnapshot.total_expenses, masterCurrency)}` : `−${money(0, masterCurrency)}`;
  const savedVal = annualSnapshot ? signedMoney(annualSnapshot.net_savings, masterCurrency) : `${money(0, masterCurrency)}`;
  const investedVal = annualSnapshot ? money(annualSnapshot.investments_done, masterCurrency) : `${money(0, masterCurrency)}`;
  const soldVal = annualSnapshot ? money(annualSnapshot.investments_closed, masterCurrency) : `${money(0, masterCurrency)}`;

  const snapshotRows = [
    ["Income", incomeVal, "text-gain"],
    ["Expenses", expensesVal, "text-loss"],
    ["Saved", savedVal, "text-gain"],
    ["Invested", investedVal, ""],
    ["Sold", soldVal, ""],
  ];

  if (loading) {
    return (
      <>
        <PageHeader
          className="mb-4"
          title="Home"
          description="Your net worth at a glance."
        />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="flex flex-col gap-4 lg:min-h-[calc(100vh-8.5rem)]">
            <div className="rounded-card border border-border bg-surface shadow-card flex flex-1 flex-col p-6 animate-pulse min-h-[360px]">
              <div className="h-4 w-24 bg-surface-2 rounded mb-3" />
              <div className="h-8 w-48 bg-surface-2 rounded mb-6" />
              <div className="flex-1 rounded bg-surface-2/60 min-h-[200px]" />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-card border border-border bg-surface shadow-card p-5 animate-pulse min-h-[160px]">
                <div className="h-4 w-28 bg-surface-2 rounded mb-4" />
                <div className="h-24 bg-surface-2/60 rounded" />
              </div>
              <div className="rounded-card border border-border bg-surface shadow-card p-5 animate-pulse min-h-[160px]">
                <div className="h-4 w-28 bg-surface-2 rounded mb-4" />
                <div className="space-y-2">
                  <div className="h-4 bg-surface-2/60 rounded" />
                  <div className="h-4 bg-surface-2/60 rounded" />
                  <div className="h-4 bg-surface-2/60 rounded" />
                </div>
              </div>
            </div>
          </div>
          <div className="rounded-card border border-border bg-surface shadow-card p-5 animate-pulse min-h-[500px]">
            <div className="h-4 w-28 bg-surface-2 rounded mb-4" />
            <div className="h-16 bg-surface-2/60 rounded mb-4" />
            <div className="space-y-3">
              <div className="h-14 bg-surface-2/60 rounded" />
              <div className="h-14 bg-surface-2/60 rounded" />
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        className="mb-4"
        title="Home"
        description="Your net worth at a glance."
      />

      {expanded ? (
        /* Community takes the page. Net worth collapses to one compact strip. */
        <div className="space-y-4">
          <div className="rounded-card border border-border bg-surface shadow-card flex flex-wrap items-center justify-between gap-4 px-5 py-3">
            <div className="flex items-baseline gap-3">
              <span className="eyebrow">Net worth</span>
              <span className="text-title font-semibold tnum">{money(netWorthValue, masterCurrency)}</span>
              <TrendBadge value={deltaPct} />
            </div>
            <span className="text-label text-muted">
              YTD {deltaAmt >= 0 ? "+" : "−"}{money(Math.abs(deltaAmt), masterCurrency)}
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
                  data={snapshots}
                  height={250}
                  currency={masterCurrency}
                  compact
                  fill
                  header={
                    <HeroCard
                      label="Net worth"
                      value={netWorthValue}
                      delta={deltaPct}
                      deltaAmount={deltaAmt}
                      currency={masterCurrency}
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
                    currency={masterCurrency}
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
    </>
  );
}
