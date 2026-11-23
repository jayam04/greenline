"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { parsePaginatedResponse, syncUrlPage } from "@/lib/pagination";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
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
  const [loadingMore, setLoadingMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>("ALL");
  const [selectedAccountId, setSelectedAccountId] = useState<string>("ALL");
  const [selectedAccountIds, setSelectedAccountIds] = useState<number[]>([]);

  // Modals
  const [isCashflowModalOpen, setIsCashflowModalOpen] = useState(false);
  const [editingCashflowTx, setEditingCashflowTx] = useState<CashflowTransactionItem | null>(null);

  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);
  const [isPrintModalOpen, setIsPrintModalOpen] = useState(false);
  const [editingTradeTx, setEditingTradeTx] = useState<TransactionItem | null>(null);

  const inFlightRef = useRef(false);
  const queryVersionRef = useRef(0);
  const hasMoreRef = useRef(true);
  const currentPageRef = useRef(1);
  const selectedAccountIdRef = useRef<string>("ALL");

  const fetchChunk = async (
    targetPage: number,
    isReset = false,
    accountIdFilter = selectedAccountIdRef.current
  ) => {
    if (inFlightRef.current && !isReset) return;
    inFlightRef.current = true;
    const currentVersion = isReset ? ++queryVersionRef.current : queryVersionRef.current;

    if (isReset) {
      setLoading(true);
      setError(null);
    } else {
      setLoadingMore(true);
      setError(null);
    }

    try {
      let cfUrl = "/cashflow";
      let trUrl = "/transactions";
      const queryParts: string[] = [];

      if (targetPage > 1) {
        queryParts.push(`page=${targetPage}`, "page_size=20");
      } else if (accountIdFilter && accountIdFilter !== "ALL") {
        queryParts.push("page=1", "page_size=20");
      }

      if (accountIdFilter && accountIdFilter !== "ALL") {
        queryParts.push(`account_id=${encodeURIComponent(accountIdFilter)}`);
      }

      if (queryParts.length > 0) {
        const q = queryParts.join("&");
        cfUrl += `?${q}`;
        trUrl += `?${q}`;
      }

      let [cfRes, trRes] = await Promise.all([
        apiFetch<any>(cfUrl),
        apiFetch<any>(trUrl),
      ]);

      const isEmptyEnvelope = (res: any) => {
        if (!res) return true;
        if (Array.isArray(res)) return false;
        if (typeof res === "object") {
          if ("items" in res || "data" in res || "total" in res || "transactions" in res) return false;
          return Object.keys(res).length === 0;
        }
        return true;
      };

      if (isEmptyEnvelope(cfRes) && cfUrl !== "/cashflow") {
        cfRes = await apiFetch<any>("/cashflow");
      }
      if (isEmptyEnvelope(trRes) && trUrl !== "/transactions") {
        trRes = await apiFetch<any>("/transactions");
      }

      if (currentVersion !== queryVersionRef.current) return;

      const cfParsed = parsePaginatedResponse<CashflowTransactionItem>(cfRes, targetPage, 20);
      const trParsed = parsePaginatedResponse<TransactionItem>(trRes, targetPage, 20);

      const nextHasMore = cfParsed.hasMore;
      currentPageRef.current = targetPage;
      setCurrentPage(targetPage);
      hasMoreRef.current = nextHasMore;
      setHasMore(nextHasMore);

      setCashflowTxs((prev) => {
        if (isReset) return cfParsed.items;
        const existingIds = new Set(prev.map((c) => c.cashflow_id));
        const unique = cfParsed.items.filter((c) => !existingIds.has(c.cashflow_id));
        return [...prev, ...unique];
      });

      setTradeTxs((prev) => {
        if (isReset) return trParsed.items;
        const existingIds = new Set(prev.map((t) => t.transaction_id));
        const unique = trParsed.items.filter((t) => !existingIds.has(t.transaction_id));
        return [...prev, ...unique];
      });

      syncUrlPage(targetPage);
    } catch (err: any) {
      if (currentVersion !== queryVersionRef.current) return;
      console.error("Failed to load cashflow transactions chunk:", err);
      setError(err.message || "Failed to load transactions");
    } finally {
      inFlightRef.current = false;
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    document.title = "Cashflow Transactions · greenline";

    apiFetch<Account[]>("/accounts")
      .then((accRes) => setAccounts(accRes || []))
      .catch((e) => console.error("Failed to load accounts:", e));

    const searchParams = new URLSearchParams(window.location.search);
    const pageParam = parseInt(searchParams.get("page") || "1", 10);
    const initialPage = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;
    currentPageRef.current = initialPage;
    setCurrentPage(initialPage);
    fetchChunk(initialPage, true, selectedAccountIdRef.current);
  }, []);

  const handleDeleteCashflow = async (id: number) => {
    if (!confirm("Are you sure you want to delete this transaction?")) return;
    try {
      await apiFetch(`/cashflow/${id}`, { method: "DELETE" });
      fetchChunk(1, true, selectedAccountIdRef.current);
    } catch (err: any) {
      alert(err.message || "Failed to delete transaction");
    }
  };

  const handleDeleteTrade = async (id: number) => {
    if (!confirm("Are you sure you want to delete this trade transaction?")) return;
    try {
      await apiFetch(`/transactions/${id}`, { method: "DELETE" });
      fetchChunk(1, true, selectedAccountIdRef.current);
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
          const nextBal = (currentRunningBalances[p.account_id] || 0) + p.amount;
          currentRunningBalances[p.account_id] = Math.round(nextBal * 100) / 100;
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
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Every cash movement with a running balance."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={() => setIsPrintModalOpen(true)}>
              <Printer className="size-4" />
              <span>Print</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setEditingTradeTx(null);
                setIsTradeModalOpen(true);
              }}
            >
              <Briefcase className="size-4" />
              <span>Trade / SIP</span>
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setEditingCashflowTx(null);
                setIsCashflowModalOpen(true);
              }}
            >
              <Plus className="size-4" />
              <span>Cashflow</span>
            </Button>
          </div>
        }
      />

      {/* Main Card with Table */}
      <div className="getquin-card rounded-card border border-border bg-surface p-5 space-y-4 shadow-card">
        
        {/* Table Header Bar with Filters & Account Balance */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-border">
          <div>
            <h2 className="text-body font-semibold text-foreground">
              Income & Spend Transactions ({filteredRows.length})
            </h2>
            <p className="text-label text-muted">
              Historical statement ledger with continuous running net cash balance
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Account Balance in place of removed buttons */}
            {selectedAccountInfo && (
              <div 
                data-testid="selected-account-balance"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-control border border-border bg-surface text-label"
              >
                <Wallet className="size-3.5 text-primary" />
                <span className="font-medium text-muted">{selectedAccountInfo.name}:</span>
                <span className={`font-bold tabular-nums ${selectedAccountInfo.balance >= 0 ? "text-gain" : "text-loss"}`}>
                  {formatCurrency(selectedAccountInfo.balance, selectedAccountInfo.currency)}
                </span>
              </div>
            )}

            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="size-3.5 text-muted absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Search merchant, account..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-52 rounded-control border border-border bg-surface pl-8 pr-3 text-label font-medium text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none transition-colors"
              />
            </div>

            {/* Account Selector Filter */}
            <select
              aria-label="account-filter"
              value={selectedAccountId}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedAccountId(val);
                selectedAccountIdRef.current = val;
                if (val === "ALL") {
                  setSelectedAccountIds([]);
                } else {
                  setSelectedAccountIds([Number(val)]);
                }
                currentPageRef.current = 1;
                setCurrentPage(1);
                syncUrlPage(1);
                fetchChunk(1, true, val);
              }}
              className="h-9 rounded-control border border-border bg-surface px-3 text-label font-medium text-foreground transition-colors hover:border-border-strong focus:outline-none cursor-pointer"
            >
              <option value="ALL">All accounts</option>
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>
                  {a.account_name} ({a.currency})
                </option>
              ))}
            </select>

            {/* Label Filter Select */}
            <select
              aria-label="label-filter"
              value={selectedLabelFilter}
              onChange={(e) => setSelectedLabelFilter(e.target.value)}
              className="h-9 rounded-control border border-border bg-surface px-3 text-label font-medium text-foreground transition-colors hover:border-border-strong focus:outline-none cursor-pointer"
            >
              {["ALL", "ESSENTIAL", "DISCRETIONARY", "LUXURY", "INVESTMENT"].map((lbl) => (
                <option key={lbl} value={lbl}>
                  {lbl === "ALL" ? "All labels" : lbl.charAt(0) + lbl.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Ledger Table */}
        <TransactionLedger
          transactions={filteredRows}
          loading={loading}
          loadingMore={loadingMore}
          hasMore={hasMore}
          error={error}
          onLoadMore={() => {
            if (hasMoreRef.current && !inFlightRef.current) {
              fetchChunk(currentPageRef.current + 1, false, selectedAccountIdRef.current);
            }
          }}
          onRetry={() => {
            const isInitialRetry = cashflowTxs.length === 0 && tradeTxs.length === 0;
            fetchChunk(
              isInitialRetry ? currentPageRef.current : currentPageRef.current + 1,
              isInitialRetry,
              selectedAccountIdRef.current
            );
          }}
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
        onSuccess={() => fetchChunk(1, true, selectedAccountIdRef.current)}
        initialData={editingCashflowTx}
      />

      {/* Trade Modal */}
      <TransactionModal
        isOpen={isTradeModalOpen}
        onClose={() => {
          setIsTradeModalOpen(false);
          setEditingTradeTx(null);
        }}
        onSuccess={() => fetchChunk(1, true, selectedAccountIdRef.current)}
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
