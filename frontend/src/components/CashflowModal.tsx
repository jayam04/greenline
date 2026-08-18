"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { 
  X, Plus, Edit, Trash2, Split, CheckCircle2, AlertCircle, 
  Layers, ArrowDownLeft, ArrowUpRight, Sparkles 
} from "lucide-react";
import { formatCurrency } from "@/lib/format";

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
}

interface Category {
  category_id: number;
  name: string;
  category_type: string;
  default_label?: string | null;
  effective_label?: string | null;
  full_path?: string | null;
  level?: number;
}

export interface CashflowTransactionItem {
  cashflow_id: number;
  transaction_date: string;
  title: string;
  total_amount: number;
  currency: string;
  notes?: string | null;
  payments: {
    payment_id?: number;
    account_id: number;
    account_name?: string;
    amount: number;
  }[];
  items: {
    item_id?: number;
    category_id: number;
    category_name?: string;
    amount: number;
    label?: string | null;
    effective_label?: string | null;
    description?: string | null;
  }[];
}

interface CashflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialData?: CashflowTransactionItem | null;
}

const CLASSIFICATION_LABELS = [
  { key: "ESSENTIAL", label: "Essential (Need)", color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { key: "DISCRETIONARY", label: "Discretionary (Want)", color: "bg-amber-50 text-amber-700 border-amber-200" },
  { key: "LUXURY", label: "Luxury", color: "bg-pink-50 text-pink-700 border-pink-200" },
  { key: "INVESTMENT", label: "Investment / Savings", color: "bg-blue-50 text-blue-700 border-blue-200" },
];

export function CashflowModal({ isOpen, onClose, onSuccess, initialData }: CashflowModalProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);

  // Form State
  const [title, setTitle] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split("T")[0]);
  const [totalAmount, setTotalAmount] = useState("");
  const [notes, setNotes] = useState("");

  // Simple Mode vs Split Modes
  const [isSplitPayments, setIsSplitPayments] = useState(false);
  const [isSplitItems, setIsSplitItems] = useState(false);

  // Single mode state
  const [simpleAccountId, setSimpleAccountId] = useState<number | "">("");
  const [simpleCategoryId, setSimpleCategoryId] = useState<number | "">("");
  const [simpleLabel, setSimpleLabel] = useState<string>("");

  // Advanced Split Arrays
  const [payments, setPayments] = useState<{ account_id: number | ""; amount: string }[]>([
    { account_id: "", amount: "" }
  ]);
  const [items, setItems] = useState<{ category_id: number | ""; amount: string; label: string; description: string }[]>([
    { category_id: "", amount: "", label: "", description: "" }
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successBanner, setSuccessBanner] = useState("");

  useEffect(() => {
    if (isOpen) {
      setError("");
      setSuccessBanner("");
      loadDropdowns();

      if (initialData) {
        setTitle(initialData.title);
        setTransactionDate(initialData.transaction_date);
        setTotalAmount(initialData.total_amount.toString());
        setNotes(initialData.notes || "");

        const hasMultiplePayments = initialData.payments.length > 1;
        const hasMultipleItems = initialData.items.length > 1;
        setIsSplitPayments(hasMultiplePayments);
        setIsSplitItems(hasMultipleItems);

        if (initialData.payments.length > 0) {
          setSimpleAccountId(initialData.payments[0].account_id);
          setPayments(initialData.payments.map((p) => ({ account_id: p.account_id, amount: p.amount.toString() })));
        }
        if (initialData.items.length > 0) {
          setSimpleCategoryId(initialData.items[0].category_id);
          setSimpleLabel(initialData.items[0].label || "");
          setItems(initialData.items.map((i) => ({
            category_id: i.category_id,
            amount: i.amount.toString(),
            label: i.label || "",
            description: i.description || ""
          })));
        }
      } else {
        setTitle("");
        setTransactionDate(new Date().toISOString().split("T")[0]);
        setTotalAmount("");
        setNotes("");
        setIsSplitPayments(false);
        setIsSplitItems(false);
        setSimpleLabel("");
        setPayments([{ account_id: "", amount: "" }]);
        setItems([{ category_id: "", amount: "", label: "", description: "" }]);
      }
    }
  }, [isOpen, initialData]);

  const loadDropdowns = async () => {
    try {
      const [accs, cats] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Category[]>("/categories"),
      ]);
      setAccounts(accs || []);
      setCategories(cats || []);

      if (!initialData) {
        if (accs && accs.length > 0) {
          setSimpleAccountId(accs[0].account_id);
          setPayments([{ account_id: accs[0].account_id, amount: "" }]);
        }
        if (cats && cats.length > 0) {
          setSimpleCategoryId(cats[0].category_id);
          setItems([{ category_id: cats[0].category_id, amount: "", label: "", description: "" }]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Sync category default label when simpleCategoryId changes
  useEffect(() => {
    if (simpleCategoryId && !simpleLabel) {
      const found = categories.find((c) => c.category_id === simpleCategoryId);
      if (found?.effective_label) {
        setSimpleLabel(found.effective_label);
      }
    }
  }, [simpleCategoryId, categories, simpleLabel]);

  // Balance checking calculations
  const parsedTotal = parseFloat(totalAmount) || 0;
  const totalPaymentsSum = isSplitPayments
    ? payments.reduce((acc, p) => acc + (parseFloat(p.amount) || 0), 0)
    : parsedTotal;
  const totalItemsSum = isSplitItems
    ? items.reduce((acc, i) => acc + (parseFloat(i.amount) || 0), 0)
    : parsedTotal;

  const paymentBalanceDiff = parsedTotal - totalPaymentsSum;
  const itemBalanceDiff = parsedTotal - totalItemsSum;

  if (!isOpen) return null;

  const handleSubmit = async (e?: React.FormEvent, isAddNew: boolean = false) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError("");
    setSuccessBanner("");

    if (!title.trim()) {
      setError("Please enter a transaction title.");
      setLoading(false);
      return;
    }

    if (parsedTotal <= 0) {
      setError("Please enter a valid total amount.");
      setLoading(false);
      return;
    }

    // Build payload
    const finalPayments = isSplitPayments
      ? payments.map((p) => ({ account_id: Number(p.account_id), amount: parseFloat(p.amount) || 0 }))
      : [{ account_id: Number(simpleAccountId), amount: parsedTotal }];

    const finalItems = isSplitItems
      ? items.map((i) => ({
          category_id: Number(i.category_id),
          amount: parseFloat(i.amount) || 0,
          label: i.label ? i.label.toUpperCase() : null,
          description: i.description || null,
        }))
      : [{
          category_id: Number(simpleCategoryId),
          amount: parsedTotal,
          label: simpleLabel ? simpleLabel.toUpperCase() : null,
          description: title.trim(),
        }];

    // Validate splits
    if (isSplitPayments && Math.abs(paymentBalanceDiff) > 0.01) {
      setError(`Payment methods sum (${formatCurrency(totalPaymentsSum, "EUR")}) must equal Total Amount (${formatCurrency(parsedTotal, "EUR")}). Remaining: ${formatCurrency(paymentBalanceDiff, "EUR")}`);
      setLoading(false);
      return;
    }

    if (isSplitItems && Math.abs(itemBalanceDiff) > 0.01) {
      setError(`Category items sum (${formatCurrency(totalItemsSum, "EUR")}) must equal Total Amount (${formatCurrency(parsedTotal, "EUR")}). Remaining: ${formatCurrency(itemBalanceDiff, "EUR")}`);
      setLoading(false);
      return;
    }

    try {
      const payload = {
        transaction_date: transactionDate,
        title: title.trim(),
        total_amount: parsedTotal,
        currency: "EUR",
        notes: notes || null,
        payments: finalPayments,
        items: finalItems,
      };

      if (initialData) {
        await apiFetch(`/cashflow/${initialData.cashflow_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        onSuccess();
        onClose();
      } else {
        await apiFetch("/cashflow", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        onSuccess();

        if (isAddNew) {
          setSuccessBanner("Transaction saved successfully! Enter next spend or income below.");
          setTitle("");
          setTotalAmount("");
          setNotes("");
          setPayments([{ account_id: simpleAccountId || accounts[0]?.account_id || "", amount: "" }]);
          setItems([{ category_id: simpleCategoryId || categories[0]?.category_id || "", amount: "", label: "", description: "" }]);
        } else {
          onClose();
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to save cashflow transaction");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-2xl shadow-xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2.5 mb-4">
          <div className="p-2 bg-[#0F172A] text-white rounded-xl">
            {initialData ? <Edit className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Income / Spend" : "Record Income or Spend"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Track salary, Amazon purchases, groceries, split payments & multi-category receipts
            </p>
          </div>
        </div>

        {successBanner && (
          <div className="mb-3.5 p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold rounded-lg flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>{successBanner}</span>
          </div>
        )}

        {error && (
          <div className="mb-3.5 p-2.5 bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={(e) => handleSubmit(e, false)} className="space-y-4 text-xs">
          {/* Header Row: Title, Date, Total Amount */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-1">
              <label className="block font-semibold text-slate-600 mb-1">Title / Merchant</label>
              <input
                type="text"
                placeholder="e.g. Amazon Order, Base Salary"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Date</label>
              <input
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Total Amount (€)</label>
              <input
                type="number"
                step="any"
                placeholder="0.00"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold text-sm rounded-lg px-3 py-1.5 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>
          </div>

          {/* Section 1: Payment Method(s) */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5">
                <ArrowDownLeft className="w-3.5 h-3.5 text-blue-600" />
                Payment Method / Funding Source
              </span>
              <button
                type="button"
                onClick={() => {
                  setIsSplitPayments(!isSplitPayments);
                  if (!isSplitPayments && payments.length === 1 && totalAmount) {
                    setPayments([{ account_id: simpleAccountId || accounts[0]?.account_id || "", amount: totalAmount }]);
                  }
                }}
                className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
              >
                <Split className="w-3 h-3" />
                {isSplitPayments ? "Use Single Account" : "Split Multiple Accounts"}
              </button>
            </div>

            {!isSplitPayments ? (
              <div>
                <select
                  value={simpleAccountId}
                  onChange={(e) => setSimpleAccountId(Number(e.target.value))}
                  className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:outline-none cursor-pointer"
                  required
                >
                  {accounts.map((acc) => (
                    <option key={acc.account_id} value={acc.account_id}>
                      {acc.account_name} ({acc.currency})
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="space-y-2">
                {payments.map((p, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <select
                      value={p.account_id}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        setPayments((prev) => prev.map((item, i) => i === idx ? { ...item, account_id: val } : item));
                      }}
                      className="flex-1 bg-white text-slate-900 font-semibold rounded-lg px-3 py-1.5 border border-slate-200 focus:outline-none text-xs"
                      required
                    >
                      <option value="">Select Account</option>
                      {accounts.map((acc) => (
                        <option key={acc.account_id} value={acc.account_id}>
                          {acc.account_name}
                        </option>
                      ))}
                    </select>

                    <input
                      type="number"
                      step="any"
                      placeholder="Amount"
                      value={p.amount}
                      onChange={(e) => {
                        const val = e.target.value;
                        setPayments((prev) => prev.map((item, i) => i === idx ? { ...item, amount: val } : item));
                      }}
                      className="w-28 bg-white text-slate-900 font-bold tabular-nums rounded-lg px-3 py-1.5 border border-slate-200 focus:outline-none text-xs"
                      required
                    />

                    {payments.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setPayments((prev) => prev.filter((_, i) => i !== idx))}
                        className="p-1.5 text-rose-500 hover:bg-rose-50 rounded-lg cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}

                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => setPayments((prev) => [...prev, { account_id: accounts[0]?.account_id || "", amount: "" }])}
                    className="text-[11px] font-bold text-slate-700 hover:text-black flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Add Payment Account
                  </button>

                  <div className="text-[11px] font-bold">
                    {Math.abs(paymentBalanceDiff) < 0.01 ? (
                      <span className="text-emerald-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Balanced: {formatCurrency(totalPaymentsSum, "EUR")}
                      </span>
                    ) : (
                      <span className="text-rose-600">
                        Remaining: {formatCurrency(paymentBalanceDiff, "EUR")}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: Categories / Itemization */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5">
                <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
                Category & Classification
              </span>
              <button
                type="button"
                onClick={() => {
                  setIsSplitItems(!isSplitItems);
                  if (!isSplitItems && items.length === 1 && totalAmount) {
                    setItems([{ category_id: simpleCategoryId || categories[0]?.category_id || "", amount: totalAmount, label: simpleLabel, description: title }]);
                  }
                }}
                className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
              >
                <Split className="w-3 h-3" />
                {isSplitItems ? "Single Category" : "Split Multiple Categories"}
              </button>
            </div>

            {!isSplitItems ? (
              <div className="space-y-2">
                <select
                  value={simpleCategoryId}
                  onChange={(e) => {
                    const catId = Number(e.target.value);
                    setSimpleCategoryId(catId);
                    const found = categories.find((c) => c.category_id === catId);
                    if (found?.effective_label) setSimpleLabel(found.effective_label);
                  }}
                  className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:outline-none cursor-pointer"
                  required
                >
                  {categories.map((c) => (
                    <option key={c.category_id} value={c.category_id}>
                      {c.full_path || c.name} ({c.category_type})
                    </option>
                  ))}
                </select>

                {/* Label Override Selector */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                    Classification Label (Inherited: <span className="font-bold">{categories.find(c => c.category_id === simpleCategoryId)?.effective_label || "None"}</span>)
                  </label>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {CLASSIFICATION_LABELS.map((lbl) => (
                      <button
                        key={lbl.key}
                        type="button"
                        onClick={() => setSimpleLabel(lbl.key)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-bold border transition-all cursor-pointer ${
                          simpleLabel === lbl.key
                            ? "bg-[#0F172A] text-white border-[#0F172A]"
                            : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        {lbl.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-2.5">
                {items.map((itm, idx) => (
                  <div key={idx} className="p-2.5 bg-white rounded-lg border border-slate-200 space-y-2">
                    <div className="flex items-center gap-2">
                      <select
                        value={itm.category_id}
                        onChange={(e) => {
                          const val = Number(e.target.value);
                          const found = categories.find((c) => c.category_id === val);
                          setItems((prev) =>
                            prev.map((item, i) =>
                              i === idx ? { ...item, category_id: val, label: item.label || found?.effective_label || "" } : item
                            )
                          );
                        }}
                        className="flex-1 bg-slate-50 text-slate-900 font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 text-xs"
                        required
                      >
                        <option value="">Select Category</option>
                        {categories.map((c) => (
                          <option key={c.category_id} value={c.category_id}>
                            {c.full_path || c.name}
                          </option>
                        ))}
                      </select>

                      <input
                        type="number"
                        step="any"
                        placeholder="Amount"
                        value={itm.amount}
                        onChange={(e) => {
                          const val = e.target.value;
                          setItems((prev) => prev.map((item, i) => i === idx ? { ...item, amount: val } : item));
                        }}
                        className="w-24 bg-slate-50 text-slate-900 font-bold tabular-nums rounded-lg px-2.5 py-1.5 border border-slate-200 text-xs"
                        required
                      />

                      {items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))}
                          className="p-1.5 text-rose-500 hover:bg-rose-50 rounded-lg cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="Item description (e.g. Speakers, Groceries)"
                        value={itm.description}
                        onChange={(e) => {
                          const val = e.target.value;
                          setItems((prev) => prev.map((item, i) => i === idx ? { ...item, description: val } : item));
                        }}
                        className="bg-slate-50 text-slate-800 font-medium rounded-lg px-2.5 py-1 border border-slate-200 text-[11px]"
                      />

                      <select
                        value={itm.label}
                        onChange={(e) => {
                          const val = e.target.value;
                          setItems((prev) => prev.map((item, i) => i === idx ? { ...item, label: val } : item));
                        }}
                        className="bg-slate-50 text-slate-800 font-bold rounded-lg px-2.5 py-1 border border-slate-200 text-[11px]"
                      >
                        <option value="">Use Category Default</option>
                        <option value="ESSENTIAL">Essential (Need)</option>
                        <option value="DISCRETIONARY">Discretionary (Want)</option>
                        <option value="LUXURY">Luxury</option>
                        <option value="INVESTMENT">Investment</option>
                      </select>
                    </div>
                  </div>
                ))}

                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => setItems((prev) => [...prev, { category_id: categories[0]?.category_id || "", amount: "", label: "", description: "" }])}
                    className="text-[11px] font-bold text-slate-700 hover:text-black flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Add Category Split Line
                  </button>

                  <div className="text-[11px] font-bold">
                    {Math.abs(itemBalanceDiff) < 0.01 ? (
                      <span className="text-emerald-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Balanced: {formatCurrency(totalItemsSum, "EUR")}
                      </span>
                    ) : (
                      <span className="text-rose-600">
                        Remaining: {formatCurrency(itemBalanceDiff, "EUR")}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block font-semibold text-slate-600 mb-1">Notes / Tags (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Reimbursement pending, Prime Day sale"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#F3F4F6] text-slate-900 font-medium rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Footer Actions */}
          <div className="mt-5 flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill-gray text-xs cursor-pointer"
            >
              Cancel
            </button>
            
            {!initialData && (
              <button
                type="button"
                onClick={() => handleSubmit(undefined, true)}
                disabled={loading}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-lg text-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                {loading ? "Saving..." : "Save & Add Another"}
              </button>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-pill-black text-xs disabled:opacity-50 cursor-pointer"
            >
              {loading ? "Saving..." : (initialData ? "Update Transaction" : "Save Transaction")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
