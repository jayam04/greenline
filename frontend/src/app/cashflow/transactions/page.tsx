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
import { TransactionLedger, UnifiedRowItem } from "@/components/TransactionLedger";
import { PrintTransactionsDialog } from "@/components/PrintTransactionsDialog";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Check, ChevronsUpDown, Printer } from "lucide-react";


interface Account {
  account_id: number;
  account_name: string;
  currency: string;
  account_type: string;
}


export default function CashflowTransactionsPage() {
  const [cashflowTxs, setCashflowTxs] = useState<CashflowTransactionItem[]>([]);
  const [tradeTxs, setTradeTxs] = useState<TransactionItem[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>("ALL");
  const [selectedAccountIds, setSelectedAccountIds] = useState<number[]>([]);

  // Modals
  const [isCashflowModalOpen, setIsCashflowModalOpen] = useState(false);
  const [editingCashflowTx, setEditingCashflowTx] = useState<CashflowTransactionItem | null>(null);

  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);
  const [isPrintModalOpen, setIsPrintModalOpen] = useState(false);
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
      if (selectedAccountIds.length > 0) {
        if (!r.payments.some((p) => selectedAccountIds.includes(p.account_id))) return false;
      }

      // Label filter
      if (selectedLabelFilter !== "ALL") {
        if (!r.items.some((i) => (i.effective_label || "DISCRETIONARY") === selectedLabelFilter)) return false;
      }

      return true;
    });
  }, [unifiedRows, searchQuery, selectedAccountIds, selectedLabelFilter]);

  // Current balance of selected account
  const selectedAccountInfo = useMemo(() => {
    if (selectedAccountIds.length !== 1) {
      return null;
    }
    const aid = selectedAccountIds[0];
    const acc = accounts.find((a) => a.account_id === aid);
    if (!acc) return null;

    // Latest balance across all unified rows
    const latestRowWithAccount = unifiedRows.find((r) => r.runningBalancesAfter?.[aid] !== undefined);
    const currentBal = latestRowWithAccount ? latestRowWithAccount.runningBalancesAfter?.[aid] || 0 : 0;
    return {
      name: acc.account_name,
      currency: acc.currency,
      balance: currentBal
    };
  }, [selectedAccountIds, accounts, unifiedRows]);

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-8 space-y-6">
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
            <button
              onClick={() => {
                setEditingTradeTx(null);
                setIsTradeModalOpen(true);
              }}
              className="px-3 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <Briefcase className="w-3.5 h-3.5 text-blue-500" />
              <span>+ Trade / SIP</span>
            </button>

            <button
              onClick={() => {
                setEditingCashflowTx(null);
                setIsCashflowModalOpen(true);
              }}
              className="px-3 py-1.5 text-xs font-bold bg-[#0F172A] hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-[#0F172A] rounded-lg transition-all shadow-sm flex items-center gap-1.5 cursor-pointer mr-2"
            >
              <Plus className="w-3.5 h-3.5 text-emerald-400" />
              <span>+ Cashflow</span>
            </button>
            
            <button
              onClick={() => setIsPrintModalOpen(true)}
              className="px-3 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer mr-2"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print</span>
            </button>

            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Search merchant, account..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-secondary text-xs font-semibold text-foreground placeholder:text-muted-foreground pl-8 pr-3 py-1.5 rounded-lg border border-input focus:border-ring focus:bg-background focus:outline-none w-48"
              />
            </div>

            {/* Account Multi-Select Popover */}
            <Popover>
              <PopoverTrigger className="flex items-center justify-between bg-secondary hover:bg-secondary/80 text-xs font-bold text-secondary-foreground border border-border px-3 py-1.5 rounded-lg w-40">
                  <span className="truncate">
                    {selectedAccountIds.length === 0 
                      ? "All Accounts" 
                      : selectedAccountIds.length === 1
                      ? accounts.find(a => a.account_id === selectedAccountIds[0])?.account_name
                      : `${selectedAccountIds.length} Accounts`}
                  </span>
                  <ChevronsUpDown className="ml-2 h-3.5 w-3.5 shrink-0 opacity-50" />
              </PopoverTrigger>
              <PopoverContent className="w-56 p-0" align="end">
                <Command>
                  <CommandInput placeholder="Search accounts..." />
                  <CommandList>
                    <CommandEmpty>No account found.</CommandEmpty>
                    <CommandGroup>
                      {accounts.map((a) => (
                        <CommandItem
                          key={a.account_id}
                          onSelect={() => {
                            setSelectedAccountIds(prev => 
                              prev.includes(a.account_id) 
                                ? prev.filter(id => id !== a.account_id)
                                : [...prev, a.account_id]
                            )
                          }}
                        >
                          <Checkbox 
                            checked={selectedAccountIds.includes(a.account_id)}
                            className="mr-2"
                          />
                          {a.account_name} ({a.currency})
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>

            {/* Label Filter Select */}
            <Select value={selectedLabelFilter} onValueChange={(v) => setSelectedLabelFilter(v || "ALL")}>
              <SelectTrigger className="w-[140px] h-8 text-xs font-bold bg-secondary text-secondary-foreground border border-border">
                <SelectValue placeholder="All Labels" />
              </SelectTrigger>
              <SelectContent>
                {["ALL", "ESSENTIAL", "DISCRETIONARY", "LUXURY", "INVESTMENT"].map((lbl) => (
                  <SelectItem key={lbl} value={lbl} className="text-xs font-bold">
                    {lbl === "ALL" ? "All Labels" : lbl.charAt(0) + lbl.slice(1).toLowerCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Ledger Table */}
        <TransactionLedger
          transactions={filteredRows}
          loading={loading}
          showRunningBalance={true}
          selectedAccountIds={selectedAccountIds}
          onEditCashflow={(tx) => {
            setEditingCashflowTx(tx);
            setIsCashflowModalOpen(true);
          }}
          onDeleteCashflow={handleDeleteCashflow}
          onEditTrade={(tx) => {
            setEditingTradeTx(tx);
            setIsTradeModalOpen(true);
          }}
          onDeleteTrade={handleDeleteTrade}
        />
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

      <PrintTransactionsDialog
        isOpen={isPrintModalOpen}
        onClose={() => setIsPrintModalOpen(false)}
        accounts={accounts}
      />

    </div>
  );
}
