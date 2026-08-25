"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  TrendingUp, TrendingDown, Wallet, PiggyBank, Plus, 
  Calendar, Layers, Filter, Search, Edit, Trash2, Split,
  ArrowRight, ShieldCheck, Tag, Sparkles
} from "lucide-react";
import { formatCurrency, formatCleanMoney, convertCurrency } from "@/lib/format";
import { TimelineKey, TIMELINE_OPTIONS, getTimelineDateRange } from "@/lib/dateUtils";
import { SankeyChart, SankeyDataResponse } from "@/components/SankeyChart";
import { CashflowModal, CashflowTransactionItem } from "@/components/CashflowModal";

interface CashflowSummary {
  total_income: number;
  total_expenses: number;
  total_invested: number;
  net_savings: number;
  savings_rate_pct: number;
  breakdown_by_label: { [key: string]: number };
  top_expense_categories: { category: string; amount: number; pct: number }[];
}

export default function CashflowPage() {
  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [sankeyData, setSankeyData] = useState<SankeyDataResponse | null>(null);
  const [transactions, setTransactions] = useState<CashflowTransactionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");

  // Filters
  const [sankeyDepth, setSankeyDepth] = useState<number>(2);
  const [selectedTimeline, setSelectedTimeline] = useState<TimelineKey>("THIS_MONTH");
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<CashflowTransactionItem | null>(null);

  const { startDate, endDate } = useMemo(() => {
    return getTimelineDateRange(selectedTimeline);
  }, [selectedTimeline]);

  useEffect(() => {
    loadAllData();
  }, [sankeyDepth, selectedTimeline]);

  const loadAllData = async () => {
    try {
      let includeInvestments = true;
      let activeCurrency = "EUR";
      try {
        const settingsRes = await apiFetch<{ link_brokerage_with_bank: boolean; master_currency: string }>("/settings");
        if (settingsRes) {
          if (typeof settingsRes.link_brokerage_with_bank === "boolean") {
            includeInvestments = !settingsRes.link_brokerage_with_bank;
          }
          if (settingsRes.master_currency) {
            activeCurrency = settingsRes.master_currency.trim().toUpperCase();
            setMasterCurrency(activeCurrency);
          }
        }
      } catch {
        const localVal = typeof window !== "undefined" && localStorage.getItem("greenline_link_brokerage_with_bank") === "true";
        includeInvestments = !localVal;
        activeCurrency = (typeof window !== "undefined" && localStorage.getItem("greenline_master_currency")) || "EUR";
        setMasterCurrency(activeCurrency);
      }

      const queryParams = new URLSearchParams();
      if (startDate) queryParams.append("start_date", startDate);
      if (endDate) queryParams.append("end_date", endDate);
      queryParams.append("include_investments", String(includeInvestments));
      queryParams.append("master_currency", activeCurrency);

      const qs = queryParams.toString() ? `?${queryParams.toString()}` : "";
      const sankeyQs = `?depth=${sankeyDepth}&include_investments=${includeInvestments}&master_currency=${activeCurrency}${startDate ? `&start_date=${startDate}` : ""}${endDate ? `&end_date=${endDate}` : ""}`;

      const [sumRes, sankeyRes, txRes] = await Promise.all([
        apiFetch<CashflowSummary>(`/cashflow/summary${qs}`),
        apiFetch<SankeyDataResponse>(`/cashflow/sankey${sankeyQs}`),
        apiFetch<CashflowTransactionItem[]>(`/cashflow${qs}`),
      ]);

      setSummary(sumRes);
      setSankeyData(sankeyRes);
      setTransactions(txRes || []);
    } catch (err) {
      console.error("Failed to load cashflow data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAddModal = () => {
    setEditingTransaction(null);
    setIsModalOpen(true);
  };

  const handleDeleteTransaction = async (id: number) => {
    if (!confirm("Are you sure you want to delete this cashflow record?")) return;
    try {
      await apiFetch(`/cashflow/${id}`, { method: "DELETE" });
      loadAllData();
    } catch (e: any) {
      alert(e.message || "Failed to delete transaction");
    }
  };

  // Filtered transactions for the ledger
  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      // Label filter
      if (selectedLabelFilter !== "ALL") {
        const matchesLabel = tx.items.some(
          (i) => (i.effective_label || i.label) === selectedLabelFilter
        );
        if (!matchesLabel) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = tx.title.toLowerCase().includes(q);
        const matchesAccount = tx.payments.some((p) => p.account_name?.toLowerCase().includes(q));
        const matchesCategory = tx.items.some(
          (i) => i.category_name?.toLowerCase().includes(q) || i.description?.toLowerCase().includes(q)
        );
        if (!matchesTitle && !matchesAccount && !matchesCategory) return false;
      }

      return true;
    });
  }, [transactions, selectedLabelFilter, searchQuery]);

  const labelTotals = summary?.breakdown_by_label || {};

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Income & Spends
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Cashflow engine, multi-currency ledger, and interactive Sankey diagram
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Timeline Filter Pills */}
          <div className="flex items-center bg-[#F1F5F9] p-1 rounded-xl text-xs font-bold flex-wrap">
            {TIMELINE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setSelectedTimeline(opt.key)}
                className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                  selectedTimeline === opt.key
                    ? "bg-[#0F172A] text-white shadow-xs"
                    : "text-slate-600 hover:text-black"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <button
            onClick={handleOpenAddModal}
            className="btn-pill-black text-xs cursor-pointer shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Record Spend / Income</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 1. SIDE-BY-SIDE: 4 KPI CARDS (20%) + SANKEY (80%)        */}
      {/* ======================================================== */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5 items-start">
        {/* Left 1 Col (~20% width): 4 Stacked KPI Cards */}
        <div className="xl:col-span-1 space-y-3.5 flex flex-col">
          {/* Card 1: Total Inflow */}
          <div className="getquin-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500">Total Inflow</span>
              <div className="p-1.5 bg-emerald-50 text-emerald-600 rounded-lg">
                <TrendingUp className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5">
              <div className="text-xl font-bold text-[#0F172A] tabular-nums">
                {formatCleanMoney(summary?.total_income || 0, masterCurrency)}
              </div>
              <p className="text-[10px] font-semibold text-emerald-600 mt-0.5">
                Salary, Consulting & Dividends
              </p>
            </div>
          </div>

          {/* Card 2: Total Expenses */}
          <div className="getquin-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500">Total Spends</span>
              <div className="p-1.5 bg-rose-50 text-rose-600 rounded-lg">
                <TrendingDown className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5">
              <div className="text-xl font-bold text-[#0F172A] tabular-nums">
                {formatCleanMoney(summary?.total_expenses || 0, masterCurrency)}
              </div>
              <p className="text-[10px] font-semibold text-rose-600 mt-0.5">
                Outflows & Lifestyle Spends
              </p>
            </div>
          </div>

          {/* Card 3: Net Retained Cash */}
          <div className="getquin-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500">Net Retained Cash</span>
              <div className="p-1.5 bg-blue-50 text-blue-600 rounded-lg">
                <Wallet className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5">
              <div className="text-xl font-bold text-[#0F172A] tabular-nums">
                {formatCleanMoney(summary?.net_savings || 0, masterCurrency)}
              </div>
              <p className="text-[10px] font-semibold text-slate-500 mt-0.5">
                Savings Rate: <span className="font-bold text-[#0F172A]">{summary?.savings_rate_pct || 0}%</span>
              </p>
            </div>
          </div>

          {/* Card 4: Classification Split */}
          <div className="getquin-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500">Classification Split</span>
              <div className="p-1.5 bg-purple-50 text-purple-600 rounded-lg">
                <PiggyBank className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2 space-y-1 text-[11px] font-semibold">
              <div className="flex items-center justify-between">
                <span className="text-emerald-700">Essential (Need):</span>
                <span className="font-bold text-[#0F172A]">{formatCurrency(labelTotals["ESSENTIAL"] || 0, masterCurrency)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-amber-700">Discretionary:</span>
                <span className="font-bold text-[#0F172A]">{formatCurrency(labelTotals["DISCRETIONARY"] || 0, masterCurrency)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-pink-700">Luxury:</span>
                <span className="font-bold text-[#0F172A]">{formatCurrency(labelTotals["LUXURY"] || 0, masterCurrency)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right 4 Cols (~80% width): Sankey Flow Diagram Card */}
        <div className="xl:col-span-4 getquin-card p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-600" />
                <span>Cashflow Sankey Flow Diagram</span>
              </h2>
              <p className="text-[11px] font-medium text-slate-400">
                Visualizing money flow from income & past savings into classification buckets and category nodes
              </p>
            </div>

            {/* Depth Selector (Level 1 to 5) */}
            <div className="flex items-center gap-1 bg-[#F1F5F9] p-1 rounded-xl text-xs font-bold">
              <span className="text-[10px] text-slate-400 font-bold px-2 uppercase tracking-wider flex items-center gap-1">
                <Layers className="w-3 h-3" /> Depth:
              </span>
              {[1, 2, 3, 4, 5].map((d) => (
                <button
                  key={d}
                  onClick={() => setSankeyDepth(d)}
                  className={`w-6 h-6 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center ${
                    sankeyDepth === d
                      ? "bg-[#0F172A] text-white shadow-xs"
                      : "text-slate-600 hover:text-black"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Render Sankey Visualizer */}
          <div className="w-full bg-slate-50/50 rounded-xl border border-slate-100 p-2 min-h-[420px] flex items-center justify-center">
            {loading && !sankeyData ? (
              <div className="text-xs font-bold text-slate-400 animate-pulse">
                Generating flow ribbons...
              </div>
            ) : (
              <SankeyChart data={sankeyData} currency={masterCurrency} />
            )}
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 2. TRANSACTIONS LEDGER TABLE                             */}
      {/* ======================================================== */}
      <div className="getquin-card p-5 space-y-4">
        {/* Table Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-bold text-[#0F172A]">
              Income & Spend Transactions ({filteredTransactions.length})
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Historical ledger with split payment methods and multi-category itemization
            </p>
          </div>

          {/* Search & Label Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Search merchant, account, category..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#F3F4F6] text-xs font-semibold text-slate-800 placeholder-slate-400 pl-8 pr-3 py-1.5 rounded-lg border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none w-52"
              />
            </div>

            {/* Label Filter Pills */}
            <div className="flex items-center bg-[#F1F5F9] p-1 rounded-xl text-xs font-bold">
              {["ALL", "ESSENTIAL", "DISCRETIONARY", "LUXURY", "INVESTMENT"].map((lbl) => (
                <button
                  key={lbl}
                  onClick={() => setSelectedLabelFilter(lbl)}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    selectedLabelFilter === lbl
                      ? "bg-[#0F172A] text-white shadow-xs"
                      : "text-slate-600 hover:text-black"
                  }`}
                >
                  {lbl === "ALL" ? "All Labels" : lbl.charAt(0) + lbl.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Ledger Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 text-[11px] font-bold uppercase tracking-wider">
                <th className="pb-2.5 font-bold">Date</th>
                <th className="pb-2.5 font-bold">Title / Merchant</th>
                <th className="pb-2.5 font-bold">Payment Method(s)</th>
                <th className="pb-2.5 font-bold">Category & Description</th>
                <th className="pb-2.5 font-bold text-right">Total Amount</th>
                <th className="pb-2.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {filteredTransactions.map((tx) => {
                const isTransfer = tx.transaction_kind === "TRANSFER" || tx.items.some((i) => i.category_type === "TRANSFER");
                const isIncome = !isTransfer && (tx.transaction_kind === "INCOME" || tx.items.some((i) => i.category_type === "INCOME"));

                return (
                  <tr key={tx.cashflow_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 font-semibold text-slate-500 tabular-nums whitespace-nowrap">
                      {tx.transaction_date}
                    </td>

                    <td className="py-3 font-bold text-[#0F172A]">
                      <div>{tx.title}</div>
                      {tx.notes && <div className="text-[10px] text-slate-400 font-normal mt-0.5">{tx.notes}</div>}
                    </td>

                    {/* Payment Method(s) with Green/Red Inflow/Outflow Dots */}
                    <td className="py-3">
                      <div className="flex flex-col gap-1">
                        {tx.payments.map((p, pIdx) => {
                          const pCurr = p.account_currency || tx.currency || "EUR";
                          const isCredit = p.amount > 0;
                          const dotColor = isCredit ? "bg-emerald-500" : "bg-rose-500";
                          const textColor = isCredit 
                            ? "text-emerald-600 dark:text-emerald-400" 
                            : "text-rose-600 dark:text-rose-400";
                          const signPrefix = isCredit ? "+" : "-";

                          return (
                            <div key={pIdx} className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700 dark:text-slate-200">
                              <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                              <span>{p.account_name}</span>
                              <span className={`tabular-nums font-bold ${textColor}`}>
                                ({signPrefix}{formatCurrency(Math.abs(p.amount), pCurr)})
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </td>

                    {/* Category & Description (Plain text for transfers) */}
                    <td className="py-3">
                      <div className="flex flex-col gap-1.5">
                        {isTransfer ? (
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-800 text-xs">
                              Account Transfers & FX
                            </span>
                            {tx.items.find((i) => i.category_name?.includes("Fee")) && (
                              <span className="text-slate-400 text-[11px]">
                                • Transfer Fee
                              </span>
                            )}
                          </div>
                        ) : (
                          tx.items.map((itm, iIdx) => {
                            const lbl = itm.effective_label || itm.label || "DISCRETIONARY";
                            const badgeColor =
                              lbl === "ESSENTIAL"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : lbl === "LUXURY"
                                ? "bg-pink-50 text-pink-700 border-pink-200"
                                : lbl === "INVESTMENT"
                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                : "bg-amber-50 text-amber-700 border-amber-200";

                            return (
                              <div key={iIdx} className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-slate-800 text-xs">
                                  {itm.category_name}
                                </span>
                                {itm.description && (
                                  <span className="text-slate-400 text-[11px]">
                                    • {itm.description}
                                  </span>
                                )}
                                <span className={`px-1.5 py-0.2 text-[9px] font-extrabold uppercase rounded-md border ${badgeColor}`}>
                                  {lbl}
                                </span>
                                {tx.items.length > 1 && (
                                  <span className={`font-bold text-[11px] tabular-nums ${itm.amount < 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400"}`}>
                                    {itm.amount < 0
                                      ? `- ${formatCurrency(Math.abs(itm.amount), tx.currency || "EUR")} (${isIncome ? "Adjustment" : "Reimbursement"})`
                                      : formatCurrency(itm.amount, tx.currency || "EUR")}
                                  </span>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </td>

                    {/* Total Amount Column (Green for Income, Red for Expense, Black for Transfers, No +/- signs) */}
                    <td className="py-3 text-right font-bold tabular-nums">
                      <div className={isTransfer ? "text-[#0F172A] text-xs" : isIncome ? "text-emerald-600 text-xs" : "text-rose-600 text-xs"}>
                        {formatCurrency(Math.abs(tx.total_amount), tx.currency || "EUR")}
                      </div>
                      {tx.currency && tx.currency !== masterCurrency && (
                        <div className="text-[10px] text-slate-400 font-semibold mt-0.5">
                          ≈ {formatCurrency(convertCurrency(Math.abs(tx.total_amount), tx.currency, masterCurrency), masterCurrency)}
                        </div>
                      )}
                    </td>

                    <td className="py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => {
                            setEditingTransaction(tx);
                            setIsModalOpen(true);
                          }}
                          className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer"
                          title="Edit"
                        >
                          <Edit className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteTransaction(tx.cashflow_id)}
                          className="p-1.5 text-rose-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 cursor-pointer"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {filteredTransactions.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400 font-medium text-xs">
                    No cashflow transactions recorded for this period.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Transaction Entry & Edit Modal */}
      <CashflowModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadAllData}
        initialData={editingTransaction}
      />
    </div>
  );
}
