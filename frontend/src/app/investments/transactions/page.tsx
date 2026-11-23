"use client";

import React, { useEffect, useState, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney } from "@/lib/format";
import { parsePaginatedResponse, syncUrlPage } from "@/lib/pagination";
import { TransactionModal, TransactionItem } from "@/components/TransactionModal";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { 
  Plus, Search, Pencil, Trash2, ArrowUpRight, ArrowDownLeft, RefreshCw 
} from "lucide-react";
import { cn } from "@/lib/utils";

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

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [editingTransaction, setEditingTransaction] = useState<TransactionItem | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const inFlightRef = useRef(false);
  const queryVersionRef = useRef(0);
  const hasMoreRef = useRef(true);
  const currentPageRef = useRef(1);
  const filterTypeRef = useRef("all");

  const fetchChunk = async (targetPage: number, isInitial = false, currentFilter = filterTypeRef.current) => {
    if (inFlightRef.current && !isInitial) return;
    inFlightRef.current = true;
    const currentVersion = ++queryVersionRef.current;

    if (isInitial) {
      setLoading(true);
      setError(null);
    } else {
      setIsLoadingMore(true);
      setError(null);
    }

    try {
      let endpoint = `/transactions?page=${targetPage}&page_size=20`;
      if (currentFilter && currentFilter !== "all") {
        endpoint += `&type=${encodeURIComponent(currentFilter)}`;
      }

      const res = await apiFetch<any>(endpoint);
      if (currentVersion !== queryVersionRef.current) return;

      const parsed = parsePaginatedResponse<Transaction>(res, targetPage, 20);
      currentPageRef.current = targetPage;
      setCurrentPage(targetPage);
      hasMoreRef.current = parsed.hasMore;
      setHasMore(parsed.hasMore);

      setTransactions((prev) => {
        if (isInitial) return parsed.items;
        const existingIds = new Set(prev.map((t) => t.transaction_id));
        const unique = parsed.items.filter((t) => !existingIds.has(t.transaction_id));
        return [...prev, ...unique];
      });

      syncUrlPage(targetPage);
    } catch (err: any) {
      if (currentVersion !== queryVersionRef.current) return;
      console.error("Failed to fetch trades chunk:", err);
      setError(err.message || "Failed to load trades");
    } finally {
      inFlightRef.current = false;
      setLoading(false);
      setIsLoadingMore(false);
    }
  };

  useEffect(() => {
    document.title = "Trades · greenline";
    const searchParams = new URLSearchParams(window.location.search);
    const pageParam = parseInt(searchParams.get("page") || "1", 10);
    const initialPage = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;
    currentPageRef.current = initialPage;
    setCurrentPage(initialPage);
    fetchChunk(initialPage, true, filterTypeRef.current);
  }, []);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver((entries) => {
      const first = entries[0];
      if (first && first.isIntersecting) {
        if (hasMoreRef.current && !inFlightRef.current) {
          fetchChunk(currentPageRef.current + 1, false, filterTypeRef.current);
        }
      }
    });

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  const handleFilterChange = (newFilter: string) => {
    setFilterType(newFilter);
    filterTypeRef.current = newFilter;
    currentPageRef.current = 1;
    setCurrentPage(1);
    syncUrlPage(1);
    fetchChunk(1, true, newFilter);
  };

  const handleSearchChange = (q: string) => {
    setSearchQuery(q);
    currentPageRef.current = 1;
    setCurrentPage(1);
    syncUrlPage(1);
    fetchChunk(1, true, filterTypeRef.current);
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
      fetchChunk(1, true, filterTypeRef.current);
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

  return (
    <>
      <PageHeader
        title="Trades"
        description="Every buy, sell, dividend and split."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchChunk(1, true, filterTypeRef.current)}
              className="p-2 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors"
              title="Refresh transactions"
              aria-label="Refresh transactions"
            >
              <RefreshCw className={cn("size-4", (loading || isLoadingMore) && "animate-spin text-primary")} />
            </button>
            <Button
              size="sm"
              onClick={() => {
                setEditingTransaction(null);
                setIsModalOpen(true);
              }}
            >
              <Plus className="size-4" />
              <span>Add transaction</span>
            </Button>
          </div>
        }
      />

      <Card className="rounded-card border border-border bg-surface shadow-card">
        <CardContent className="space-y-6 p-6">
          {/* Search & Filter Bar */}
          <div className="flex flex-wrap gap-3">
            <div className="relative min-w-64 flex-1">
              <Search className="size-3.5 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search asset, symbol, account or notes"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full bg-surface-2 text-foreground placeholder:text-muted text-label rounded-control pl-8.5 pr-4 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
            <select
              value={filterType}
              onChange={(e) => handleFilterChange(e.target.value)}
              className="w-44 bg-surface-2 text-foreground text-label font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none cursor-pointer"
            >
              <option value="all">All types</option>
              <option value="buy">Buys</option>
              <option value="sell">Sells</option>
              <option value="dividend">Dividends</option>
              <option value="deposit">Deposits</option>
              <option value="withdrawal">Withdrawals</option>
              <option value="split">Splits</option>
            </select>
          </div>

          {/* Grouped Month Streams */}
          {Object.keys(groupedTransactions).length > 0 ? (
            Object.entries(groupedTransactions).map(([monthYear, txList]) => (
              <section key={monthYear} className="space-y-2">
                <h3 className="text-micro uppercase tracking-wider text-subtle font-semibold mb-1">
                  {monthYear}
                </h3>
                <ul className="divide-y divide-border border-t border-border">
                  {txList.map((tx) => {
                    const isBuy = tx.transaction_type.toLowerCase() === "buy";
                    const isSell = tx.transaction_type.toLowerCase() === "sell";
                    const isDividend = tx.transaction_type.toLowerCase() === "dividend";
                    const curr = tx.account_currency || "USD";

                    return (
                      <li
                        key={tx.transaction_id}
                        className="group flex items-center gap-4 py-3 hover:bg-surface-2/40 px-2 rounded-control transition-colors"
                      >
                        <span className="w-12 text-label text-muted font-medium tabular-nums shrink-0">
                          {formatDayDate(tx.transaction_date)}
                        </span>

                        <span
                          className={cn(
                            "grid size-8 place-items-center rounded-full shrink-0",
                            isBuy
                              ? "bg-info-soft text-info"
                              : "bg-gain-soft text-gain"
                          )}
                          aria-label={tx.transaction_type}
                        >
                          {isBuy ? (
                            <ArrowUpRight className="size-4" />
                          ) : (
                            <ArrowDownLeft className="size-4" />
                          )}
                        </span>

                        <div className="min-w-0 flex-1 leading-tight">
                          <div className="font-semibold text-foreground text-body truncate">
                            {tx.asset_name || tx.asset_symbol || tx.account_name || "Cash Movement"}
                          </div>
                          <div className="text-label text-muted tabular-nums truncate mt-0.5">
                            {isBuy && `Bought x${formatQty(tx.quantity || 0)} at ${formatMoney(tx.price_per_unit, curr)}`}
                            {isSell && `Sold x${formatQty(tx.quantity || 0)} at ${formatMoney(tx.price_per_unit, curr)}`}
                            {isDividend && `Dividend distribution`}
                            {tx.transaction_type.toLowerCase() === "deposit" && `Deposit`}
                            {tx.transaction_type.toLowerCase() === "withdrawal" && `Withdrawal`}
                            {tx.transaction_type.toLowerCase() === "split" && `Stock Split`}
                            {tx.notes && <span className="ml-1 opacity-75">· {tx.notes}</span>}
                          </div>
                        </div>

                        <div className="text-right leading-tight tabular-nums shrink-0">
                          <div className="font-semibold text-foreground text-body">
                            {formatMoney(tx.total_amount, curr)}
                          </div>
                          <div className="text-micro text-muted mt-0.5">
                            {tx.funding_account_name && tx.funding_account_name !== tx.account_name
                              ? `${tx.account_name} · ${tx.funding_account_name}`
                              : (tx.funding_account_name || tx.account_name || "Account")}
                          </div>
                        </div>

                        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleEdit(tx)}
                            className="p-1.5 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors"
                            title="Edit"
                            aria-label="Edit"
                          >
                            <Pencil className="size-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(tx.transaction_id)}
                            className="p-1.5 text-loss/70 hover:text-loss hover:bg-loss-soft rounded-control transition-colors"
                            title="Delete"
                            aria-label="Delete"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          ) : (
            <div className="py-16 text-center text-label text-muted">
              {loading ? "Loading trades..." : "No trades found matching your search."}
            </div>
          )}

          {/* Sentinel element observed by IntersectionObserver */}
          <div
            ref={sentinelRef}
            data-testid="trades-sentinel"
            className="py-4 flex flex-col items-center justify-center min-h-[40px]"
          >
            {isLoadingMore && (
              <div role="status" className="flex items-center gap-2 text-label text-muted">
                <RefreshCw className="size-4 animate-spin text-primary" />
                <span>Loading trades...</span>
              </div>
            )}
            {error && (
              <div className="flex flex-col items-center gap-2">
                <span className="text-label text-loss">{error}</span>
                <button
                  type="button"
                  onClick={() => {
                    const isInitialRetry = transactions.length === 0;
                    fetchChunk(
                      isInitialRetry ? currentPageRef.current : currentPageRef.current + 1,
                      isInitialRetry,
                      filterTypeRef.current
                    );
                  }}
                  className="px-3 py-1 text-label rounded-control border border-border bg-surface-2 hover:bg-surface-3 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Trade Edit/Add Modal */}
      {isModalOpen && (
        <TransactionModal
          isOpen={isModalOpen}
          initialData={editingTransaction}
          onClose={() => {
            setIsModalOpen(false);
            setEditingTransaction(null);
          }}
          onSuccess={() => {
            setIsModalOpen(false);
            setEditingTransaction(null);
            fetchChunk(1, true, filterTypeRef.current);
          }}
        />
      )}
    </>
  );
}
