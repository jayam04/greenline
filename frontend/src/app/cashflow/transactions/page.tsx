"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  ArrowLeftRight, Plus, Search, Trash2, Edit, 
  ShoppingBag, Briefcase, Layers, RefreshCw, Wallet 
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
  runningBalancesAfter: Record<number, number>;
  primaryBalanceAfter?: {
    account_id: number;
    account_name: string;
    currency: string;
    balance: number;
  };
}

export default function CashflowTransactionsPage() {
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
    document.title = "Cashflow Transactions · greenline";
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

  // Convert raw records into standardized rows and compute chronological running statement balances
  const unifiedRows = useMemo<UnifiedRowItem[]>(() => {
    const rawRows: {
      key: string;
      sortKey: string;
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
    }[] = [];

    // 1. Day-to-Day Cashflow
    cashflowTxs.forEach((cf) => {
      const isTransfer = cf.transaction_kind === "TRANSFER" || cf.items.some((i) => i.category_type === "TRANSFER");
      const isIncome = !isTransfer && cf.items.some((i) => i.category_type === "INCOME");

      const netCashDelta = cf.payments.reduce((sum, p) => sum + (p.amount || 0), 0);
      let flowPriority = 1; // neutral / transfer
      if (netCashDelta > 0 || isIncome) {
        flowPriority = 0; // inflow / credit
      } else if (netCashDelta < 0 || !isTransfer) {
        flowPriority = 2; // outflow / debit
      }

      rawRows.push({
        key: `cf-${cf.cashflow_id}`,
        sortKey: `${cf.transaction_date}_p${flowPriority}_cf_${String(cf.cashflow_id).padStart(10, '0')}`,
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

    // 2. Investment Trades
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
      if (isBuy && t.quantity) {
        paymentsList.push({
          account_id: t.account_id,
          account_name: `${holdingName} (Holding)`,
          account_currency: t.account_currency || "USD",
          amount: 0,
          holding_delta: `+${t.quantity} ${t.asset_symbol || "shares"}`
        });
        paymentsList.push({
          account_id: t.funding_account_id || t.account_id,
          account_name: fundingName !== holdingName ? fundingName : `${holdingName} (Cash)`,
          account_currency: t.funding_account_currency || t.account_currency || "USD",
          amount: -netTotal
        });
      } else if (isSell && t.quantity) {
        paymentsList.push({
          account_id: t.account_id,
          account_name: `${holdingName} (Holding)`,
          account_currency: t.account_currency || "USD",
          amount: 0,
          holding_delta: `-${t.quantity} ${t.asset_symbol || "shares"}`
        });
        paymentsList.push({
          account_id: t.funding_account_id || t.account_id,
          account_name: fundingName !== holdingName ? fundingName : `${holdingName} (Cash)`,
          account_currency: t.funding_account_currency || t.account_currency || "USD",
          amount: netTotal
        });
      } else if (isDiv) {
        paymentsList.push({
          account_id: t.funding_account_id || t.account_id,
          account_name: t.funding_account_name ? t.funding_account_name : `${holdingName} (Unlinked)`,
          account_currency: t.funding_account_currency || t.account_currency || "USD",
          amount: t.funding_account_id ? netTotal : 0
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
        tradeDesc = t.quantity && t.price_per_unit
          ? `Dividend: ${t.quantity} shares @ ${formatCurrency(t.price_per_unit, t.account_currency || "USD")}`
          : `Dividend Payout`;
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
          description: "Withheld Taxes & Duties",
          effective_label: "ESSENTIAL",
          amount: taxes
        });
      }

      const netTradeCashDelta = paymentsList.reduce((sum, p) => sum + (p.amount || 0), 0);
      let tradeFlowPriority = 1;
      if (netTradeCashDelta > 0 || isIncome) {
        tradeFlowPriority = 0; // sell proceeds, dividend, deposit
      } else if (netTradeCashDelta < 0 || !isTransfer) {
        tradeFlowPriority = 2; // buy, withdrawal
      }

      rawRows.push({
        key: `tr-${t.transaction_id}`,
        sortKey: `${t.transaction_date}_p${tradeFlowPriority}_tr_${String(t.transaction_id).padStart(10, '0')}`,
        source: "investment",
        rawTrade: t,
        date: t.transaction_date,
        title: t.asset_name ? `${t.asset_name}` : (t.asset_symbol || "Trade"),
        notes: t.notes,
        payments: paymentsList,
        items: itemsList,
        isTransfer,
        isIncome,
        totalAmount: netTotal,
        currency: t.account_currency || "USD"
      });
    });

    // Sort strictly chronological (oldest to newest) to compute cumulative running statement balances
    rawRows.sort((a, b) => a.sortKey.localeCompare(b.sortKey));

    const currentRunningBalances: Record<number, number> = {};
    const processedRows: UnifiedRowItem[] = [];

    rawRows.forEach((r) => {
      // Update running balance for each affected account
      const paymentsWithBal = r.payments.map((p) => {
        if (p.amount !== 0) {
          currentRunningBalances[p.account_id] = (currentRunningBalances[p.account_id] || 0) + p.amount;
        }
        return {
          ...p,
          running_balance_after: currentRunningBalances[p.account_id] ?? 0
        };
      });

      // Snapshot running balances after this transaction
      const balancesSnapshot = { ...currentRunningBalances };

      // Determine primary cash payment account for single-cell display
      const cashPayments = paymentsWithBal.filter((p) => p.amount !== 0);
      let primaryBalObj = undefined;
      if (cashPayments.length > 0) {
        const primary = cashPayments[0];
        primaryBalObj = {
          account_id: primary.account_id,
          account_name: primary.account_name,
          currency: primary.account_currency,
          balance: primary.running_balance_after ?? 0
        };
      } else if (paymentsWithBal.length > 0) {
        const primary = paymentsWithBal[0];
        primaryBalObj = {
          account_id: primary.account_id,
          account_name: primary.account_name,
          currency: primary.account_currency,
          balance: primary.running_balance_after ?? 0
        };
      }

      processedRows.push({
        ...r,
        payments: paymentsWithBal,
        runningBalancesAfter: balancesSnapshot,
        primaryBalanceAfter: primaryBalObj
      });
    });

    // Return in reverse chronological order (newest first) for standard ledger display
    return processedRows.reverse();
  }, [cashflowTxs, tradeTxs]);

  // Filter rows
  const filteredRows = useMemo(() => {
    return unifiedRows.filter((r) => {
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = r.title.toLowerCase().includes(q);
        const matchNotes = (r.notes || "").toLowerCase().includes(q);
        const matchItems = r.items.some(
          (i) => i.category_name.toLowerCase().includes(q) || (i.description || "").toLowerCase().includes(q)
        );
        const matchAccounts = r.payments.some((p) => p.account_name.toLowerCase().includes(q));
        if (!matchTitle && !matchNotes && !matchItems && !matchAccounts) return false;
      }

      // Account filter
      if (selectedAccountId !== "ALL") {
        const aid = Number(selectedAccountId);
        if (!r.payments.some((p) => p.account_id === aid)) return false;
      }

      // Label filter
      if (selectedLabelFilter !== "ALL") {
        if (!r.items.some((i) => (i.effective_label || "DISCRETIONARY") === selectedLabelFilter)) return false;
      }

      return true;
    });
  }, [unifiedRows, searchQuery, selectedAccountId, selectedLabelFilter]);

  // Current balance of selected account
  const selectedAccountInfo = useMemo(() => {
    if (selectedAccountId === "ALL") {
      return null;
    }
    const aid = Number(selectedAccountId);
    const acc = accounts.find((a) => a.account_id === aid);
    if (!acc) return null;

    // Latest balance across all unified rows
    const latestRowWithAccount = unifiedRows.find((r) => r.runningBalancesAfter[aid] !== undefined);
    const currentBal = latestRowWithAccount ? latestRowWithAccount.runningBalancesAfter[aid] : 0;
    return {
      name: acc.account_name,
      currency: acc.currency,
      balance: currentBal
    };
  }, [selectedAccountId, accounts, unifiedRows]);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-8 space-y-6">
      {/* Header Bar */}
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
            Historical ledger with running statement balances, split payment methods, and multi-category itemization
          </p>
        </div>

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

      {/* Main Card with Table */}
      <div className="getquin-card p-5 space-y-4">
        
        {/* Table Header Bar with Mode Selector & Filters */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Income & Spend Transactions ({filteredRows.length})
              </h2>
              <p className="text-[11px] font-medium text-slate-400">
                Historical statement ledger with continuous running net cash balance
              </p>
            </div>

            {/* Selected Account Balance Badge */}
            {selectedAccountInfo && (
              <div 
                data-testid="selected-account-balance"
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 dark:bg-blue-950/50 border border-blue-200/60 dark:border-blue-800/60 rounded-xl text-xs"
              >
                <Wallet className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span className="font-semibold text-slate-600 dark:text-slate-300">{selectedAccountInfo.name}:</span>
                <span className={`font-bold tabular-nums ${selectedAccountInfo.balance >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                  {formatCurrency(selectedAccountInfo.balance, selectedAccountInfo.currency)}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
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
              aria-label="account-filter"
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
                <th className="pb-2.5 font-bold text-right">Amount</th>
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
                filteredRows.map((r) => (
                  <tr key={r.key} data-testid="transaction-row" className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                    {/* Date */}
                    <td className="py-3 font-semibold text-slate-500 dark:text-slate-400 tabular-nums whitespace-nowrap">
                      {r.date}
                    </td>

                    {/* Title */}
                    <td className="py-3 font-bold text-[#0F172A] dark:text-white">
                      <div className="flex items-center gap-1.5">
                        {r.source === "investment" && (
                          <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" title="Investment Trade" />
                        )}
                        <span>{r.title}</span>
                      </div>
                      {r.notes && (
                        <div className="text-[11px] font-normal text-slate-400 line-clamp-1">{r.notes}</div>
                      )}
                    </td>

                    {/* Payments */}
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {r.payments.map((p, idx) => (
                          <span
                            key={idx}
                            data-testid="payment-badge"
                            data-account-id={p.account_id}
                            data-amount={p.amount}
                            data-running-balance={p.running_balance_after}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200/60 dark:border-slate-700/60"
                          >
                            <span>{p.account_name}</span>
                            {p.holding_delta ? (
                              <span className="text-blue-600 dark:text-blue-400 font-extrabold">({p.holding_delta})</span>
                            ) : (
                              <>
                                <span className={p.amount >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
                                  {p.amount >= 0 ? `+${formatCurrency(p.amount, p.account_currency)}` : formatCurrency(p.amount, p.account_currency)}
                                </span>
                                {p.running_balance_after !== undefined && (
                                  <span className="text-[9px] text-slate-400 font-semibold pl-0.5 border-l border-slate-300 dark:border-slate-700">
                                    Bal: {formatCurrency(p.running_balance_after, p.account_currency)}
                                  </span>
                                )}
                              </>
                            )}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Items */}
                    <td className="py-3">
                      <div className="space-y-1">
                        {r.items.map((i, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-xs">
                            <span className="font-bold text-slate-800 dark:text-slate-200">{i.category_name}</span>
                            {i.description && (
                              <span className="text-[11px] text-slate-400 line-clamp-1 font-normal">• {i.description}</span>
                            )}
                            {i.effective_label && (
                              <span className="px-1.5 py-0.2 text-[9px] font-extrabold uppercase rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                                {i.effective_label}
                              </span>
                            )}
                            {r.items.length > 1 && (
                              <span className="text-[10px] text-slate-400 font-semibold ml-auto">
                                {formatCurrency(i.amount, r.currency)}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </td>

                    {/* Total Amount */}
                    <td className="py-3 text-right font-bold tabular-nums">
                      <span className={r.isTransfer ? "text-blue-600 dark:text-blue-400" : r.isIncome ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
                        {r.isIncome ? "+" : "-"}{formatCurrency(r.totalAmount, r.currency)}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="py-3 text-right whitespace-nowrap">
                      {r.source === "cashflow" && r.rawCashflow && (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => {
                              setEditingCashflowTx(r.rawCashflow!);
                              setIsCashflowModalOpen(true);
                            }}
                            className="p-1 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                            title="Edit Cashflow"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteCashflow(r.rawCashflow!.cashflow_id)}
                            className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                            title="Delete Cashflow"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}

                      {r.source === "investment" && r.rawTrade && (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => {
                              setEditingTradeTx(r.rawTrade!);
                              setIsTradeModalOpen(true);
                            }}
                            className="p-1 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                            title="Edit Trade Transaction"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteTrade(r.rawTrade!.transaction_id)}
                            className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                            title="Delete Trade"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cashflow Modal */}
      <CashflowModal
        isOpen={isCashflowModalOpen}
        onClose={() => {
          setIsCashflowModalOpen(false);
          setEditingCashflowTx(null);
        }}
        onSuccess={() => loadData()}
        initialData={editingCashflowTx}
      />

      {/* Trade Modal */}
      <TransactionModal
        isOpen={isTradeModalOpen}
        onClose={() => {
          setIsTradeModalOpen(false);
          setEditingTradeTx(null);
        }}
        onSuccess={() => loadData()}
        initialData={editingTradeTx}
      />
    </div>
  );
}
