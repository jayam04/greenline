"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney } from "@/lib/format";
import { TransactionModal, TransactionItem } from "@/components/TransactionModal";
import { 
  Plus, Search, ArrowRight, ArrowLeft, MoreVertical, 
  Edit, Trash2, Info, ArrowUpRight, ArrowDownRight, RefreshCw
} from "lucide-react";

interface Transaction {
  transaction_id: number;
  account_id: number;
  funding_account_id?: number | null;
  funding_account_name?: string | null;
  funding_account_currency?: string | null;
  asset_id: number | null;
  account_name: string;
  account_currency?: string;
  asset_symbol: string;
  asset_name: string;
  transaction_type: string;
  transaction_date: string;
  quantity: number | null;
  price_per_unit: number | null;
  total_amount: number;
  fees: number;
  taxes: number;
  notes: string | null;
}

interface PortfolioSummary {
  total_net_worth: number;
  total_invested: number;
  total_current_value: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  portfolio_xirr: number | null;
}

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<TransactionItem | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  useEffect(() => {
    document.title = "Transactions · greenline";
    loadTransactions();
  }, []);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const [txData, sumData] = await Promise.all([
        apiFetch<Transaction[]>("/transactions?limit=500"),
        apiFetch<PortfolioSummary>("/portfolio/summary"),
      ]);
      setTransactions(txData || []);
      setSummary(sumData);
    } catch (e) {
      console.error("Failed to load transactions:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (tx: Transaction) => {
    setEditingTransaction(tx);
    setIsModalOpen(true);
  };

  const handleDelete = async (transactionId: number) => {
    if (!confirm("Are you sure you want to delete this transaction? This will recalculate lots and net worth.")) {
      return;
    }
    try {
      await apiFetch(`/transactions/${transactionId}`, { method: "DELETE" });
      loadTransactions();
    } catch (e: any) {
      alert(e.message || "Failed to delete transaction");
    }
  };

  // Filter transactions
  const filtered = transactions.filter((t) => {
    if (filterType !== "all" && t.transaction_type.toLowerCase() !== filterType) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const sym = (t.asset_symbol || "").toLowerCase();
      const name = (t.asset_name || "").toLowerCase();
      const acc = (t.account_name || "").toLowerCase();
      const notes = (t.notes || "").toLowerCase();
      return sym.includes(q) || name.includes(q) || acc.includes(q) || notes.includes(q);
    }
    return true;
  });

  // Group transactions by Month Year (e.g. "August 2026", "January 2026")
  const groupedTransactions: Record<string, Transaction[]> = {};
  filtered.forEach((tx) => {
    const parts = (tx.transaction_date || "").split("-");
    let monthYear = "Recent";
    if (parts.length === 3) {
      const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      monthYear = d.toLocaleString("default", { month: "long", year: "numeric" });
    }
    if (!groupedTransactions[monthYear]) {
      groupedTransactions[monthYear] = [];
    }
    groupedTransactions[monthYear].push(tx);
  });

  const formatDayDate = (dateStr: string) => {
    const parts = (dateStr || "").split("-");
    if (parts.length === 3) {
      return `${parts[2]}.${parts[1]}`;
    }
    return dateStr;
  };

  const totalPnL = (summary?.total_unrealized_pnl || 0) + (summary?.total_realized_pnl || 0);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT COLUMN: Month-Grouped Transactions Ledger (~68% width) */}
        <div className="lg:col-span-8 space-y-5">
          <div className="getquin-card p-5">
            {/* Header: Title & Add Transaction */}
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[#0F172A]">Transactions</h2>
                <span className="text-[11px] font-bold text-slate-400">
                  ({transactions.length} total)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={loadTransactions}
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                  title="Reload Transactions"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-600" : ""}`} />
                </button>
                <button
                  onClick={() => {
                    setEditingTransaction(null);
                    setIsModalOpen(true);
                  }}
                  className="btn-pill-black text-[11px]"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add transaction</span>
                </button>
              </div>
            </div>

            {/* Search & Filter Bar */}
            <div className="py-3 flex items-center gap-3 border-b border-[#F1F5F9]">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search asset, symbol, account, or notes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-xs font-semibold text-slate-800 placeholder-slate-400 pl-9 pr-4 py-2 rounded-lg border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none transition-all"
                />
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="bg-[#F3F4F6] text-xs font-bold text-slate-700 px-3 py-2 rounded-lg border border-transparent focus:outline-none cursor-pointer"
                >
                  <option value="all">All Types</option>
                  <option value="buy">Buys</option>
                  <option value="sell">Sells</option>
                  <option value="dividend">Dividends</option>
                  <option value="deposit">Deposits</option>
                  <option value="withdrawal">Withdrawals</option>
                </select>
              </div>
            </div>

            {/* Month-Grouped Transaction List */}
            <div className="divide-y divide-slate-100">
              {Object.keys(groupedTransactions).length > 0 ? (
                Object.entries(groupedTransactions).map(([monthYear, txList]) => (
                  <div key={monthYear} className="py-3.5">
                    {/* Month Year Header */}
                    <div className="text-xs font-bold text-slate-400 mb-2">
                      {monthYear}
                    </div>

                    {/* Transaction Rows */}
                    <div className="space-y-1">
                      {txList.map((tx) => {
                        const isBuy = tx.transaction_type.toLowerCase() === "buy";
                        const isSell = tx.transaction_type.toLowerCase() === "sell";
                        const isDeposit = tx.transaction_type.toLowerCase() === "deposit";
                        const isDividend = tx.transaction_type.toLowerCase() === "dividend";
                        const curr = tx.account_currency || "USD";

                        const initials = tx.asset_symbol
                          ? tx.asset_symbol.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase()
                          : (tx.transaction_type.slice(0, 3).toUpperCase());

                        return (
                          <div
                            key={tx.transaction_id}
                            className="flex items-center justify-between py-2.5 px-2 rounded-xl hover:bg-slate-50 transition-colors group"
                          >
                            {/* Left: Date + Arrow + Avatar + Asset Description */}
                            <div className="flex items-center gap-3 min-w-0">
                              {/* Date with Direction Arrow */}
                              <div className="w-12 text-[11px] font-bold text-slate-700 flex items-center gap-1 tabular-nums shrink-0">
                                <span>{formatDayDate(tx.transaction_date)}</span>
                                {isBuy || isDeposit ? (
                                  <ArrowRight className="w-3 h-3 text-slate-400" />
                                ) : (
                                  <ArrowLeft className="w-3 h-3 text-slate-400" />
                                )}
                              </div>

                              {/* Ticker Avatar Badge */}
                              <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-800 font-extrabold text-[10px] flex items-center justify-center border border-slate-200/80 shrink-0">
                                {initials}
                              </div>

                              {/* Asset Title & Transaction Subtitle */}
                              <div className="truncate">
                                <div className="font-bold text-[#0F172A] text-xs truncate">
                                  {tx.asset_name || tx.asset_symbol || tx.account_name || "Cash Entry"}
                                </div>
                                <div className="text-[11px] font-medium text-slate-400 mt-0.5 truncate">
                                  {isBuy && `Bought x${formatQty(tx.quantity || 0)} at ${formatMoney(tx.price_per_unit, curr)}`}
                                  {isSell && `Sold x${formatQty(tx.quantity || 0)} at ${formatMoney(tx.price_per_unit, curr)}`}
                                  {isDividend && `Dividend received`}
                                  {isDeposit && `Deposit into ${tx.account_name || "account"}`}
                                  {tx.transaction_type.toLowerCase() === "withdrawal" && `Withdrawal from ${tx.account_name || "account"}`}
                                </div>
                              </div>
                            </div>

                            {/* Right: Total Amount & Action Menu */}
                            <div className="flex items-center gap-3 shrink-0 tabular-nums">
                              <div className="text-right">
                                <div className="font-extrabold text-xs text-[#0F172A]">
                                  {formatMoney(tx.total_amount, curr)}
                                </div>
                                <div className="text-[10px] font-semibold text-slate-400">
                                  {tx.funding_account_name && tx.funding_account_name !== tx.account_name
                                    ? `${tx.account_name} • via ${tx.funding_account_name}`
                                    : (tx.funding_account_name || tx.account_name || "Account")}
                                </div>
                              </div>

                              <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                                <button
                                  onClick={() => handleEdit(tx)}
                                  className="p-1 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-200/60 transition-colors"
                                  title="Edit"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDelete(tx.transaction_id)}
                                  className="p-1 text-rose-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors"
                                  title="Delete"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-12 text-center text-slate-400 font-medium text-xs">
                  {loading ? (
                    "Loading transactions..."
                  ) : (
                    <div>
                      <p className="mb-3">No transactions found.</p>
                      <button
                        onClick={() => {
                          setEditingTransaction(null);
                          setIsModalOpen(true);
                        }}
                        className="btn-pill-black text-xs"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add your first transaction</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Performance & Capital Summary Widget (~32% width) */}
        <div className="lg:col-span-4 space-y-5">
          <div className="getquin-card p-5">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">Performance</h3>
                <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                  PRO
                </span>
              </div>
            </div>

            <div className="space-y-4 pt-3 text-xs">
              {/* Capital */}
              <div>
                <h4 className="font-bold text-[#0F172A] text-xs mb-2">Capital</h4>
                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    Invested capital <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className="font-bold text-[#0F172A] tabular-nums">
                    ${formatNum(summary?.total_invested || 0, 2)}
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
                        {formatMoney(summary?.total_unrealized_pnl || 0, "USD", 2, true)}
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
                        {formatMoney(summary?.total_realized_pnl || 0, "USD", 2, true)}
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
                    {totalPnL >= 0 ? "↗" : "↘"} {formatMoney(totalPnL, "USD", 2, true)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 text-slate-600">
                  <span className="flex items-center gap-1">
                    Internal rate of return (IRR) <Info className="w-3 h-3 text-slate-400" />
                  </span>
                  <span className="font-extrabold text-[#16A34A] tabular-nums">
                    {summary?.portfolio_xirr != null ? `↗ ${(summary.portfolio_xirr * 100).toFixed(2)}%` : "0.00%"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadTransactions}
        initialData={editingTransaction}
      />
    </div>
  );
}
