"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  X, Plus, Edit, Trash2, Split, CheckCircle2, AlertCircle, 
  ArrowDownLeft, ArrowUpRight, ArrowLeftRight, TrendingUp, 
  TrendingDown, RefreshCw 
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

export function CashflowModal({ isOpen, onClose, onSuccess, initialData }: CashflowModalProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);

  // Transaction Kind: EXPENSE, INCOME, TRANSFER
  const [transactionKind, setTransactionKind] = useState<"EXPENSE" | "INCOME" | "TRANSFER">("EXPENSE");

  // Form State
  const [title, setTitle] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split("T")[0]);
  const [notes, setNotes] = useState("");

  // Simple Mode vs Split Modes
  const [isSplitPayments, setIsSplitPayments] = useState(false);
  const [isSplitItems, setIsSplitItems] = useState(false);

  // Single mode state
  const [simpleAccountId, setSimpleAccountId] = useState<number | "">("");
  const [simpleAmount, setSimpleAmount] = useState<string>("");
  const [simpleCategoryId, setSimpleCategoryId] = useState<number | "">("");
  const [simpleDescription, setSimpleDescription] = useState<string>("");
  const [simpleLabel, setSimpleLabel] = useState<string>("");

  // Transfer Mode State
  const [fromAccountId, setFromAccountId] = useState<number | "">("");
  const [fromAmount, setFromAmount] = useState<string>("");
  const [toAccountId, setToAccountId] = useState<number | "">("");
  const [toAmount, setToAmount] = useState<string>("");
  const [hasTransferFee, setHasTransferFee] = useState(false);
  const [feeAmount, setFeeAmount] = useState<string>("");

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
    }
  }, [isOpen, initialData]);

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
        setNotes(initialData.notes || "");

        const isTransferTx = initialData.items.some((i) => i.category_type === "TRANSFER") || initialData.payments.some((p) => p.amount < 0);
        if (isTransferTx) {
          setTransactionKind("TRANSFER");
          const outPayment = initialData.payments.find((p) => p.amount < 0) || initialData.payments[0];
          const inPayment = initialData.payments.find((p) => p.amount > 0) || initialData.payments[1] || initialData.payments[0];
          if (outPayment) {
            setFromAccountId(outPayment.account_id);
            setFromAmount(Math.abs(outPayment.amount).toString());
          }
          if (inPayment) {
            setToAccountId(inPayment.account_id);
            setToAmount(Math.abs(inPayment.amount).toString());
          }
        } else {
          const isIncomeTx = initialData.items.some((i) => i.category_type === "INCOME");
          setTransactionKind(isIncomeTx ? "INCOME" : "EXPENSE");

          const hasMultiplePayments = initialData.payments.length > 1;
          const hasMultipleItems = initialData.items.length > 1;
          setIsSplitPayments(hasMultiplePayments);
          setIsSplitItems(hasMultipleItems);

          if (initialData.payments.length > 0) {
            setSimpleAccountId(initialData.payments[0].account_id);
            setSimpleAmount(initialData.payments[0].amount.toString());
            setPayments(initialData.payments.map((p) => ({ account_id: p.account_id, amount: p.amount.toString() })));
          }
          if (initialData.items.length > 0) {
            setSimpleCategoryId(initialData.items[0].category_id);
            setSimpleDescription(initialData.items[0].description || "");
            setSimpleLabel(initialData.items[0].label || "");
            setItems(initialData.items.map((i) => ({
              category_id: i.category_id,
              amount: i.amount.toString(),
              label: i.label || "",
              description: i.description || ""
            })));
          }
        }
      } else {
        setTransactionKind("EXPENSE");
        setTitle("");
        setTransactionDate(new Date().toISOString().split("T")[0]);
        setNotes("");
        setIsSplitPayments(false);
        setIsSplitItems(false);
        setSimpleAmount("");
        setSimpleDescription("");
        setSimpleLabel("");
        setFromAmount("");
        setToAmount("");
        setHasTransferFee(false);
        setFeeAmount("");

        if (loadedAccounts.length > 0) {
          setSimpleAccountId(loadedAccounts[0].account_id);
          setFromAccountId(loadedAccounts[0].account_id);
          setToAccountId(loadedAccounts.length > 1 ? loadedAccounts[1].account_id : loadedAccounts[0].account_id);
          setPayments([{ account_id: loadedAccounts[0].account_id, amount: "" }]);
        }

        if (loadedCategories.length > 0) {
          const defaultExpCat = loadedCategories.find((c) => c.category_type === "EXPENSE") || loadedCategories[0];
          setSimpleCategoryId(defaultExpCat.category_id);
          setSimpleLabel(defaultExpCat.effective_label || "DISCRETIONARY");
          setItems([{ category_id: defaultExpCat.category_id, amount: "", label: "", description: "" }]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Switch Transaction Kind Handler (Syncs category appropriately)
  const handleSwitchKind = (newKind: "EXPENSE" | "INCOME" | "TRANSFER") => {
    setTransactionKind(newKind);
    setError("");

    if (newKind === "INCOME") {
      const incomeCat = categories.find((c) => c.category_type === "INCOME");
      if (incomeCat) {
        setSimpleCategoryId(incomeCat.category_id);
        setSimpleLabel(incomeCat.effective_label || "ESSENTIAL");
        setItems((prev) => prev.map((itm) => ({
          ...itm,
          category_id: incomeCat.category_id,
          label: incomeCat.effective_label || "ESSENTIAL"
        })));
      }
    } else if (newKind === "EXPENSE") {
      const expCat = categories.find((c) => c.category_type === "EXPENSE");
      if (expCat) {
        setSimpleCategoryId(expCat.category_id);
        setSimpleLabel(expCat.effective_label || "DISCRETIONARY");
        setItems((prev) => prev.map((itm) => ({
          ...itm,
          category_id: expCat.category_id,
          label: expCat.effective_label || "DISCRETIONARY"
        })));
      }
    }
  };

  // Currencies
  const selectedSimpleAccount = useMemo(() => accounts.find((a) => a.account_id === simpleAccountId), [accounts, simpleAccountId]);
  const simpleCurrency = selectedSimpleAccount?.currency || "EUR";
  const simpleCurrencySymbol = getCurrencySymbol(simpleCurrency);

  const fromAccount = useMemo(() => accounts.find((a) => a.account_id === fromAccountId), [accounts, fromAccountId]);
  const toAccount = useMemo(() => accounts.find((a) => a.account_id === toAccountId), [accounts, toAccountId]);
  const fromCurrencySymbol = getCurrencySymbol(fromAccount?.currency || "EUR");
  const toCurrencySymbol = getCurrencySymbol(toAccount?.currency || "EUR");

  // Effective Exchange Rate calculation for Transfer mode
  const effectiveExchangeRate = useMemo(() => {
    const fromVal = parseFloat(fromAmount) || 0;
    const toVal = parseFloat(toAmount) || 0;
    if (fromVal > 0 && toVal > 0) {
      const rate = fromVal / toVal;
      return `1 ${toAccount?.currency || "EUR"} ≈ ${rate.toFixed(4)} ${fromAccount?.currency || "INR"}`;
    }
    return null;
  }, [fromAmount, toAmount, fromAccount, toAccount]);

  // Converted Fee in destination currency
  const convertedFeeInToCurrency = useMemo(() => {
    const fee = parseFloat(feeAmount) || 0;
    if (fee <= 0) return 0;
    const fromVal = parseFloat(fromAmount) || 0;
    const toVal = parseFloat(toAmount) || 0;
    if (fromVal > 0 && toVal > 0 && fromAccount?.currency !== toAccount?.currency) {
      return (fee / fromVal) * toVal;
    }
    return fee;
  }, [feeAmount, fromAmount, toAmount, fromAccount, toAccount]);

  // Sync category default label when simpleCategoryId changes
  useEffect(() => {
    if (simpleCategoryId && !simpleLabel) {
      const found = categories.find((c) => c.category_id === simpleCategoryId);
      if (found?.effective_label) {
        setSimpleLabel(found.effective_label);
      }
    }
  }, [simpleCategoryId, categories, simpleLabel]);

  // Payment total calculation
  const totalPaymentCalculated = useMemo(() => {
    if (transactionKind === "TRANSFER") {
      return parseFloat(toAmount) || 0;
    }
    if (!isSplitPayments) {
      return parseFloat(simpleAmount) || 0;
    }
    return payments.reduce((sum, p) => sum + (parseFloat(p.amount) || 0), 0);
  }, [transactionKind, toAmount, isSplitPayments, simpleAmount, payments]);

  // Itemized total calculation
  const totalItemsCalculated = useMemo(() => {
    if (transactionKind === "TRANSFER") {
      return totalPaymentCalculated;
    }
    if (!isSplitItems) {
      return totalPaymentCalculated;
    }
    return items.reduce((sum, i) => sum + (parseFloat(i.amount) || 0), 0);
  }, [transactionKind, isSplitItems, totalPaymentCalculated, items]);

  const itemBalanceDiff = totalPaymentCalculated - totalItemsCalculated;

  if (!isOpen) return null;

  const handleSubmit = async (e?: React.FormEvent, isAddNew: boolean = false) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError("");
    setSuccessBanner("");

    // 1. Validation for Transfer Mode
    if (transactionKind === "TRANSFER") {
      if (!fromAccountId || !toAccountId) {
        setError("Please select both source ('From') and destination ('To') accounts.");
        setLoading(false);
        return;
      }
      if (fromAccountId === toAccountId) {
        setError("Source and destination accounts must be different.");
        setLoading(false);
        return;
      }
      const parsedFrom = parseFloat(fromAmount) || 0;
      const parsedTo = parseFloat(toAmount) || 0;
      if (parsedFrom <= 0 || parsedTo <= 0) {
        setError("Please enter valid positive amounts for both From and To accounts.");
        setLoading(false);
        return;
      }

      const transferTitle = title.trim() || `Transfer: ${fromAccount?.account_name} ➔ ${toAccount?.account_name}`;
      const transferCat = categories.find((c) => c.category_type === "TRANSFER") || categories[0];
      const feeCat = categories.find((c) => c.name.includes("Fees") || c.name.includes("Financial")) || transferCat;

      const transferPayments = [
        { account_id: Number(fromAccountId), amount: -parsedFrom },
        { account_id: Number(toAccountId), amount: parsedTo },
      ];

      const transferItems = [
        {
          category_id: transferCat.category_id,
          amount: parsedTo,
          label: null,
          description: transferTitle,
        }
      ];

      const parsedFee = parseFloat(feeAmount) || 0;
      if (hasTransferFee && parsedFee > 0) {
        const finalFeeAmount = Math.round(convertedFeeInToCurrency * 100) / 100;
        transferItems.push({
          category_id: feeCat.category_id,
          amount: finalFeeAmount,
          label: "ESSENTIAL",
          description: `Transfer / FX Fee (${fromCurrencySymbol}${parsedFee.toFixed(2)})`,
        });
      }

      try {
        const payload = {
          transaction_date: transactionDate,
          title: transferTitle,
          total_amount: parsedTo,
          currency: toAccount?.currency || "EUR",
          transaction_kind: "TRANSFER",
          notes: notes || null,
          payments: transferPayments,
          items: transferItems,
        };

        if (initialData) {
          await apiFetch(`/cashflow/${initialData.cashflow_id}`, { method: "PUT", body: JSON.stringify(payload) });
          onSuccess();
          onClose();
        } else {
          await apiFetch("/cashflow", { method: "POST", body: JSON.stringify(payload) });
          onSuccess();
          if (isAddNew) {
            setSuccessBanner("Transfer recorded successfully! Ready for next entry.");
            setFromAmount("");
            setToAmount("");
            setFeeAmount("");
            setTitle("");
          } else {
            onClose();
          }
        }
      } catch (err: any) {
        setError(err.message || "Failed to record transfer");
      } finally {
        setLoading(false);
      }
      return;
    }

    // 2. Standard Expense / Income Validation
    if (!title.trim()) {
      setError("Please enter a Merchant / Entity name.");
      setLoading(false);
      return;
    }

    if (totalPaymentCalculated <= 0) {
      setError("Please enter an amount greater than 0.");
      setLoading(false);
      return;
    }

    // Validate Item Description
    if (!isSplitItems) {
      if (!simpleDescription.trim()) {
        setError("Please enter an Item Description (e.g. Ergonomic Chair, Monthly Salary).");
        setLoading(false);
        return;
      }
    } else {
      const missingDesc = items.some((itm) => !itm.description || !itm.description.trim());
      if (missingDesc) {
        setError("Please enter a description for all category split line items.");
        setLoading(false);
        return;
      }
    }

    const finalPayments = isSplitPayments
      ? payments.map((p) => ({ account_id: Number(p.account_id), amount: parseFloat(p.amount) || 0 }))
      : [{ account_id: Number(simpleAccountId), amount: totalPaymentCalculated }];

    const finalItems = isSplitItems
      ? items.map((i) => ({
          category_id: Number(i.category_id),
          amount: parseFloat(i.amount) || 0,
          label: i.label ? i.label.toUpperCase() : null,
          description: i.description.trim(),
        }))
      : [{
          category_id: Number(simpleCategoryId),
          amount: totalPaymentCalculated,
          label: simpleLabel ? simpleLabel.toUpperCase() : null,
          description: simpleDescription.trim(),
        }];

    if (isSplitItems && Math.abs(itemBalanceDiff) > 0.01) {
      setError(`Category items sum (${formatCurrency(totalItemsCalculated, simpleCurrency)}) must equal Payment sum (${formatCurrency(totalPaymentCalculated, simpleCurrency)}).`);
      setLoading(false);
      return;
    }

    try {
      const payload = {
        transaction_date: transactionDate,
        title: title.trim(),
        total_amount: totalPaymentCalculated,
        currency: simpleCurrency,
        transaction_kind: transactionKind,
        notes: notes || null,
        payments: finalPayments,
        items: finalItems,
      };

      if (initialData) {
        await apiFetch(`/cashflow/${initialData.cashflow_id}`, { method: "PUT", body: JSON.stringify(payload) });
        onSuccess();
        onClose();
      } else {
        await apiFetch("/cashflow", { method: "POST", body: JSON.stringify(payload) });
        onSuccess();
        if (isAddNew) {
          setSuccessBanner("Transaction recorded! Ready for next entry.");
          setTitle("");
          setSimpleAmount("");
          setSimpleDescription("");
          setNotes("");
          setPayments([{ account_id: simpleAccountId || accounts[0]?.account_id || "", amount: "" }]);
          setItems([{ category_id: simpleCategoryId || categories[0]?.category_id || "", amount: "", label: "", description: "" }]);
        } else {
          onClose();
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to save transaction");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-xl shadow-xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2.5 mb-3">
          <div className="p-2 bg-[#0F172A] text-white rounded-xl">
            {initialData ? <Edit className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Transaction" : "Record Spend, Income or Transfer"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Track multi-currency expenses, salary deposits, or internal FX conversions
            </p>
          </div>
        </div>

        {/* Transaction Kind Selector */}
        <div className="grid grid-cols-3 gap-1.5 p-1 bg-[#F1F5F9] rounded-xl mb-4 text-xs font-bold">
          <button
            type="button"
            onClick={() => handleSwitchKind("EXPENSE")}
            className={`py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              transactionKind === "EXPENSE"
                ? "bg-white text-rose-600 shadow-xs"
                : "text-slate-600 hover:text-[#0F172A]"
            }`}
          >
            <TrendingDown className="w-3.5 h-3.5" />
            <span>Expense / Spend</span>
          </button>

          <button
            type="button"
            onClick={() => handleSwitchKind("INCOME")}
            className={`py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              transactionKind === "INCOME"
                ? "bg-white text-emerald-600 shadow-xs"
                : "text-slate-600 hover:text-[#0F172A]"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Income</span>
          </button>

          <button
            type="button"
            onClick={() => handleSwitchKind("TRANSFER")}
            className={`py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              transactionKind === "TRANSFER"
                ? "bg-white text-blue-600 shadow-xs"
                : "text-slate-600 hover:text-[#0F172A]"
            }`}
          >
            <ArrowLeftRight className="w-3.5 h-3.5" />
            <span>Transfer / FX</span>
          </button>
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
          {/* ======================================================== */}
          {/* 1. DEDICATED TRANSFER / FX CONVERSION MODE               */}
          {/* ======================================================== */}
          {transactionKind === "TRANSFER" ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block font-semibold text-slate-600 mb-1">Transfer Description</label>
                  <input
                    type="text"
                    placeholder={`e.g. Convert INR to EUR for trip`}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
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
              </div>

              {/* Transfer Flow Box: From ➔ To */}
              <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-3">
                {/* Source Account (From) */}
                <div>
                  <label className="block font-bold text-slate-700 mb-1 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span>From Account (Money Outflow)</span>
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div className="sm:col-span-2">
                      <select
                        value={fromAccountId}
                        onChange={(e) => setFromAccountId(Number(e.target.value))}
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

                    <div className="relative flex items-center">
                      <span className="absolute left-3 font-bold text-slate-400 pointer-events-none text-xs">
                        {fromCurrencySymbol}
                      </span>
                      <input
                        type="number"
                        step="any"
                        placeholder="0.00"
                        value={fromAmount}
                        onChange={(e) => setFromAmount(e.target.value)}
                        className="w-full bg-white text-slate-900 font-bold tabular-nums rounded-lg pl-7 pr-3 py-2 border border-slate-200 focus:outline-none text-xs"
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Arrow Divider */}
                <div className="flex items-center justify-center -my-1">
                  <div className="p-1 bg-white rounded-full border border-slate-200 text-slate-400 shadow-2xs">
                    <ArrowLeftRight className="w-3.5 h-3.5 text-blue-600" />
                  </div>
                </div>

                {/* Destination Account (To) */}
                <div>
                  <label className="block font-bold text-slate-700 mb-1 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span>To Account (Money Inflow)</span>
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div className="sm:col-span-2">
                      <select
                        value={toAccountId}
                        onChange={(e) => setToAccountId(Number(e.target.value))}
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

                    <div className="relative flex items-center">
                      <span className="absolute left-3 font-bold text-slate-400 pointer-events-none text-xs">
                        {toCurrencySymbol}
                      </span>
                      <input
                        type="number"
                        step="any"
                        placeholder="0.00"
                        value={toAmount}
                        onChange={(e) => setToAmount(e.target.value)}
                        className="w-full bg-white text-slate-900 font-bold tabular-nums rounded-lg pl-7 pr-3 py-2 border border-slate-200 focus:outline-none text-xs"
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Effective Exchange Rate Display */}
                {effectiveExchangeRate && (
                  <div className="p-2 bg-blue-50/70 border border-blue-200/60 rounded-lg text-[11px] font-bold text-blue-700 flex items-center justify-between">
                    <span>Effective Exchange Rate:</span>
                    <span className="bg-white px-2 py-0.5 rounded border border-blue-200 font-bold">
                      {effectiveExchangeRate}
                    </span>
                  </div>
                )}
              </div>

              {/* Optional Transfer Fee */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasTransferFee}
                    onChange={(e) => setHasTransferFee(e.target.checked)}
                    className="w-3.5 h-3.5 accent-blue-600 rounded cursor-pointer"
                  />
                  <span>Add Transfer Fee / Bank Charge (Optional)</span>
                </label>

                {hasTransferFee && (
                  <div className="pt-1 flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-500 font-semibold">Fee Amount ({fromCurrencySymbol}):</span>
                      <input
                        type="number"
                        step="any"
                        placeholder="e.g. 177.00"
                        value={feeAmount}
                        onChange={(e) => setFeeAmount(e.target.value)}
                        className="w-28 bg-white text-slate-900 font-bold tabular-nums rounded-lg px-3 py-1.5 border border-slate-200 text-xs"
                      />
                    </div>

                    {convertedFeeInToCurrency > 0 && fromAccount?.currency !== toAccount?.currency && (
                      <span className="text-[11px] font-bold text-slate-600 bg-white px-2 py-1 rounded border border-slate-200 shadow-2xs">
                        ≈ {formatCurrency(convertedFeeInToCurrency, toAccount?.currency || "EUR")}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ======================================================== */
            /* 2. STANDARD EXPENSE & INCOME MODE                        */
            /* ======================================================== */
            <div className="space-y-4">
              {/* Top Row: Merchant / Entity & Date */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block font-semibold text-slate-600 mb-1">
                    {transactionKind === "INCOME" ? "Source / Employer / Client" : "Merchant / Store"} <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder={transactionKind === "INCOME" ? "e.g. Google LLC, Client XYZ, Stock Broker" : "e.g. Amazon, Uber, Walmart, Restaurant"}
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
              </div>

              {/* Payment Method / Funding Source */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5">
                    <ArrowDownLeft className="w-3.5 h-3.5 text-blue-600" />
                    {transactionKind === "INCOME" ? "Deposit Account & Amount" : "Payment Method & Amount"}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setIsSplitPayments(!isSplitPayments);
                      if (!isSplitPayments && payments.length === 1 && simpleAmount) {
                        setPayments([{ account_id: simpleAccountId || accounts[0]?.account_id || "", amount: simpleAmount }]);
                      }
                    }}
                    className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
                  >
                    <Split className="w-3 h-3" />
                    {isSplitPayments ? "Single Account" : "Split Multiple Accounts"}
                  </button>
                </div>

                {!isSplitPayments ? (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    <div className="sm:col-span-2">
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

                    <div className="relative flex items-center">
                      <span className="absolute left-3 font-bold text-slate-400 pointer-events-none text-xs">
                        {simpleCurrencySymbol}
                      </span>
                      <input
                        type="number"
                        step="any"
                        placeholder="0.00"
                        value={simpleAmount}
                        onChange={(e) => setSimpleAmount(e.target.value)}
                        className="w-full bg-white text-slate-900 font-bold tabular-nums rounded-lg pl-7 pr-3 py-2 border border-slate-200 focus:outline-none text-xs"
                        required
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {payments.map((p, idx) => {
                      const acc = accounts.find((a) => a.account_id === p.account_id);
                      const currSym = getCurrencySymbol(acc?.currency || "EUR");
                      return (
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
                                {acc.account_name} ({acc.currency})
                              </option>
                            ))}
                          </select>

                          <div className="relative flex items-center w-32">
                            <span className="absolute left-2.5 font-bold text-slate-400 pointer-events-none text-xs">
                              {currSym}
                            </span>
                            <input
                              type="number"
                              step="any"
                              placeholder="Amount"
                              value={p.amount}
                              onChange={(e) => {
                                const val = e.target.value;
                                setPayments((prev) => prev.map((item, i) => i === idx ? { ...item, amount: val } : item));
                              }}
                              className="w-full bg-white text-slate-900 font-bold tabular-nums rounded-lg pl-6 pr-2 py-1.5 border border-slate-200 focus:outline-none text-xs"
                              required
                            />
                          </div>

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
                      );
                    })}

                    <div className="flex items-center justify-between pt-1">
                      <button
                        type="button"
                        onClick={() => setPayments((prev) => [...prev, { account_id: accounts[0]?.account_id || "", amount: "" }])}
                        className="text-[11px] font-bold text-slate-700 hover:text-black flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3 h-3" /> Add Account Split
                      </button>

                      <div className="text-[11px] font-bold text-slate-700">
                        Total: {formatCurrency(totalPaymentCalculated, simpleCurrency)}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Category & Classification */}
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
                      if (!isSplitItems && items.length === 1 && totalPaymentCalculated) {
                        setItems([{ category_id: simpleCategoryId || categories[0]?.category_id || "", amount: totalPaymentCalculated.toString(), label: simpleLabel, description: simpleDescription }]);
                      }
                    }}
                    className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
                  >
                    <Split className="w-3 h-3" />
                    {isSplitItems ? "Single Category" : "Split Multiple Categories"}
                  </button>
                </div>

                {!isSplitItems ? (
                  <div className="space-y-2.5">
                    {/* Category Dropdown */}
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                        Category <span className="text-rose-500">*</span>
                      </label>
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
                        {categories
                          .filter((c) => transactionKind === "INCOME" ? c.category_type === "INCOME" : c.category_type !== "INCOME")
                          .map((c) => (
                            <option key={c.category_id} value={c.category_id}>
                              {c.full_path || c.name}
                            </option>
                          ))}
                      </select>
                    </div>

                    {/* Dedicated Required Item Description Field */}
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                        Item Description <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        placeholder={transactionKind === "INCOME" ? "e.g. August Base Salary, Tech Consulting, Dividend" : "e.g. Ergonomic Office Chair, Grocery supplies, Dinner with friends"}
                        value={simpleDescription}
                        onChange={(e) => setSimpleDescription(e.target.value)}
                        className="w-full bg-white text-slate-900 font-medium rounded-lg px-3 py-2 border border-slate-200 focus:outline-none text-xs"
                        required
                      />
                    </div>

                    {/* Classification Label Selector */}
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                        Classification (Default: <span className="font-bold">{categories.find(c => c.category_id === simpleCategoryId)?.effective_label || "None"}</span>)
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
                            {categories
                              .filter((c) => transactionKind === "INCOME" ? c.category_type === "INCOME" : c.category_type !== "INCOME")
                              .map((c) => (
                                <option key={c.category_id} value={c.category_id}>
                                  {c.full_path || c.name}
                                </option>
                              ))}
                          </select>

                          <div className="relative flex items-center w-28">
                            <span className="absolute left-2 font-bold text-slate-400 pointer-events-none text-xs">
                              {simpleCurrencySymbol}
                            </span>
                            <input
                              type="number"
                              step="any"
                              placeholder="Amount"
                              value={itm.amount}
                              onChange={(e) => {
                                const val = e.target.value;
                                setItems((prev) => prev.map((item, i) => i === idx ? { ...item, amount: val } : item));
                              }}
                              className="w-full bg-slate-50 text-slate-900 font-bold tabular-nums rounded-lg pl-5 pr-2 py-1.5 border border-slate-200 text-xs"
                              required
                            />
                          </div>

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
                            placeholder="Item description (Required, e.g. Speakers)"
                            value={itm.description}
                            onChange={(e) => {
                              const val = e.target.value;
                              setItems((prev) => prev.map((item, i) => i === idx ? { ...item, description: val } : item));
                            }}
                            className="bg-slate-50 text-slate-800 font-medium rounded-lg px-2.5 py-1 border border-slate-200 text-[11px]"
                            required
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
                        onClick={() => {
                          const defaultCat = categories.find((c) => transactionKind === "INCOME" ? c.category_type === "INCOME" : c.category_type !== "INCOME") || categories[0];
                          setItems((prev) => [...prev, { category_id: defaultCat?.category_id || "", amount: "", label: "", description: "" }]);
                        }}
                        className="text-[11px] font-bold text-slate-700 hover:text-black flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3 h-3" /> Add Category Split Line
                      </button>

                      <div className="text-[11px] font-bold">
                        {Math.abs(itemBalanceDiff) < 0.01 ? (
                          <span className="text-emerald-600 flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Balanced: {formatCurrency(totalItemsCalculated, simpleCurrency)}
                          </span>
                        ) : (
                          <span className="text-rose-600">
                            Remaining: {formatCurrency(itemBalanceDiff, simpleCurrency)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

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
