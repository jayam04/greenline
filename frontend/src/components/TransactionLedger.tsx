import React, { useState, useMemo } from "react";
import { formatCurrency, convertCurrency } from "@/lib/format";
import { 
  Edit, Trash2, RefreshCw, ChevronDown, ChevronUp, 
  ShoppingBag, Briefcase, ArrowRightLeft, CreditCard,
  MoreHorizontal
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
  selectedAccountId?: string;
  onEditCashflow?: (tx: CashflowTransactionItem) => void;
  onDeleteCashflow?: (id: number) => void;
  onEditTrade?: (tx: TransactionItem) => void;
  onDeleteTrade?: (id: number) => void;
}

// Group transactions by date
function groupTransactionsByDate(transactions: UnifiedRowItem[]) {
  const grouped: Record<string, UnifiedRowItem[]> = {};
  transactions.forEach(tx => {
    if (!grouped[tx.date]) grouped[tx.date] = [];
    grouped[tx.date].push(tx);
  });
  // Sort dates descending
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
  
  // Reset time to compare dates only
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
  selectedAccountId = "ALL",
  onEditCashflow,
  onDeleteCashflow,
  onEditTrade,
  onDeleteTrade
}: TransactionLedgerProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const groupedTransactions = useMemo(() => groupTransactionsByDate(transactions), [transactions]);

  const toggleRow = (key: string) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) newSet.delete(key);
      else newSet.add(key);
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="py-12 text-center text-slate-400 font-semibold">
        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-400" />
        Loading transactions ledger...
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="py-12 text-center text-slate-400 font-medium text-xs">
        No transactions recorded for this period.
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-6">
      {groupedTransactions.map((group) => (
        <div key={group.date} className="flex flex-col space-y-2">
          {/* Date Header */}
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider px-2">
            {formatDateHeader(group.date)}
          </div>
          
          {/* Transaction List */}
          <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden divide-y divide-slate-100">
            {group.transactions.map((tx) => {
              const isExpanded = expandedRows.has(tx.key);
              const hasSplits = tx.items.length > 1 || tx.payments.length > 1;
              
              // Primary Icon
              let Icon = ShoppingBag;
              let iconBg = "bg-slate-100 text-slate-500";
              
              if (tx.source === "investment") {
                Icon = Briefcase;
                iconBg = "bg-blue-50 text-blue-600";
              } else if (tx.isTransfer) {
                Icon = ArrowRightLeft;
                iconBg = "bg-slate-100 text-slate-600";
              } else if (tx.isIncome) {
                iconBg = "bg-emerald-50 text-emerald-600";
              }

              // Payment Account Display
              let paymentDisplay = "";
              if (tx.payments.length === 1) {
                paymentDisplay = tx.payments[0].account_name;
              } else if (tx.payments.length > 1) {
                paymentDisplay = "Multiple Accounts";
              }

              // Running Balance Display
              let runningBalanceDisplay = null;
              if (showRunningBalance && selectedAccountId !== "ALL") {
                const aid = Number(selectedAccountId);
                const bal = tx.runningBalancesAfter?.[aid];
                if (bal !== undefined) {
                  const acc = tx.payments.find(p => p.account_id === aid);
                  const curr = acc?.account_currency || masterCurrency;
                  runningBalanceDisplay = formatCurrency(bal, curr);
                }
              } else if (showRunningBalance && tx.primaryBalanceAfter) {
                runningBalanceDisplay = formatCurrency(tx.primaryBalanceAfter.balance, tx.primaryBalanceAfter.currency);
              }

              // Label Badges
              const labelBadges = tx.items
                .map(i => i.effective_label)
                .filter((v, i, a) => v && a.indexOf(v) === i);

              return (
                <div key={tx.key} className="flex flex-col hover:bg-slate-50/80 transition-colors">
                  {/* Primary Row (Responsive Grid) */}
                  <div 
                    className="grid grid-cols-12 items-center p-4 cursor-pointer select-none group"
                    onClick={() => hasSplits && toggleRow(tx.key)}
                  >
                    {/* Col 1: Icon & Title (Spans 8 cols on mobile, 4 on desktop) */}
                    <div className="col-span-8 md:col-span-4 flex items-center gap-3.5 min-w-0 pr-4">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${iconBg}`}>
                        <Icon className="w-4.5 h-4.5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <div className="font-bold text-[#0F172A] truncate text-sm">
                          {tx.title}
                        </div>
                        {/* Mobile shows category/account below title, Desktop hides it */}
                        <div className="md:hidden text-xs text-slate-500 truncate flex items-center gap-1.5 mt-0.5">
                          <span>{tx.items[0]?.category_name || "Uncategorized"}</span>
                          {paymentDisplay && (
                            <>
                              <span className="w-1 h-1 bg-slate-300 rounded-full" />
                              <span className="flex items-center gap-1">
                                <CreditCard className="w-3 h-3" />
                                <span className="truncate">{paymentDisplay}</span>
                              </span>
                            </>
                          )}
                        </div>
                        {/* Desktop shows notes (if any) below title */}
                        <div className="hidden md:block text-xs text-slate-500 truncate mt-0.5">
                          {tx.notes ? tx.notes : <span className="text-transparent select-none">No notes</span>}
                        </div>
                      </div>
                    </div>

                    {/* Col 2: Category & Labels (Spans 3 cols, hidden on mobile) */}
                    <div className="hidden md:flex col-span-3 flex-col items-start pr-4 min-w-0">
                      <div className="text-sm text-slate-700 truncate w-full">
                        {tx.items[0]?.category_name || "Uncategorized"}
                      </div>
                      <div className="flex gap-1 mt-0.5">
                        {labelBadges.map((lbl, i) => (
                          <span key={i} className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            {lbl}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Col 3: Payment Account (Spans 2 cols, hidden on mobile) */}
                    <div className="hidden md:flex col-span-2 flex-col items-start pr-4 min-w-0">
                      <div className="flex items-center gap-1.5 text-sm text-slate-700 truncate w-full">
                        <CreditCard className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{paymentDisplay}</span>
                      </div>
                      {hasSplits && (
                        <div className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                          <span className="w-3 h-3 flex items-center justify-center bg-slate-200 rounded-sm text-[8px] font-bold">S</span> Split
                        </div>
                      )}
                    </div>

                    {/* Col 4: Actions & Amount (Spans 4 cols on mobile, 3 on desktop) */}
                    <div className="col-span-4 md:col-span-3 flex items-center justify-end gap-3 min-w-0">
                      
                      {/* Desktop Actions (visible on row hover) - Positioned BEFORE Amount */}
                      <div className="hidden md:flex opacity-0 group-hover:opacity-100 transition-opacity items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {tx.source === "cashflow" && tx.rawCashflow && (
                          <>
                            <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="p-1 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                              <Edit className="w-4 h-4" />
                            </button>
                            <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="p-1 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {tx.source === "investment" && tx.rawTrade && (
                          <>
                            <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="p-1 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                              <Edit className="w-4 h-4" />
                            </button>
                            <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="p-1 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>

                      {/* Amount & Balance */}
                      <div className="flex flex-col items-end shrink-0 pl-2">
                        <div className={`font-bold tabular-nums text-sm ${tx.isTransfer ? "text-[#0F172A]" : tx.isIncome ? "text-emerald-600" : "text-rose-600"}`}>
                          {tx.isIncome ? "+" : "-"}{formatCurrency(tx.totalAmount, tx.currency)}
                        </div>
                        
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {showRunningBalance && runningBalanceDisplay && (
                            <div className="text-[10px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                              Bal: {runningBalanceDisplay}
                            </div>
                          )}
                          
                          {hasSplits && (
                            <div className="text-slate-400 ml-1">
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Mobile Actions (Always visible below row on small screens) */}
                  <div className="md:hidden flex items-center justify-end gap-3 px-4 pb-3" onClick={(e) => e.stopPropagation()}>
                     {tx.source === "cashflow" && tx.rawCashflow && (
                        <>
                          <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                      {tx.source === "investment" && tx.rawTrade && (
                        <>
                          <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                  </div>

                  {/* Expanded Receipt View */}
                  {isExpanded && hasSplits && (
                    <div className="bg-slate-50 px-4 py-3 text-xs border-t border-slate-100">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Items Breakdown */}
                        {tx.items.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="font-bold text-slate-700 text-[10px] uppercase tracking-wider">Item Breakdown</h4>
                            <div className="space-y-1.5">
                              {tx.items.map((itm, iIdx) => (
                                <div key={iIdx} className="flex justify-between items-start">
                                  <div className="flex flex-col">
                                    <span className="font-semibold text-slate-800">{itm.category_name}</span>
                                    {itm.description && <span className="text-slate-500 text-[11px]">{itm.description}</span>}
                                  </div>
                                  <span className="font-medium tabular-nums text-slate-600">
                                    {formatCurrency(itm.amount, tx.currency)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Payments Breakdown */}
                        {tx.payments.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="font-bold text-slate-700 text-[10px] uppercase tracking-wider">Payment Accounts</h4>
                            <div className="space-y-1.5">
                              {tx.payments.map((p, pIdx) => (
                                <div key={pIdx} className="flex justify-between items-start">
                                  <span className="font-semibold text-slate-800">{p.account_name}</span>
                                  <div className="flex flex-col items-end">
                                    {p.holding_delta ? (
                                      <span className="font-bold text-blue-600">{p.holding_delta}</span>
                                    ) : (
                                      <span className={`font-medium tabular-nums ${p.amount >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                                        {p.amount >= 0 ? "+" : ""}{formatCurrency(p.amount, p.account_currency)}
                                      </span>
                                    )}
                                    {p.running_balance_after !== undefined && (
                                      <span className="text-[10px] text-slate-400">Bal: {formatCurrency(p.running_balance_after, p.account_currency)}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {tx.notes && (
                        <div className="mt-3 pt-3 border-t border-slate-200">
                          <h4 className="font-bold text-slate-700 text-[10px] uppercase tracking-wider mb-1">Notes</h4>
                          <p className="text-slate-600">{tx.notes}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
