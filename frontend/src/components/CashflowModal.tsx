"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  X, Plus, Edit, Trash2, CheckCircle2, AlertCircle, 
  ArrowDownLeft, ArrowUpRight, ArrowLeftRight, TrendingUp, 
  TrendingDown, Sparkles 
} from "lucide-react";
import { formatCurrency, getCurrencySymbol } from "@/lib/format";

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
  master_amount_eur?: number | null;
  transaction_kind?: string;
  notes?: string | null;
  payments: {
    payment_id?: number;
    account_id: number;
    account_name?: string;
    account_currency?: string;
    amount: number;
  }[];
  items: {
    item_id?: number;
    category_id: number;
    category_name?: string;
    category_type?: string;
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
  { key: "ESSENTIAL", label: "Essential (Need)" },
  { key: "DISCRETIONARY", label: "Discretionary (Want)" },
  { key: "LUXURY", label: "Luxury" },
  { key: "INVESTMENT", label: "Investment / Savings" },
];

export function isCategoryAllowedForKind(c: Category, kind: "EXPENSE" | "INCOME" | "TRANSFER"): boolean {
  if (kind === "TRANSFER") return c.category_type === "TRANSFER";
  if (kind === "INCOME") {
    if (c.category_type === "INCOME") return true;
    if (c.category_type === "INVESTMENT") {
      const name = (c.name || "").toLowerCase();
      // Hide purchase/outflow specific investment categories in income mode
      const isSpendOnly = name.includes("purchase") || name.includes("sip") || name.includes("allocation");
      return !isSpendOnly;
    }
    return false;
  } else {
    // EXPENSE
    if (c.category_type === "EXPENSE") return true;
    if (c.category_type === "INVESTMENT") {
      const name = (c.name || "").toLowerCase();
      // Hide income-specific investment categories in expense mode
      const isIncomeOnly = name.includes("dividend") || name.includes("rental") || name.includes("staking") || name.includes("gain");
      return !isIncomeOnly;
    }
    return false;
  }
}

type AccountMovement = {
  account_id: number | "";
  direction: "OUTFLOW" | "INFLOW"; // OUTFLOW = -Amount (spent/withdrawn), INFLOW = +Amount (deposit/received)
  amount: string;
};

type CategoryItem = {
  category_id: number | "";
  amount: string;
  label: string;
  description: string;
};

