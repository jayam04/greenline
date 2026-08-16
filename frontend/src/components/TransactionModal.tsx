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
      setError("");
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
        setTransactionType("buy");
        setTransactionDate(new Date().toISOString().split("T")[0]);
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
      setAccounts(accData || []);
      setAssets(astData || []);

      if (!initialData) {
        if (accData && accData.length > 0) {
          setAccountId(accData[0].account_id);
        }
        if (astData && astData.length > 0) {
          setAssetId(astData[0].asset_id);
        }
      }
    } catch (e: any) {
      console.error("Failed to load accounts/assets dropdowns:", e);
    }
  };

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

    if (!accountId) {
      setError("Please select an investment account.");
      setLoading(false);
      return;
    }

    const isAssetTransaction = ["buy", "sell", "dividend"].includes(transactionType);
    if (isAssetTransaction && !assetId) {
      setError("Please select a security from master.");
      setLoading(false);
      return;
    }

    const parsedTotal = parseFloat(totalAmount);
    if (isNaN(parsedTotal) || parsedTotal < 0) {
      setError("Please enter a valid total amount.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        account_id: Number(accountId),
        asset_id: isAssetTransaction && assetId ? Number(assetId) : null,
        transaction_type: transactionType,
        transaction_date: transactionDate,
        quantity: quantity ? parseFloat(quantity) : null,
        price_per_unit: pricePerUnit ? parseFloat(pricePerUnit) : null,
        total_amount: parsedTotal,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-lg shadow-xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2.5 mb-5">
          <div className="p-2 bg-[#0F172A] text-white rounded-xl">
            {initialData ? <Edit className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Transaction" : "Add Transaction"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400">Record buys, sells, dividends, deposits, or withdrawals</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-2.5 bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Transaction Type</label>
              <select
                value={transactionType}
                onChange={(e) => setTransactionType(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
                <option value="dividend">Dividend</option>
                <option value="deposit">Deposit (Cash In)</option>
                <option value="withdrawal">Withdrawal (Cash Out)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Date</label>
              <input
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Account</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
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
                <label className="block font-semibold text-slate-600 mb-1">Security / Asset</label>
                <select
                  value={assetId}
                  onChange={(e) => setAssetId(Number(e.target.value))}
                  className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
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
                <label className="block font-semibold text-slate-600 mb-1">Quantity</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 10"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required={transactionType === "buy" || transactionType === "sell"}
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-600 mb-1">Price Per Unit</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 150.50"
                  value={pricePerUnit}
                  onChange={(e) => setPricePerUnit(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required={transactionType === "buy" || transactionType === "sell"}
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Total Amount</label>
              <input
                type="number"
                step="any"
                placeholder="0.00"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Fees</label>
              <input
                type="number"
                step="any"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Taxes</label>
              <input
                type="number"
                step="any"
                value={taxes}
                onChange={(e) => setTaxes(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-600 mb-1">Notes</label>
            <input
              type="text"
              placeholder="Optional notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#F3F4F6] text-slate-900 font-medium rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="mt-5 flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill-gray text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-pill-black text-xs disabled:opacity-50"
            >
              {loading ? "Saving..." : (initialData ? "Update Transaction" : "Save Transaction")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
