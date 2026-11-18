"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney } from "@/lib/format";
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
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [editingTransaction, setEditingTransaction] = useState<TransactionItem | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  useEffect(() => {
    document.title = "Trades · greenline";
    loadTransactions();
  }, []);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<Transaction[]>("/transactions?limit=500");
      setTransactions(data || []);
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

  return (
    <>
      <PageHeader
        title="Trades"
        description="Every buy, sell, dividend and split."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={loadTransactions}
              className="p-2 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors"
              title="Reload Transactions"
            >
              <RefreshCw className={cn("size-4", loading && "animate-spin text-primary")} />
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
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-surface-2 text-foreground placeholder:text-muted text-label rounded-control pl-8.5 pr-4 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
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
            loadTransactions();
          }}
        />
      )}
    </>
  );
}
