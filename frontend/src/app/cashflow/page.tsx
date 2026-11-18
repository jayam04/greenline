"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { money } from "@/lib/utils";
import { getMasterCurrency } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { MetricCard } from "@/components/MetricCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/tabs";
import { SankeyChart, SankeyDataResponse } from "@/components/SankeyChart";
import { CashflowModal } from "@/components/CashflowModal";
import { Plus, ArrowRight } from "lucide-react";

interface CashflowSummary {
  total_income: number;
  total_expenses: number;
  total_invested: number;
  net_savings: number;
  savings_rate_pct: number;
  breakdown_by_label?: Record<string, number>;
  top_expense_categories?: { category: string; amount: number; pct: number }[];
}

type TimeframeOption = "week" | "month" | "ytd" | "all";

export default function CashflowOverviewPage() {
  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [sankeyData, setSankeyData] = useState<SankeyDataResponse | null>(null);
  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");
  const [timeframe, setTimeframe] = useState<TimeframeOption>("month");
  const [loading, setLoading] = useState(true);
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);

  useEffect(() => {
    document.title = "Income & Spend · greenline";
    loadData();
  }, [timeframe]);

  const getDateRange = (tf: TimeframeOption) => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    const today = `${year}-${month}-${day}`;

    if (tf === "week") {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return { start: d.toISOString().split("T")[0], end: today };
    }
    if (tf === "month") {
      return { start: `${year}-${month}-01`, end: today };
    }
    if (tf === "ytd") {
      return { start: `${year}-01-01`, end: today };
    }
    return { start: null, end: null };
  };

  const loadData = async () => {
    try {
      setLoading(true);
      let activeCurrency = "EUR";
      try {
        const settingsRes = await apiFetch<{ master_currency: string }>("/settings");
        if (settingsRes?.master_currency) {
          activeCurrency = settingsRes.master_currency.trim().toUpperCase();
        }
      } catch {
        activeCurrency = getMasterCurrency();
      }
      setMasterCurrency(activeCurrency);

      const { start, end } = getDateRange(timeframe);
      const queryParams = new URLSearchParams();
      if (start) queryParams.append("start_date", start);
      if (end) queryParams.append("end_date", end);
      queryParams.append("include_investments", "true");
      queryParams.append("master_currency", activeCurrency);

      const qs = queryParams.toString() ? `?${queryParams.toString()}` : "";
      const sankeyQs = `?depth=2&include_investments=true&master_currency=${activeCurrency}${start ? `&start_date=${start}` : ""}${end ? `&end_date=${end}` : ""}`;

      const [sumRes, sankeyRes] = await Promise.all([
        apiFetch<CashflowSummary>(`/cashflow/summary${qs}`),
        apiFetch<SankeyDataResponse>(`/cashflow/sankey${sankeyQs}`).catch(() => null),
      ]);

      setSummary(sumRes);
      setSankeyData(sankeyRes);
    } catch (err) {
      console.error("Failed to load cashflow data:", err);
    } finally {
      setLoading(false);
    }
  };

  const totalInflow = summary?.total_income ?? 0;
  const totalSpends = summary?.total_expenses ?? 0;
  const netSavings = summary?.net_savings ?? 0;
  const savingsRate = summary?.savings_rate_pct ?? (totalInflow > 0 ? Math.round(((totalInflow - totalSpends) / totalInflow) * 100) : 0);

  const breakdown = summary?.breakdown_by_label || {};
  const essentialSpend = breakdown["ESSENTIAL"] ?? 0;
  const discretionarySpend = breakdown["DISCRETIONARY"] ?? 0;
  const luxurySpend = breakdown["LUXURY"] ?? 0;

  return (
    <>
      <PageHeader
        title="Income & spend"
        description="Where money came from and where it went this period."
        actions={
          <div className="flex items-center gap-3">
            <Segmented
              size="sm"
              value={timeframe}
              onChange={(v) => setTimeframe(v as TimeframeOption)}
              options={[
                { value: "week", label: "Week" },
                { value: "month", label: "Month" },
                { value: "ytd", label: "YTD" },
                { value: "all", label: "All" },
              ]}
            />
            <Button size="sm" onClick={() => setIsRecordModalOpen(true)}>
              <Plus className="size-4" />
              <span>Record</span>
            </Button>
          </div>
        }
      />

      {/* 4 Financial Pulse Metric Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Total inflow"
          value={totalInflow}
          currency={masterCurrency}
          tone="gain"
          hint="Salary, consulting, dividends"
        />
        <MetricCard
          label="Total spends"
          value={totalSpends}
          currency={masterCurrency}
          tone="loss"
          hint="Outflows & lifestyle"
        />
        <MetricCard
          label="Net retained"
          value={netSavings}
          currency={masterCurrency}
          tone={netSavings >= 0 ? "gain" : "loss"}
          hint={`Savings rate ${savingsRate}%`}
        />
        <Card className="p-4">
          <div className="text-micro uppercase tracking-wider text-subtle font-medium">Classification</div>
          <dl className="mt-2 space-y-1.5 text-label font-medium">
            <div className="flex items-center justify-between">
              <dt className="text-gain">Essential</dt>
              <dd className="font-semibold text-foreground">{money(essentialSpend, masterCurrency)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-warn">Discretionary</dt>
              <dd className="font-semibold text-foreground">{money(discretionarySpend, masterCurrency)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-muted">Luxury</dt>
              <dd className="font-semibold text-foreground">{money(luxurySpend, masterCurrency)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      {/* Cashflow Diagram: Sankey Flow Chart */}
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div>
            <CardTitle>Cashflow diagram</CardTitle>
            <CardDescription>Income into essentials, discretionary spend and savings</CardDescription>
          </div>
          <Link
            href="/cashflow/transactions"
            className="flex items-center gap-1.5 text-label font-medium text-primary hover:underline"
          >
            <span>View all transactions</span>
            <ArrowRight className="size-3.5" />
          </Link>
        </CardHeader>
        <CardContent>
          {sankeyData && sankeyData.nodes && sankeyData.nodes.length > 0 ? (
            <SankeyChart
              data={sankeyData}
              loading={loading}
              currency={masterCurrency}
            />
          ) : (
            <div className="py-16 text-center text-label text-muted">
              {loading ? "Calculating cashflow movements..." : "No cash movements recorded for this period."}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cashflow Record Modal */}
      {isRecordModalOpen && (
        <CashflowModal
          isOpen={isRecordModalOpen}
          initialData={null}
          onClose={() => setIsRecordModalOpen(false)}
          onSuccess={() => {
            setIsRecordModalOpen(false);
            loadData();
          }}
        />
      )}
    </>
  );
}
