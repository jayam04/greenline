"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { X, Plus, Edit } from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
}

interface Asset {
  asset_id: number;
  symbol: string;
  name: string;
}

export interface TransactionItem {
  transaction_id: number;
  account_id: number;
  asset_id: number | null;
  transaction_type: string;
  transaction_date: string;
  quantity: number | null;
  price_per_unit: number | null;
  total_amount: number;
  fees: number;
  taxes: number;
  notes: string | null;
}

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialData?: TransactionItem | null;
}

export function TransactionModal({ isOpen, onClose, onSuccess, initialData }: TransactionModalProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  
  const [accountId, setAccountId] = useState<number | "">("");
  const [assetId, setAssetId] = useState<number | "">("");
  const [transactionType, setTransactionType] = useState<string>("buy");
  const [transactionDate, setTransactionDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [quantity, setQuantity] = useState<string>("");
  const [pricePerUnit, setPricePerUnit] = useState<string>("");
  const [totalAmount, setTotalAmount] = useState<string>("");
  const [fees, setFees] = useState<string>("0");
  const [taxes, setTaxes] = useState<string>("0");
  const [notes, setNotes] = useState<string>("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen) {
      loadDropdowns();
      if (initialData) {
        setAccountId(initialData.account_id);
        setAssetId(initialData.asset_id ?? "");
        setTransactionType(initialData.transaction_type);
        setTransactionDate(initialData.transaction_date);
        setQuantity(initialData.quantity ? initialData.quantity.toString() : "");
        setPricePerUnit(initialData.price_per_unit ? initialData.price_per_unit.toString() : "");
        setTotalAmount(initialData.total_amount.toString());
        setFees(initialData.fees.toString());
        setTaxes(initialData.taxes.toString());
        setNotes(initialData.notes || "");
      } else {
        setQuantity("");
        setPricePerUnit("");
        setTotalAmount("");
        setFees("0");
        setTaxes("0");
        setNotes("");
      }
    }
  }, [isOpen, initialData]);

  const loadDropdowns = async () => {
    try {
      const [accData, astData] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Asset[]>("/assets"),
      ]);
      setAccounts(accData);
      setAssets(astData);
      if (!initialData) {
        if (accData.length > 0 && !accountId) setAccountId(accData[0].account_id);
        if (astData.length > 0 && !assetId) setAssetId(astData[0].asset_id);
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  // Auto-compute total amount when qty & price change
  useEffect(() => {
    if (quantity && pricePerUnit && !initialData) {
      const calcTotal = (parseFloat(quantity) * parseFloat(pricePerUnit)).toFixed(2);
      setTotalAmount(calcTotal);
    }
  }, [quantity, pricePerUnit, initialData]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const payload = {
        account_id: Number(accountId),
        asset_id: assetId ? Number(assetId) : null,
        transaction_type: transactionType,
        transaction_date: transactionDate,
        quantity: quantity ? parseFloat(quantity) : null,
        price_per_unit: pricePerUnit ? parseFloat(pricePerUnit) : null,
        total_amount: parseFloat(totalAmount),
        fees: parseFloat(fees || "0"),
        taxes: parseFloat(taxes || "0"),
        notes: notes || null,
      };

      if (initialData) {
        await apiFetch(`/transactions/${initialData.transaction_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/transactions", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save transaction");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          {initialData ? <Edit className="w-5 h-5 text-emerald-400" /> : <Plus className="w-5 h-5 text-emerald-400" />}
          {initialData ? "Edit Transaction" : "Add New Transaction"}
        </h2>

        {error && (
          <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Transaction Type</label>
              <select
                value={transactionType}
                onChange={(e) => setTransactionType(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
                <option value="dividend">Dividend</option>
                <option value="deposit">Deposit (Cash In)</option>
                <option value="withdrawal">Withdrawal (Cash Out)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Date</label>
              <input
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Account</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
                required
              >
                {accounts.map((acc) => (
                  <option key={acc.account_id} value={acc.account_id}>
                    {acc.account_name}
                  </option>
                ))}
              </select>
            </div>

            {["buy", "sell", "dividend"].includes(transactionType) && (
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Asset</label>
                <select
                  value={assetId}
                  onChange={(e) => setAssetId(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
                  required
                >
                  {assets.map((ast) => (
                    <option key={ast.asset_id} value={ast.asset_id}>
                      {ast.symbol} - {ast.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {["buy", "sell", "dividend"].includes(transactionType) && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Quantity</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 10"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Price Per Unit</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 150.50"
                  value={pricePerUnit}
                  onChange={(e) => setPricePerUnit(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Total Amount</label>
              <input
                type="number"
                step="any"
                placeholder="0.00"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500 font-semibold"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Brokerage Fees</label>
              <input
                type="number"
                step="any"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Taxes</label>
              <input
                type="number"
                step="any"
                value={taxes}
                onChange={(e) => setTaxes(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Notes</label>
            <input
              type="text"
              placeholder="Optional notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="mt-6 flex justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 font-semibold text-slate-950 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "Saving..." : (initialData ? "Update Transaction" : "Save Transaction")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
