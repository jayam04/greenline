"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  Plus, Search, Filter, TrendingUp, TrendingDown, Wallet, 
  PiggyBank, ArrowDownLeft, ArrowUpRight, Split, Trash2, Edit, 
  SlidersHorizontal, Check, RefreshCw
} from "lucide-react";
import { formatCurrency, formatCleanMoney } from "@/lib/format";
import { SankeyChart, SankeyData } from "@/components/SankeyChart";
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
  const [transactions, setTransactions] = useState<CashflowTransactionItem[]>([]);
  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [sankeyData, setSankeyData] = useState<SankeyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingSankey, setLoadingSankey] = useState(false);

  // Sankey Controls
  const [sankeyDepth, setSankeyDepth] = useState<number>(2);
  const [includeInvestments, setIncludeInvestments] = useState<boolean>(true);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>("ALL");
  const [dateRangeFilter, setDateRangeFilter] = useState<string>("YTD");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<CashflowTransactionItem | null>(null);

  useEffect(() => {
    loadData();
  }, [dateRangeFilter]);

  useEffect(() => {
    loadSankey();
  }, [sankeyDepth, includeInvestments, dateRangeFilter]);

  const getDateRangeParams = () => {
    const today = new Date();
    let startDate: string | undefined = undefined;
    const endDate: string = today.toISOString().split("T")[0];

    if (dateRangeFilter === "1M") {
      const d = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
      startDate = d.toISOString().split("T")[0];
    } else if (dateRangeFilter === "YTD") {
      startDate = `${today.getFullYear()}-01-01`;
    } else if (dateRangeFilter === "1Y") {
      const d = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
      startDate = d.toISOString().split("T")[0];
    }

    return { startDate, endDate };
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const { startDate, endDate } = getDateRangeParams();
      let queryParams = "";
      if (startDate) queryParams += `?start_date=${startDate}&end_date=${endDate}`;

      const [txData, sumData] = await Promise.all([
        apiFetch<CashflowTransactionItem[]>(`/cashflow${queryParams}`),
        apiFetch<CashflowSummary>(`/cashflow/summary${queryParams}`),
      ]);

      setTransactions(txData || []);
      setSummary(sumData || null);
    } catch (e) {
      console.error("Failed to load cashflow data:", e);
    } finally {
      setLoading(false);
    }
  };

  const loadSankey = async () => {
    try {
      setLoadingSankey(true);
      const { startDate, endDate } = getDateRangeParams();
      let query = `?depth=${sankeyDepth}&include_investments=${includeInvestments}`;
      if (startDate) query += `&start_date=${startDate}&end_date=${endDate}`;

      const data = await apiFetch<SankeyData>(`/cashflow/sankey${query}`);
      setSankeyData(data || null);
    } catch (e) {
      console.error("Failed to load sankey data:", e);
    } finally {
      setLoadingSankey(false);
    }
  };

  const handleDeleteTransaction = async (id: number) => {
    if (!confirm("Are you sure you want to delete this cashflow transaction?")) return;
    try {
      await apiFetch(`/cashflow/${id}`, { method: "DELETE" });
      loadData();
      loadSankey();
    } catch (err: any) {
      alert(err.message || "Failed to delete transaction");
    }
  };

  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      const matchesSearch = 
        tx.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tx.payments.some((p) => (p.account_name || "").toLowerCase().includes(searchQuery.toLowerCase())) ||
        tx.items.some((i) => (i.category_name || "").toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesLabel =
        selectedLabelFilter === "ALL" ||
        tx.items.some((i) => (i.effective_label || i.label) === selectedLabelFilter);

      return matchesSearch && matchesLabel;
    });
  }, [transactions, searchQuery, selectedLabelFilter]);

  const labelTotals = summary?.breakdown_by_label || {};
  const totalOutflows = (summary?.total_expenses || 0) + (summary?.total_invested || 0);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Income & Spends
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Cashflow tracking, multi-account splits, and hierarchical Sankey flow analysis
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Timeframe Filter Pills */}
          <div className="flex items-center bg-[#F1F5F9] p-1 rounded-xl">
            {["1M", "YTD", "1Y", "ALL"].map((range) => (
              <button
                key={range}
                onClick={() => setDateRangeFilter(range)}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                  dateRangeFilter === range
                    ? "bg-[#0F172A] text-white shadow-xs"
                    : "text-slate-600 hover:text-[#0F172A]"
                }`}
              >
                {range}
              </button>
            ))}
          </div>

          <button
            onClick={() => {
              setEditingTransaction(null);
              setIsModalOpen(true);
            }}
            className="btn-pill-black text-xs cursor-pointer flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Record Spend / Income</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Inflow */}
        <div className="getquin-card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Inflow</span>
            <div className="p-1.5 bg-emerald-50 text-emerald-600 rounded-lg">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-[#0F172A] tabular-nums font-mono">
              {formatCleanMoney(summary?.total_income || 0, "EUR")}
            </div>
            <p className="text-[11px] font-semibold text-emerald-600 mt-1 flex items-center gap-1">
              <span>↗</span> Salary, Freelancing & Dividends
            </p>
          </div>
        </div>

        {/* Total Expenses */}
        <div className="getquin-card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Expenses</span>
            <div className="p-1.5 bg-rose-50 text-rose-600 rounded-lg">
              <TrendingDown className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-[#0F172A] tabular-nums font-mono">
              {formatCleanMoney(summary?.total_expenses || 0, "EUR")}
            </div>
            <p className="text-[11px] font-semibold text-rose-600 mt-1 flex items-center gap-1">
              <span>↘</span> Outflows & Lifestyle Spends
            </p>
          </div>
        </div>

        {/* Net Savings Buffer */}
        <div className="getquin-card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Net Retained Cash</span>
            <div className="p-1.5 bg-blue-50 text-blue-600 rounded-lg">
              <Wallet className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-[#0F172A] tabular-nums font-mono">
              {formatCleanMoney(summary?.net_savings || 0, "EUR")}
            </div>
            <p className="text-[11px] font-semibold text-slate-500 mt-1">
              Savings Rate: <span className="font-bold text-[#0F172A]">{summary?.savings_rate_pct || 0}%</span>
            </p>
          </div>
        </div>

        {/* Budget Allocation (Needs vs Wants) */}
        <div className="getquin-card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Classification Split</span>
            <div className="p-1.5 bg-purple-50 text-purple-600 rounded-lg">
              <PiggyBank className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-semibold">
              <span className="text-emerald-700">Essential (Needs):</span>
              <span className="font-mono font-bold text-[#0F172A]">{formatCurrency(labelTotals["ESSENTIAL"] || 0, "EUR")}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-semibold">
              <span className="text-amber-700">Discretionary (Wants):</span>
              <span className="font-mono font-bold text-[#0F172A]">{formatCurrency(labelTotals["DISCRETIONARY"] || 0, "EUR")}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-semibold">
              <span className="text-pink-700">Luxury:</span>
              <span className="font-mono font-bold text-[#0F172A]">{formatCurrency(labelTotals["LUXURY"] || 0, "EUR")}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sankey Flow Diagram Card */}
      <div className="getquin-card p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              <span>Cashflow Sankey Flow Diagram</span>
              <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-emerald-50 text-emerald-700 rounded-md">
                Interactive Ribbons
              </span>
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Visualize how income flows from source channels into budget labels and deep categories
            </p>
          </div>

          {/* Sankey Depth & Investment Controls */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Depth 1 to 5 Picker */}
            <div className="flex items-center gap-1 bg-[#F1F5F9] p-1 rounded-xl">
              <span className="text-[11px] font-bold text-slate-500 px-2">Layers:</span>
              {[1, 2, 3, 4, 5].map((d) => (
                <button
                  key={d}
                  onClick={() => setSankeyDepth(d)}
                  className={`w-7 h-7 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center justify-center ${
                    sankeyDepth === d
                      ? "bg-[#0F172A] text-white shadow-xs"
                      : "text-slate-600 hover:text-black"
                  }`}
                  title={`Level ${d} Depth`}
                >
                  {d}
                </button>
              ))}
            </div>

            {/* Include Investment Cashflows Toggle */}
            <label className="flex items-center gap-2 text-xs font-bold text-slate-700 cursor-pointer bg-slate-50 px-2.5 py-1.5 rounded-xl border border-slate-200">
              <input
                type="checkbox"
                checked={includeInvestments}
                onChange={(e) => setIncludeInvestments(e.target.checked)}
                className="w-3.5 h-3.5 accent-blue-600 rounded cursor-pointer"
              />
              <span>Include Dividends & Portfolio Sales</span>
            </label>
          </div>
        </div>

        {/* Render Sankey SVG */}
        <SankeyChart data={sankeyData} loading={loadingSankey} />
      </div>

      {/* Cashflow Transaction Ledger */}
      <div className="getquin-card p-5 space-y-4">
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
                <th className="pb-2.5 font-bold">Category & Splits</th>
                <th className="pb-2.5 font-bold text-right">Total Amount</th>
                <th className="pb-2.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {filteredTransactions.map((tx) => {
                const isIncome = tx.items.some((i) => i.category_type === "INCOME");
                return (
                  <tr key={tx.cashflow_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 font-semibold text-slate-500 tabular-nums whitespace-nowrap">
                      {tx.transaction_date}
                    </td>

                    <td className="py-3 font-bold text-[#0F172A]">
                      <div>{tx.title}</div>
                      {tx.notes && <div className="text-[10px] text-slate-400 font-normal mt-0.5">{tx.notes}</div>}
                    </td>

                    <td className="py-3">
                      <div className="flex flex-col gap-1">
                        {tx.payments.map((p, pIdx) => (
                          <div key={pIdx} className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700">
                            <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                            <span>{p.account_name}</span>
                            {tx.payments.length > 1 && (
                              <span className="font-mono text-slate-400 tabular-nums">
                                ({formatCurrency(p.amount, "EUR")})
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </td>

                    <td className="py-3">
                      <div className="flex flex-col gap-1.5">
                        {tx.items.map((itm, iIdx) => {
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
                                <span className="font-mono font-bold text-slate-500 text-[11px] tabular-nums">
                                  {formatCurrency(itm.amount, "EUR")}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </td>

                    <td className="py-3 text-right font-mono font-bold tabular-nums">
                      <span className={isIncome ? "text-emerald-600" : "text-[#0F172A]"}>
                        {isIncome ? "+" : ""}{formatCurrency(tx.total_amount, "EUR")}
                      </span>
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
                  <td colSpan={6} className="py-8 text-center text-slate-400 font-semibold">
                    No cashflow records found for the selected criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cashflow Entry & Edit Modal */}
      <CashflowModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingTransaction(null);
        }}
        onSuccess={() => {
          loadData();
          loadSankey();
        }}
        initialData={editingTransaction}
      />
    </div>
  );
}
