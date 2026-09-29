import os

content = """import React, { useState, useMemo, useEffect } from "react";
import { formatCurrency } from "@/lib/format";
import { 
  Edit, Trash2, RefreshCw, ShoppingBag, Briefcase, 
  ArrowRightLeft, CreditCard, ChevronRight, CheckCircle2,
  AlertCircle
} from "lucide-react";
import { CashflowTransactionItem } from "@/components/CashflowModal";
import { TransactionItem } from "@/components/TransactionModal";

export interface UnifiedRowItem {
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
    holding_delta?: string;
    running_balance_after?: number;
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
  runningBalancesAfter?: Record<number, number>;
  primaryBalanceAfter?: {
    account_id: number;
    account_name: string;
    currency: string;
    balance: number;
  };
}

interface TransactionLedgerProps {
  transactions: UnifiedRowItem[];
  loading?: boolean;
  masterCurrency?: string;
  showRunningBalance?: boolean;
  selectedAccountIds?: number[];
  onEditCashflow?: (tx: CashflowTransactionItem) => void;
  onDeleteCashflow?: (id: number) => void;
  onEditTrade?: (tx: TransactionItem) => void;
  onDeleteTrade?: (id: number) => void;
}

function groupTransactionsByDate(transactions: UnifiedRowItem[]) {
  const grouped: Record<string, UnifiedRowItem[]> = {};
  transactions.forEach(tx => {
    if (!grouped[tx.date]) grouped[tx.date] = [];
    grouped[tx.date].push(tx);
  });
  return Object.keys(grouped)
    .sort((a, b) => b.localeCompare(a))
    .map(date => ({
      date,
      transactions: grouped[date]
    }));
}

function formatDateHeader(dateStr: string) {
  const today = new Date();
  const txDate = new Date(dateStr);
  today.setHours(0, 0, 0, 0);
  txDate.setHours(0, 0, 0, 0);
  const diffTime = today.getTime() - txDate.getTime();
  const diffDays = Math.round(diffTime / (1000 * 3600 * 24));
  
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return txDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: txDate.getFullYear() !== today.getFullYear() ? 'numeric' : undefined });
}

export function TransactionLedger({
  transactions,
  loading = false,
  masterCurrency = "EUR",
  showRunningBalance = false,
  selectedAccountIds = [],
  onEditCashflow,
  onDeleteCashflow,
  onEditTrade,
  onDeleteTrade
}: TransactionLedgerProps) {
  const [selectedTxKey, setSelectedTxKey] = useState<string | null>(null);

  const groupedTransactions = useMemo(() => groupTransactionsByDate(transactions), [transactions]);

  useEffect(() => {
    if (transactions.length > 0 && (!selectedTxKey || !transactions.find(t => t.key === selectedTxKey))) {
      setSelectedTxKey(transactions[0].key);
    } else if (transactions.length === 0) {
      setSelectedTxKey(null);
    }
  }, [transactions, selectedTxKey]);

  if (loading) {
    return (
      <div className="py-12 text-center text-slate-400 font-semibold w-full">
        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
        Loading ledger...
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="py-12 text-center text-slate-400 font-medium text-xs w-full">
        No transactions recorded for this period.
      </div>
    );
  }

  const selectedTx = transactions.find(t => t.key === selectedTxKey) || transactions[0];

  return (
    <div className="flex flex-col md:flex-row border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-slate-900 min-h-[500px]">
      
      {/* LEFT PANE: List (1/3 width) */}
      <div className="w-full md:w-1/3 border-r border-slate-200 dark:border-slate-800 flex flex-col max-h-[700px] overflow-y-auto bg-slate-50/50 dark:bg-slate-900/50">
        {groupedTransactions.map((group) => (
          <div key={group.date} className="flex flex-col">
            <div className="sticky top-0 bg-slate-100/90 dark:bg-slate-800/90 backdrop-blur-sm z-10 text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase px-3 py-1.5 border-b border-slate-200 dark:border-slate-800">
              {formatDateHeader(group.date)}
            </div>
            
            <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800/50">
              {group.transactions.map((tx) => {
                const isSelected = selectedTxKey === tx.key;
                
                let Icon = ShoppingBag;
                let iconColor = "text-slate-500 dark:text-slate-400";
                
                if (tx.source === "investment") {
                  Icon = Briefcase;
                  iconColor = "text-blue-500 dark:text-blue-400";
                } else if (tx.isTransfer) {
                  Icon = ArrowRightLeft;
                  iconColor = "text-slate-500 dark:text-slate-400";
                } else if (tx.isIncome) {
                  iconColor = "text-emerald-500 dark:text-emerald-400";
                }

                return (
                  <button
                    key={tx.key}
                    onClick={() => setSelectedTxKey(tx.key)}
                    className={`flex items-center gap-3 p-3 text-left transition-colors hover:bg-white dark:hover:bg-slate-800 ${
                      isSelected ? "bg-white dark:bg-slate-800 shadow-sm relative" : ""
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-full" />
                    )}
                    
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-slate-100 dark:bg-slate-800 shrink-0 ${iconColor}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
                        {tx.title}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400 truncate">
                        {tx.items[0]?.category_name || "Uncategorized"}
                      </div>
                    </div>
                    
                    <div className={`text-sm font-bold tabular-nums whitespace-nowrap ${
                      tx.isTransfer ? "text-slate-700 dark:text-slate-300" : tx.isIncome ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-slate-100"
                    }`}>
                      {tx.isIncome ? "+" : "-"}{formatCurrency(tx.totalAmount, tx.currency)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* RIGHT PANE: Detail (2/3 width) */}
      <div className="w-full md:w-2/3 flex flex-col bg-white dark:bg-slate-900 max-h-[700px]">
        {selectedTx ? (
          <div className="flex flex-col h-full">
            <div className="flex items-start justify-between p-6 border-b border-slate-100 dark:border-slate-800 shrink-0">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full flex items-center justify-center bg-slate-100 dark:bg-slate-800 shrink-0">
                  {selectedTx.source === "investment" ? <Briefcase className="w-6 h-6 text-blue-500" /> : selectedTx.isTransfer ? <ArrowRightLeft className="w-6 h-6 text-slate-500" /> : selectedTx.isIncome ? <ShoppingBag className="w-6 h-6 text-emerald-500" /> : <ShoppingBag className="w-6 h-6 text-slate-500" />}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                    {selectedTx.title}
                  </h2>
                  <div className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {new Date(selectedTx.date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                  </div>
                </div>
              </div>
              <div className={`text-2xl font-black tabular-nums ${
                selectedTx.isTransfer ? "text-slate-700 dark:text-slate-300" : selectedTx.isIncome ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
              }`}>
                {selectedTx.isIncome ? "+" : "-"}{formatCurrency(selectedTx.totalAmount, selectedTx.currency)}
              </div>
            </div>

            <div className="p-6 overflow-y-auto space-y-8 flex-1">
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Item Breakdown
                </h3>
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 space-y-3 border border-slate-100 dark:border-slate-800">
                  {selectedTx.items.map((itm, i) => (
                    <div key={i} className="flex justify-between items-start">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{itm.category_name}</span>
                        {itm.description && <span className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{itm.description}</span>}
                        {itm.effective_label && (
                          <span className="mt-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 w-fit">
                            {itm.effective_label}
                          </span>
                        )}
                      </div>
                      <span className="font-medium text-slate-700 dark:text-slate-300 tabular-nums">
                        {formatCurrency(itm.amount, selectedTx.currency)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <CreditCard className="w-3.5 h-3.5" /> Payment Accounts
                </h3>
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 space-y-3 border border-slate-100 dark:border-slate-800">
                  {selectedTx.payments.map((p, i) => (
                    <div key={i} className="flex justify-between items-start">
                      <span className="font-semibold text-slate-800 dark:text-slate-200">{p.account_name}</span>
                      <div className="flex flex-col items-end">
                        {p.holding_delta ? (
                          <span className="font-bold text-blue-600 dark:text-blue-400">{p.holding_delta}</span>
                        ) : (
                          <span className={`font-medium tabular-nums ${p.amount >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                            {p.amount >= 0 ? "+" : ""}{formatCurrency(p.amount, p.account_currency)}
                          </span>
                        )}
                        {showRunningBalance && p.running_balance_after !== undefined && (
                          <span className="text-[10px] text-slate-400 mt-0.5">Balance: {formatCurrency(p.running_balance_after, p.account_currency)}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {selectedTx.notes && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                    <AlertCircle className="w-3.5 h-3.5" /> Notes
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-300 bg-amber-50 dark:bg-amber-900/10 p-3 rounded-lg border border-amber-100 dark:border-amber-900/30">
                    {selectedTx.notes}
                  </p>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex items-center justify-end gap-3 shrink-0">
              {selectedTx.source === "cashflow" && selectedTx.rawCashflow && (
                <>
                  <button onClick={() => onDeleteCashflow?.(selectedTx.rawCashflow!.cashflow_id)} className="px-4 py-2 text-sm font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 rounded-lg transition-colors flex items-center gap-2">
                    <Trash2 className="w-4 h-4" /> Delete
                  </button>
                  <button onClick={() => onEditCashflow?.(selectedTx.rawCashflow!)} className="px-4 py-2 text-sm font-bold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors flex items-center gap-2">
                    <Edit className="w-4 h-4" /> Edit Cashflow
                  </button>
                </>
              )}
              {selectedTx.source === "investment" && selectedTx.rawTrade && (
                <>
                  <button onClick={() => onDeleteTrade?.(selectedTx.rawTrade!.transaction_id)} className="px-4 py-2 text-sm font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 rounded-lg transition-colors flex items-center gap-2">
                    <Trash2 className="w-4 h-4" /> Delete
                  </button>
                  <button onClick={() => onEditTrade?.(selectedTx.rawTrade!)} className="px-4 py-2 text-sm font-bold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors flex items-center gap-2">
                    <Edit className="w-4 h-4" /> Edit Trade
                  </button>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
            <ShoppingBag className="w-12 h-12 mb-4 text-slate-200 dark:text-slate-700" />
            <p>Select a transaction to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}
"""

with open("frontend/src/components/TransactionLedger.tsx", "w") as f:
    f.write(content)
