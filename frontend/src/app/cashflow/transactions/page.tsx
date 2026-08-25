"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  ArrowLeftRight, Plus, Search, Trash2, Edit, 
  ShoppingBag, Briefcase, Layers, RefreshCw 
} from "lucide-react";
import { CashflowModal, CashflowTransactionItem } from "@/components/CashflowModal";
import { TransactionModal, TransactionItem } from "@/components/TransactionModal";
import { formatCurrency } from "@/lib/format";

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
  account_type: string;
}

type ViewMode = "DAY_TO_DAY" | "INVESTMENTS" | "BOTH";

interface UnifiedRowItem {
  key: string;
  source: "cashflow" | "investment";
  rawCashflow?: CashflowTransactionItem;
  rawTrade?: TransactionItem;
  date: string;
  title: string;
  notes?: string | null;
  payments: {
    account_id: number;
    account_name: string;
    account_currency: string;
    amount: number;
  }[];
  items: {
    category_name: string;
    category_type?: string;
    description?: string | null;
    effective_label?: string | null;
    amount: number;
  }[];
  isTransfer: boolean;
  isIncome: boolean;
  totalAmount: number;
  currency: string;
}

export default function CashflowTransactionsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("DAY_TO_DAY");
  const [cashflowTxs, setCashflowTxs] = useState<CashflowTransactionItem[]>([]);
  const [tradeTxs, setTradeTxs] = useState<TransactionItem[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>("ALL");
  const [selectedAccountId, setSelectedAccountId] = useState<string>("ALL");

  // Modals
  const [isCashflowModalOpen, setIsCashflowModalOpen] = useState(false);
  const [editingCashflowTx, setEditingCashflowTx] = useState<CashflowTransactionItem | null>(null);

  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);
  const [editingTradeTx, setEditingTradeTx] = useState<TransactionItem | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [cfRes, tradeRes, accRes] = await Promise.all([
        apiFetch<CashflowTransactionItem[]>("/cashflow"),
        apiFetch<TransactionItem[]>("/transactions"),
        apiFetch<Account[]>("/accounts"),
      ]);
      setCashflowTxs(cfRes || []);
      setTradeTxs(tradeRes || []);
      setAccounts(accRes || []);
    } catch (err) {
      console.error("Failed to load cashflow transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCashflow = async (id: number) => {
    if (!confirm("Are you sure you want to delete this transaction?")) return;
    try {
      await apiFetch(`/cashflow/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete transaction");
    }
  };

  const handleDeleteTrade = async (id: number) => {
    if (!confirm("Are you sure you want to delete this trade transaction?")) return;
    try {
      await apiFetch(`/transactions/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete transaction");
    }
  };

  // Convert raw records into standardized rows matching /cashflow table schema
  const unifiedRows = useMemo<UnifiedRowItem[]>(() => {
    const rows: UnifiedRowItem[] = [];

    // 1. Day-to-Day Cashflow
    if (viewMode === "DAY_TO_DAY" || viewMode === "BOTH") {
      cashflowTxs.forEach((cf) => {
        const isTransfer = cf.transaction_kind === "TRANSFER" || cf.items.some((i) => i.category_type === "TRANSFER");
        const isIncome = !isTransfer && cf.items.some((i) => i.category_type === "INCOME");

        rows.push({
          key: `cf-${cf.cashflow_id}`,
          source: "cashflow",
          rawCashflow: cf,
          date: cf.transaction_date,
          title: cf.title,
          notes: cf.notes,
          payments: cf.payments.map((p) => ({
            account_id: p.account_id,
            account_name: p.account_name || "Account",
            account_currency: p.account_currency || cf.currency || "EUR",
            amount: p.amount
          })),
          items: cf.items.map((i) => ({
            category_name: i.category_name || "Uncategorized",
            category_type: i.category_type,
            description: i.description,
            effective_label: i.effective_label || i.label || "DISCRETIONARY",
            amount: i.amount
          })),
          isTransfer,
          isIncome,
          totalAmount: cf.total_amount,
          currency: cf.currency || "EUR"
        });
      });
    }

    // 2. Investment Trades
    if (viewMode === "INVESTMENTS" || viewMode === "BOTH") {
      tradeTxs.forEach((t) => {
        const ttype = (t.transaction_type || "").toLowerCase();
        const isBuy = ttype === "buy";
        const isSell = ttype === "sell";
        const isDiv = ttype === "dividend";
        const isDeposit = ttype === "deposit";
        const isWithdrawal = ttype === "withdrawal";

        const isIncome = isSell || isDiv || isDeposit;
        const isTransfer = isDeposit || isWithdrawal;

        const holdingName = t.account_name || "Demat Account";
        const fundingName = t.funding_account_name || holdingName;

        const grossAmt = (t.quantity && t.price_per_unit) ? (t.quantity * t.price_per_unit) : t.total_amount;
        const fees = t.fees || 0;
        const taxes = t.taxes || 0;

        let netTotal = grossAmt;
        if (isBuy) {
          netTotal = grossAmt + fees + taxes;
        } else if (isSell) {
          netTotal = Math.max(0, grossAmt - fees - taxes);
        } else if (isDiv) {
          netTotal = Math.max(0, grossAmt - taxes);
        }

        const signedPaymentAmt = isIncome ? netTotal : -netTotal;

        const paymentsList = [];
        if (fundingName !== holdingName) {
          paymentsList.push({
            account_id: t.account_id,
            account_name: `${holdingName} (Holding)`,
            account_currency: t.account_currency || "USD",
            amount: 0
          });
          paymentsList.push({
            account_id: t.funding_account_id || t.account_id,
            account_name: fundingName,
            account_currency: t.funding_account_currency || t.account_currency || "USD",
            amount: signedPaymentAmt
          });
        } else {
          paymentsList.push({
            account_id: t.account_id,
            account_name: holdingName,
            account_currency: t.account_currency || "USD",
            amount: signedPaymentAmt
          });
        }

        let catName = "Stock & ETF Purchases";
        if (isSell) catName = "Stock Sale Proceeds";
        else if (isDiv) catName = "Dividends";
        else if (isDeposit || isWithdrawal) catName = "Account Transfers & FX";

        let tradeDesc = "";
        if (isBuy && t.quantity && t.price_per_unit) {
          tradeDesc = `Bought x${t.quantity} at ${formatCurrency(t.price_per_unit, t.account_currency || "USD")}`;
        } else if (isSell && t.quantity && t.price_per_unit) {
          tradeDesc = `Sold x${t.quantity} at ${formatCurrency(t.price_per_unit, t.account_currency || "USD")}`;
        } else if (isDiv) {
          tradeDesc = `Dividend Payout`;
        }

        const itemsList = [
          {
            category_name: catName,
            category_type: isIncome ? "INCOME" : "INVESTMENT",
            description: tradeDesc || t.notes || null,
            effective_label: "INVESTMENT",
            amount: grossAmt
          }
        ];

        if (fees > 0) {
          itemsList.push({
            category_name: "Investment Fees & Charges",
            category_type: "EXPENSE",
            description: "Brokerage & Platform Charges",
            effective_label: "ESSENTIAL",
            amount: fees
          });
        }

        if (taxes > 0) {
          itemsList.push({
            category_name: "Taxes & Duties",
            category_type: "EXPENSE",
            description: isDiv ? "Tax Withheld at Source (TDS)" : "Securities Transaction Tax & Duties",
            effective_label: "ESSENTIAL",
            amount: taxes
          });
        }

        rows.push({
          key: `trade-${t.transaction_id}`,
          source: "investment",
          rawTrade: t,
          date: t.transaction_date,
          title: t.asset_name || t.asset_symbol || `${ttype.toUpperCase()} Transaction`,
          notes: t.notes,
          payments: paymentsList,
          items: itemsList,
          isTransfer,
          isIncome,
          totalAmount: netTotal,
          currency: t.account_currency || "USD"
        });
      });
    }

    return rows.sort((a, b) => b.date.localeCompare(a.date));
  }, [cashflowTxs, tradeTxs, viewMode]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return unifiedRows.filter((tx) => {
      // Account filter
      if (selectedAccountId !== "ALL") {
        const accIdNum = Number(selectedAccountId);
        const matchAcc = tx.payments.some((p) => p.account_id === accIdNum);
        if (!matchAcc) return false;
      }

      // Label filter
      if (selectedLabelFilter !== "ALL") {
        const hasLabel = tx.items.some((i) => i.effective_label === selectedLabelFilter);
        if (!hasLabel) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = tx.title.toLowerCase().includes(q);
        const matchNotes = (tx.notes || "").toLowerCase().includes(q);
        const matchCats = tx.items.some(
          (i) =>
            i.category_name.toLowerCase().includes(q) ||
            (i.description && i.description.toLowerCase().includes(q))
        );
        const matchAccs = tx.payments.some((p) => p.account_name.toLowerCase().includes(q));
        if (!matchTitle && !matchNotes && !matchCats && !matchAccs) return false;
      }

      return true;
    });
  }, [unifiedRows, selectedAccountId, selectedLabelFilter, searchQuery]);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-8 space-y-6">
      
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl">
              <ArrowLeftRight className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-[#0F172A] dark:text-white tracking-tight">
              Cashflow Transactions
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Historical ledger with split payment methods, multi-category itemization, and investment cash flows
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setEditingTradeTx(null);
              setIsTradeModalOpen(true);
            }}
            className="px-3 py-2 text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Briefcase className="w-3.5 h-3.5 text-blue-500" />
            <span>+ Record Trade / SIP</span>
          </button>

          <button
            onClick={() => {
              setEditingCashflowTx(null);
              setIsCashflowModalOpen(true);
            }}
            className="px-3.5 py-2 text-xs font-bold bg-[#0F172A] hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-[#0F172A] rounded-xl transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span>+ Record Cashflow</span>
          </button>
        </div>
      </div>

      {/* Main Card with Table matching /cashflow exact layout */}
      <div className="getquin-card p-5 space-y-4">
        
        {/* Table Header Bar with Mode Selector & Filters */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
              Income & Spend Transactions ({filteredRows.length})
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Historical ledger with split payment methods and multi-category itemization
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* 3-Way Mode Selector */}
            <div className="inline-flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-bold">
              <button
                onClick={() => setViewMode("DAY_TO_DAY")}
                className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                  viewMode === "DAY_TO_DAY"
                    ? "bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white"
                }`}
              >
                <ShoppingBag className="w-3.5 h-3.5 text-emerald-400" />
                <span>Day-to-Day</span>
              </button>

              <button
                onClick={() => setViewMode("INVESTMENTS")}
                className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                  viewMode === "INVESTMENTS"
                    ? "bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white"
                }`}
              >
                <Briefcase className="w-3.5 h-3.5 text-blue-400" />
                <span>Investments</span>
              </button>

              <button
                onClick={() => setViewMode("BOTH")}
                className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                  viewMode === "BOTH"
                    ? "bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white"
                }`}
              >
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                <span>Combined (Both)</span>
              </button>
            </div>

            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Search merchant, account, category..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#F3F4F6] dark:bg-slate-800 text-xs font-semibold text-slate-800 dark:text-slate-100 placeholder-slate-400 pl-8 pr-3 py-1.5 rounded-lg border border-transparent focus:border-slate-300 dark:focus:border-slate-700 focus:bg-white dark:focus:bg-slate-900 focus:outline-none w-52"
              />
            </div>

            {/* Account Selector Filter */}
            <select
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
              className="bg-[#F1F5F9] dark:bg-slate-800 text-xs font-bold text-slate-700 dark:text-slate-200 px-2.5 py-1.5 rounded-lg border border-transparent focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Accounts</option>
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>
                  {a.account_name} ({a.currency})
                </option>
              ))}
            </select>

            {/* Label Filter Pills */}
            <div className="flex items-center bg-[#F1F5F9] dark:bg-slate-800 p-1 rounded-xl text-xs font-bold">
              {["ALL", "ESSENTIAL", "DISCRETIONARY", "LUXURY", "INVESTMENT"].map((lbl) => (
                <button
                  key={lbl}
                  onClick={() => setSelectedLabelFilter(lbl)}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    selectedLabelFilter === lbl
                      ? "bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] shadow-xs"
                      : "text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white"
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
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 text-[11px] font-bold uppercase tracking-wider">
                <th className="pb-2.5 font-bold">Date</th>
                <th className="pb-2.5 font-bold">Title / Merchant</th>
                <th className="pb-2.5 font-bold">Payment Method(s)</th>
                <th className="pb-2.5 font-bold">Category & Description</th>
                <th className="pb-2.5 font-bold text-right">Total Amount</th>
                <th className="pb-2.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 font-semibold">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
                    Loading transactions ledger...
                  </td>
                </tr>
              ) : filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 font-medium text-xs">
                    No cashflow transactions recorded for this period.
                  </td>
                </tr>
              ) : (
                filteredRows.map((tx) => {
                  const isTransfer = tx.isTransfer;
                  const isIncome = tx.isIncome;

                  return (
                    <tr key={tx.key} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 font-semibold text-slate-500 dark:text-slate-400 tabular-nums whitespace-nowrap">
                        {tx.date}
                      </td>

                      <td className="py-3 font-bold text-[#0F172A] dark:text-white">
                        <div>{tx.title}</div>
                        {tx.notes && <div className="text-[10px] text-slate-400 font-normal mt-0.5">{tx.notes}</div>}
                      </td>

                      {/* Payment Method(s) with Green/Red Inflow/Outflow Dots */}
                      <td className="py-3">
                        <div className="flex flex-col gap-1">
                          {tx.payments.map((p, pIdx) => {
                            const pCurr = p.account_currency || tx.currency || "EUR";
                            const isCredit = p.amount > 0;
                            const dotColor = isCredit ? "bg-emerald-500" : p.amount < 0 ? "bg-rose-500" : "bg-blue-500";
                            const textColor = isCredit 
                              ? "text-emerald-600 dark:text-emerald-400" 
                              : p.amount < 0 
                              ? "text-rose-600 dark:text-rose-400" 
                              : "text-slate-400";
                            const signPrefix = isCredit ? "+" : p.amount < 0 ? "-" : "";

                            return (
                              <div key={pIdx} className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700 dark:text-slate-200">
                                <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                                <span>{p.account_name}</span>
                                {p.amount !== 0 && (
                                  <span className={`tabular-nums font-bold ${textColor}`}>
                                    ({signPrefix}{formatCurrency(Math.abs(p.amount), pCurr)})
                                  </span>
                                )}
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
                              <span className="font-bold text-slate-800 dark:text-slate-100 text-xs">
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
                              const lbl = itm.effective_label || "DISCRETIONARY";
                              const badgeColor =
                                lbl === "ESSENTIAL"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                                  : lbl === "LUXURY"
                                  ? "bg-pink-50 text-pink-700 border-pink-200 dark:bg-pink-950/40 dark:text-pink-300 dark:border-pink-800"
                                  : lbl === "INVESTMENT"
                                  ? "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800"
                                  : "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800";

                              return (
                                <div key={iIdx} className="flex items-center gap-2 flex-wrap">
                                  <span className="font-bold text-slate-800 dark:text-slate-100 text-xs">
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
                                        ? `- ${formatCurrency(Math.abs(itm.amount), tx.currency || "EUR")} (Reimbursement)`
                                        : formatCurrency(itm.amount, tx.currency || "EUR")}
                                    </span>
                                  )}
                                </div>
                              );
                            })
                          )}
                        </div>
                      </td>

                      {/* Total Amount Column */}
                      <td className="py-3 text-right font-bold tabular-nums">
                        <div className={isTransfer ? "text-[#0F172A] dark:text-white text-xs" : isIncome ? "text-emerald-600 dark:text-emerald-400 text-xs" : "text-rose-600 dark:text-rose-400 text-xs"}>
                          {formatCurrency(Math.abs(tx.totalAmount), tx.currency || "EUR")}
                        </div>
                      </td>

                      {/* Action Menu */}
                      <td className="py-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => {
                              if (tx.source === "cashflow" && tx.rawCashflow) {
                                setEditingCashflowTx(tx.rawCashflow);
                                setIsCashflowModalOpen(true);
                              } else if (tx.source === "investment" && tx.rawTrade) {
                                setEditingTradeTx(tx.rawTrade);
                                setIsTradeModalOpen(true);
                              }
                            }}
                            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                            title="Edit"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              if (tx.source === "cashflow" && tx.rawCashflow) {
                                handleDeleteCashflow(tx.rawCashflow.cashflow_id);
                              } else if (tx.source === "investment" && tx.rawTrade) {
                                handleDeleteTrade(tx.rawTrade.transaction_id);
                              }
                            }}
                            className="p-1.5 text-rose-400 hover:text-rose-600 dark:hover:text-rose-300 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modals */}
      <CashflowModal
        isOpen={isCashflowModalOpen}
        onClose={() => {
          setIsCashflowModalOpen(false);
          setEditingCashflowTx(null);
        }}
        onSuccess={loadData}
        initialData={editingCashflowTx}
      />

      <TransactionModal
        isOpen={isTradeModalOpen}
        onClose={() => {
          setIsTradeModalOpen(false);
          setEditingTradeTx(null);
        }}
        onSuccess={loadData}
        initialData={editingTradeTx}
      />
    </div>
  );
}