export function CashflowModal({ isOpen, onClose, onSuccess, initialData }: CashflowModalProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);

  // Transaction General Info
  const [title, setTitle] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split("T")[0]);
  const [currency, setCurrency] = useState("EUR");
  const [notes, setNotes] = useState("");

  // Unified Account Movements (+ / -)
  const [accountMovements, setAccountMovements] = useState<AccountMovement[]>([
    { account_id: "", direction: "OUTFLOW", amount: "" }
  ]);

  // Unified Category Allocations
  const [categoryItems, setCategoryItems] = useState<CategoryItem[]>([
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
    }
  }, [isOpen, initialData]);

  // Dismiss on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const loadDropdowns = async () => {
    try {
      const [accs, cats] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Category[]>("/categories"),
      ]);
      const loadedAccounts = accs || [];
      const loadedCategories = cats || [];
      setAccounts(loadedAccounts);
      setCategories(loadedCategories);

      if (initialData) {
        setTitle(initialData.title);
        setTransactionDate(initialData.transaction_date);
        setCurrency(initialData.currency || "EUR");
        setNotes(initialData.notes || "");

        // Populate Account Movements
        if (initialData.payments && initialData.payments.length > 0) {
          setAccountMovements(
            initialData.payments.map((p) => ({
              account_id: p.account_id,
              direction: p.amount >= 0 ? "INFLOW" : "OUTFLOW",
              amount: Math.abs(p.amount).toString()
            }))
          );
        }

        // Populate Category Items
        if (initialData.items && initialData.items.length > 0) {
          setCategoryItems(
            initialData.items.map((i) => ({
              category_id: i.category_id,
              amount: Math.abs(i.amount).toString(),
              label: i.label || "",
              description: i.description || ""
            }))
          );
        }
      } else {
        // Defaults for new transaction
        setTitle("");
        setTransactionDate(new Date().toISOString().split("T")[0]);
        setNotes("");

        const defaultAcc = loadedAccounts[0]?.account_id ?? "";
        const defaultCurr = loadedAccounts[0]?.currency ?? "EUR";
        setCurrency(defaultCurr);

        const defaultSpendCat = loadedCategories.find((c) => isCategoryAllowedForKind(c, "EXPENSE")) || loadedCategories[0];
        
        setAccountMovements([
          { account_id: defaultAcc, direction: "OUTFLOW", amount: "" }
        ]);
        setCategoryItems([
          {
            category_id: defaultSpendCat?.category_id ?? "",
            amount: "",
            label: defaultSpendCat?.effective_label ?? "DISCRETIONARY",
            description: ""
          }
        ]);
      }
    } catch (e) {
      console.error("Failed to load modal dropdowns:", e);
      setError("Failed to load accounts and categories.");
    }
  };

  // Preset Shortcuts: Spend, Income, Transfer
  const applyPreset = (type: "SPEND" | "INCOME" | "TRANSFER") => {
    setError("");
    const defaultAcc = accounts[0]?.account_id ?? "";
    const secondAcc = accounts[1]?.account_id ?? defaultAcc;

    if (type === "SPEND") {
      const spendCat = categories.find((c) => isCategoryAllowedForKind(c, "EXPENSE")) || categories[0];
      setAccountMovements([
        { account_id: defaultAcc, direction: "OUTFLOW", amount: accountMovements[0]?.amount || "" }
      ]);
      setCategoryItems([
        {
          category_id: spendCat?.category_id ?? "",
          amount: categoryItems[0]?.amount || accountMovements[0]?.amount || "",
          label: spendCat?.effective_label ?? "DISCRETIONARY",
          description: categoryItems[0]?.description || ""
        }
      ]);
    } else if (type === "INCOME") {
      const incomeCat = categories.find((c) => isCategoryAllowedForKind(c, "INCOME")) || categories[0];
      setAccountMovements([
        { account_id: defaultAcc, direction: "INFLOW", amount: accountMovements[0]?.amount || "" }
      ]);
      setCategoryItems([
        {
          category_id: incomeCat?.category_id ?? "",
          amount: categoryItems[0]?.amount || accountMovements[0]?.amount || "",
          label: incomeCat?.effective_label ?? "ESSENTIAL",
          description: categoryItems[0]?.description || ""
        }
      ]);
    } else if (type === "TRANSFER") {
      const transCat = categories.find((c) => c.category_type === "TRANSFER") || categories[0];
      const amt = accountMovements[0]?.amount || "";
      setAccountMovements([
        { account_id: defaultAcc, direction: "OUTFLOW", amount: amt },
        { account_id: secondAcc, direction: "INFLOW", amount: amt }
      ]);
      setCategoryItems([
        {
          category_id: transCat?.category_id ?? "",
          amount: amt,
          label: "ESSENTIAL",
          description: "Internal Transfer"
        }
      ]);
    }
  };

  // Calculations
  const netAccountMovement = useMemo(() => {
    return accountMovements.reduce((sum, p) => {
      const val = parseFloat(p.amount) || 0;
      return sum + (p.direction === "INFLOW" ? val : -val);
    }, 0);
  }, [accountMovements]);

  const totalCategoryAllocation = useMemo(() => {
    return categoryItems.reduce((sum, i) => sum + (parseFloat(i.amount) || 0), 0);
  }, [categoryItems]);

  const isPureTransfer = useMemo(() => {
    return accountMovements.length > 1 && Math.abs(netAccountMovement) < 0.01;
  }, [accountMovements, netAccountMovement]);

  // Balance difference
  const balanceDiff = useMemo(() => {
    if (isPureTransfer) {
      const outflow = accountMovements.find(p => p.direction === "OUTFLOW");
      const transferAmt = parseFloat(outflow?.amount || "0") || 0;
      return transferAmt - totalCategoryAllocation;
    }
    return Math.abs(netAccountMovement) - totalCategoryAllocation;
  }, [isPureTransfer, accountMovements, netAccountMovement, totalCategoryAllocation]);

  const isBalanced = Math.abs(balanceDiff) < 0.01 && (totalCategoryAllocation > 0 || isPureTransfer);

  const currencySymbol = useMemo(() => getCurrencySymbol(currency), [currency]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!title.trim()) {
      setError("Please enter a transaction title.");
      return;
    }

    if (accountMovements.some(p => !p.account_id || !(parseFloat(p.amount) > 0))) {
      setError("Please fill in valid accounts and non-zero amounts for all account rows.");
      return;
    }

    if (categoryItems.some(i => !i.category_id || !(parseFloat(i.amount) > 0))) {
      setError("Please fill in valid categories and amounts for all category rows.");
      return;
    }

    if (Math.abs(balanceDiff) > 0.05) {
      setError(
        `Account cash flow (${formatCurrency(Math.abs(netAccountMovement), currency)}) does not match category allocation (${formatCurrency(totalCategoryAllocation, currency)}).`
      );
      return;
    }

    setLoading(true);

    try {
      // Build signed payments payload
      const paymentsPayload = accountMovements.map((p) => ({
        account_id: Number(p.account_id),
        amount: p.direction === "INFLOW" ? parseFloat(p.amount) : -parseFloat(p.amount)
      }));

      // Build items payload
      const itemsPayload = categoryItems.map((i) => ({
        category_id: Number(i.category_id),
        amount: parseFloat(i.amount),
        label: i.label || null,
        description: i.description.trim() || null
      }));

      // Resolved transaction kind
      const resolvedKind = isPureTransfer
        ? "TRANSFER"
        : netAccountMovement > 0
        ? "INCOME"
        : "EXPENSE";

      const payload = {
        transaction_date: transactionDate,
        title: title.trim(),
        currency,
        transaction_kind: resolvedKind,
        notes: notes.trim() || null,
        payments: paymentsPayload,
        items: itemsPayload
      };

      if (initialData) {
        await apiFetch(`/cashflow/${initialData.cashflow_id}`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch("/cashflow", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }

      setSuccessBanner("Transaction saved successfully!");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 500);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to save transaction.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto font-sans"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-[#121824] rounded-2xl w-full max-w-2xl shadow-2xl border border-slate-200 dark:border-slate-800 my-8 overflow-hidden relative max-h-[90vh] flex flex-col">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
          <div>
            <h2 className="text-base font-bold text-[#0F172A] dark:text-white flex items-center gap-2">
              {initialData ? <Edit className="w-4 h-4 text-blue-500" /> : <Plus className="w-4 h-4 text-emerald-500" />}
              {initialData ? "Edit Transaction" : "Record Transaction"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500 mt-0.5">
              Unified cashflow entry with signed account flows and category allocations
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Presets Bar */}
        <div className="px-5 pt-3 pb-1 flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-[#121824]">
          <span className="text-[11px] font-bold text-slate-400">Quick Presets:</span>
          <button
            type="button"
            onClick={() => applyPreset("SPEND")}
            className="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 hover:bg-rose-100 border border-rose-200 dark:border-rose-800 flex items-center gap-1.5 cursor-pointer transition-all"
          >
            <TrendingDown className="w-3.5 h-3.5" /> Spend (Outflow)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("INCOME")}
            className="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1.5 cursor-pointer transition-all"
          >
            <TrendingUp className="w-3.5 h-3.5" /> Income (Inflow)
          </button>
          <button
            type="button"
            onClick={() => applyPreset("TRANSFER")}
            className="px-2.5 py-1 rounded-lg text-xs font-bold bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 hover:bg-purple-100 border border-purple-200 dark:border-purple-800 flex items-center gap-1.5 cursor-pointer transition-all"
          >
            <ArrowLeftRight className="w-3.5 h-3.5" /> Transfer (A &rarr; B)
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {error && (
            <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs font-bold rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successBanner && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 text-xs font-bold rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successBanner}</span>
            </div>
          )}

          {/* Core Info: Title, Date, Currency */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-1.5">
              <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                Transaction Title <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Dinner with friends, August Salary"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 focus:outline-none text-xs"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 focus:outline-none text-xs"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-500 mb-1">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 focus:outline-none text-xs cursor-pointer"
              >
                {["EUR", "USD", "INR", "GBP", "CAD", "AUD", "JPY", "CHF", "SGD"].map((c) => (
                  <option key={c} value={c}>
                    {c} ({getCurrencySymbol(c)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Section 1: Account Movements (Money in / out) */}
          <div className="space-y-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#0F172A] dark:text-white flex items-center gap-1.5">
                <ArrowDownLeft className="w-3.5 h-3.5 text-blue-500" /> Account Movements (Money In / Out)
              </label>
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                netAccountMovement < -0.01
                  ? "bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400"
                  : netAccountMovement > 0.01
                  ? "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400"
                  : "bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400"
              }`}>
                {netAccountMovement < -0.01 && `Net Outflow: ${formatCurrency(Math.abs(netAccountMovement), currency)}`}
                {netAccountMovement > 0.01 && `Net Inflow: +${formatCurrency(netAccountMovement, currency)}`}
                {Math.abs(netAccountMovement) <= 0.01 && `Net Cashflow: ${formatCurrency(0, currency)} (Balanced)`}
              </span>
            </div>

            <div className="space-y-2">
              {accountMovements.map((movement, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700">
                  {/* Account Selector */}
                  <select
                    value={movement.account_id}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setAccountMovements((prev) =>
                        prev.map((p, i) => (i === idx ? { ...p, account_id: val } : p))
                      );
                    }}
                    className="flex-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 text-xs"
                    required
                  >
                    <option value="">Select Account</option>
                    {accounts.map((a) => (
                      <option key={a.account_id} value={a.account_id}>
                        {a.account_name} ({a.currency || "EUR"})
                      </option>
                    ))}
                  </select>

                  {/* Inflow / Outflow Direction Toggle */}
                  <div className="flex items-center bg-slate-200 dark:bg-slate-700 p-0.5 rounded-lg text-xs font-bold shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        setAccountMovements((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, direction: "OUTFLOW" } : p))
                        );
                      }}
                      className={`px-2 py-1 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                        movement.direction === "OUTFLOW"
                          ? "bg-rose-500 text-white shadow-xs"
                          : "text-slate-600 dark:text-slate-300 hover:text-black dark:hover:text-white"
                      }`}
                    >
                      - Outflow
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setAccountMovements((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, direction: "INFLOW" } : p))
                        );
                      }}
                      className={`px-2 py-1 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                        movement.direction === "INFLOW"
                          ? "bg-emerald-500 text-white shadow-xs"
                          : "text-slate-600 dark:text-slate-300 hover:text-black dark:hover:text-white"
                      }`}
                    >
                      + Inflow
                    </button>
                  </div>

                  {/* Amount */}
                  <div className="relative flex items-center w-28 shrink-0">
                    <span className="absolute left-2.5 text-slate-400 font-bold text-xs pointer-events-none">
                      {currencySymbol}
                    </span>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      placeholder="0.00"
                      value={movement.amount}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAccountMovements((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, amount: val } : p))
                        );
                      }}
                      className="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-bold tabular-nums rounded-lg pl-6 pr-2 py-1.5 border border-slate-200 dark:border-slate-700 text-xs text-right"
                      required
                    />
                  </div>

                  {/* Delete Button */}
                  {accountMovements.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setAccountMovements((prev) => prev.filter((_, i) => i !== idx))}
                      className="p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}

              <button
                type="button"
                onClick={() => {
                  setAccountMovements((prev) => [
                    ...prev,
                    {
                      account_id: accounts[0]?.account_id ?? "",
                      direction: "INFLOW",
                      amount: ""
                    }
                  ]);
                }}
                className="text-[11px] font-bold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer pt-1"
              >
                <Plus className="w-3 h-3" /> Add Account (Multi-account, Reimbursement, or Transfer)
              </button>
            </div>
          </div>

          {/* Section 2: Category Breakdown (Allocations) */}
          <div className="space-y-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#0F172A] dark:text-white flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-purple-500" /> Category Breakdown & Purpose
              </label>
              <span className="text-[11px] font-bold text-slate-500">
                Total Allocated: <strong className="text-[#0F172A] dark:text-white">{formatCurrency(totalCategoryAllocation, currency)}</strong>
              </span>
            </div>

            <div className="space-y-2">
              {categoryItems.map((item, idx) => (
                <div key={idx} className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
                  <div className="flex items-center gap-2">
                    {/* Category Selector */}
                    <select
                      value={item.category_id}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        const found = categories.find((c) => c.category_id === val);
                        setCategoryItems((prev) =>
                          prev.map((itm, i) =>
                            i === idx
                              ? {
                                  ...itm,
                                  category_id: val,
                                  label: itm.label || found?.effective_label || "DISCRETIONARY"
                                }
                              : itm
                          )
                        );
                      }}
                      className="flex-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 text-xs"
                      required
                    >
                      <option value="">Select Category</option>
                      {categories.map((c) => (
                        <option key={c.category_id} value={c.category_id}>
                          {c.full_path || c.name} ({c.category_type})
                        </option>
                      ))}
                    </select>

                    {/* Amount */}
                    <div className="relative flex items-center w-28 shrink-0">
                      <span className="absolute left-2.5 text-slate-400 font-bold text-xs pointer-events-none">
                        {currencySymbol}
                      </span>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        placeholder="0.00"
                        value={item.amount}
                        onChange={(e) => {
                          const val = e.target.value;
                          setCategoryItems((prev) =>
                            prev.map((itm, i) => (i === idx ? { ...itm, amount: val } : itm))
                          );
                        }}
                        className="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-bold tabular-nums rounded-lg pl-6 pr-2 py-1.5 border border-slate-200 dark:border-slate-700 text-xs text-right"
                        required
                      />
                    </div>

                    {categoryItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setCategoryItems((prev) => prev.filter((_, i) => i !== idx))}
                        className="p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="Item description (e.g. Dinner share, Groceries, Base Salary)"
                      value={item.description}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCategoryItems((prev) =>
                          prev.map((itm, i) => (i === idx ? { ...itm, description: val } : itm))
                        );
                      }}
                      className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-medium rounded-lg px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 text-xs"
                      required
                    />

                    <select
                      value={item.label}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCategoryItems((prev) =>
                          prev.map((itm, i) => (i === idx ? { ...itm, label: val } : itm))
                        );
                      }}
                      className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 text-xs"
                    >
                      <option value="">Inherit Classification</option>
                      {CLASSIFICATION_LABELS.map((lbl) => (
                        <option key={lbl.key} value={lbl.key}>
                          {lbl.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}

              <button
                type="button"
                onClick={() => {
                  const defaultCat = categories[0];
                  // Auto-fill remaining balance if any
                  const remaining = Math.max(0, Math.abs(netAccountMovement) - totalCategoryAllocation);
                  setCategoryItems((prev) => [
                    ...prev,
                    {
                      category_id: defaultCat?.category_id ?? "",
                      amount: remaining > 0 ? remaining.toFixed(2) : "",
                      label: defaultCat?.effective_label ?? "DISCRETIONARY",
                      description: ""
                    }
                  ]);
                }}
                className="text-[11px] font-bold text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1 cursor-pointer pt-1"
              >
                <Plus className="w-3 h-3" /> Add Category Split Line
              </button>
            </div>
          </div>

          {/* Live Balance Banner */}
          <div className={`p-3 rounded-xl border text-xs font-semibold flex items-center justify-between ${
            isBalanced
              ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
              : "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
          }`}>
            <div className="flex items-center gap-2">
              {isBalanced ? <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> : <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />}
              <span>
                {isBalanced
                  ? `Balanced: Accounts (${formatCurrency(Math.abs(netAccountMovement) || totalCategoryAllocation, currency)}) = Categories (${formatCurrency(totalCategoryAllocation, currency)})`
                  : `Unbalanced: Remaining ${formatCurrency(Math.abs(balanceDiff), currency)} to allocate`}
              </span>
            </div>
            <span className="font-bold tabular-nums">
              {isBalanced ? "Ready to Save" : `Diff: ${formatCurrency(balanceDiff, currency)}`}
            </span>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Notes (Optional)</label>
            <input
              type="text"
              placeholder="Additional remarks or details"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-medium rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 focus:outline-none text-xs"
            />
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !isBalanced}
              className="px-5 py-2 rounded-xl text-xs font-bold bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] hover:bg-slate-800 dark:hover:bg-slate-100 transition-all shadow-md disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {loading ? "Saving..." : initialData ? "Update Transaction" : "Record Transaction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
