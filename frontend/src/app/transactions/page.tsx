"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum } from "@/lib/format";
import { TransactionModal, TransactionItem } from "@/components/TransactionModal";
import { Receipt, Plus, Filter, Edit, Trash2 } from "lucide-react";

interface Transaction {
  transaction_id: number;
  account_id: number;
  asset_id: number | null;
  account_name: string;
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
  const [filterType, setFilterType] = useState<string>("all");

  useEffect(() => {
    loadTransactions();
  }, []);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<Transaction[]>("/transactions?limit=200");
      setTransactions(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (tx: Transaction) => {
    setEditingTransaction(tx);
    setIsModalOpen(true);
  };

  const handleDelete = async (transactionId: number) => {
    if (!confirm("Are you sure you want to delete this transaction? This will update your open lots and net worth.")) {
      return;
    }
    try {
      await apiFetch(`/transactions/${transactionId}`, { method: "DELETE" });
      loadTransactions();
    } catch (e: any) {
      alert(e.message || "Failed to delete transaction");
    }
  };

  const filtered = transactions.filter((t) => {
    if (filterType === "all") return true;
    return t.transaction_type.toLowerCase() === filterType;
  });

  const getTypeBadge = (type: string) => {
    const t = type.toLowerCase();
    if (t === "buy") return <span className="px-2 py-0.5 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md">BUY</span>;
    if (t === "sell") return <span className="px-2 py-0.5 text-xs font-bold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md">SELL</span>;
    if (t === "dividend") return <span className="px-2 py-0.5 text-xs font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 rounded-md">DIVIDEND</span>;
    if (t === "deposit") return <span className="px-2 py-0.5 text-xs font-bold text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded-md">DEPOSIT</span>;
    if (t === "withdrawal") return <span className="px-2 py-0.5 text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md">WITHDRAWAL</span>;
    return <span className="px-2 py-0.5 text-xs font-semibold text-slate-400 bg-slate-800 rounded-md">{type.toUpperCase()}</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <Receipt className="w-6 h-6 text-emerald-400" />
            Transaction Ledger
          </h1>
          <p className="text-xs text-slate-400 mt-1">Complete historical record of buys, sells, dividends, deposits, and withdrawals</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none"
            >
              <option value="all">All Types</option>
              <option value="buy">Buys</option>
              <option value="sell">Sells</option>
              <option value="dividend">Dividends</option>
              <option value="deposit">Deposits</option>
              <option value="withdrawal">Withdrawals</option>
            </select>
          </div>

          <button
            onClick={() => {
              setEditingTransaction(null);
              setIsModalOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2 text-xs font-bold bg-emerald-500 hover:bg-emerald-600 text-slate-950 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Transaction
          </button>
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Account</th>
                <th className="py-3 px-4">Asset</th>
                <th className="py-3 px-4 text-right">Quantity</th>
                <th className="py-3 px-4 text-right">Price / Unit</th>
                <th className="py-3 px-4 text-right">Total Amount</th>
                <th className="py-3 px-4 text-right">Fees & Taxes</th>
                <th className="py-3 px-4">Notes</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
              {filtered.length > 0 ? (
                filtered.map((tx) => (
                  <tr key={tx.transaction_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 text-slate-300">{tx.transaction_date}</td>
                    <td className="py-3.5 px-4 font-sans">{getTypeBadge(tx.transaction_type)}</td>
                    <td className="py-3.5 px-4 font-sans text-slate-300">{tx.account_name || "-"}</td>
                    <td className="py-3.5 px-4 font-sans text-white font-semibold">
                      {tx.asset_symbol ? `${tx.asset_symbol}` : "-"}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-200">{tx.quantity != null ? formatQty(tx.quantity) : "-"}</td>
                    <td className="py-3.5 px-4 text-right text-slate-200">{tx.price_per_unit != null ? `$${formatNum(tx.price_per_unit)}` : "-"}</td>
                    <td className="py-3.5 px-4 text-right font-bold text-white">${formatNum(tx.total_amount)}</td>
                    <td className="py-3.5 px-4 text-right text-slate-400">
                      ${formatNum(tx.fees + tx.taxes)}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 font-sans text-xs">{tx.notes || "-"}</td>
                    <td className="py-3.5 px-4 text-center font-sans">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleEdit(tx)}
                          className="p-1 text-slate-400 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors"
                          title="Edit Transaction"
                        >
                          <Edit className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(tx.transaction_id)}
                          className="p-1 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded transition-colors"
                          title="Delete Transaction"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-500 font-sans text-sm">
                    No transactions match your filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
