"use client";

import React, { useState, useEffect } from "react";
import { 
  X, ChevronUp, ChevronDown, Eye, EyeOff, 
  RotateCcw, Check, Landmark, Building2, SlidersHorizontal 
} from "lucide-react";

export interface AccountItem {
  account_id: number;
  account_name: string;
  account_type: string;
  broker_name?: string | null;
  currency: string;
  current_balance: number;
}

export interface AccountCustomizationModalProps {
  isOpen: boolean;
  accounts: AccountItem[];
  initialOrder: number[];
  initialHidden: number[];
  onClose: () => void;
  onSave: (order: number[], hidden: number[]) => void;
}

export function AccountCustomizationModal({
  isOpen,
  accounts,
  initialOrder,
  initialHidden,
  onClose,
  onSave,
}: AccountCustomizationModalProps) {
  const [orderedAccounts, setOrderedAccounts] = useState<AccountItem[]>([]);
  const [hiddenSet, setHiddenSet] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (isOpen) {
      // Build order mapping based on initialOrder
      const orderMap = new Map<number, number>();
      initialOrder.forEach((id, idx) => orderMap.set(id, idx));

      const sorted = [...accounts].sort((a, b) => {
        const orderA = orderMap.has(a.account_id) ? orderMap.get(a.account_id)! : 9999;
        const orderB = orderMap.has(b.account_id) ? orderMap.get(b.account_id)! : 9999;
        return orderA - orderB;
      });

      setOrderedAccounts(sorted);
      setHiddenSet(new Set(initialHidden));
    }
  }, [isOpen, accounts, initialOrder, initialHidden]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const newItems = [...orderedAccounts];
    const temp = newItems[index];
    newItems[index] = newItems[index - 1];
    newItems[index - 1] = temp;
    setOrderedAccounts(newItems);
  };

  const handleMoveDown = (index: number) => {
    if (index >= orderedAccounts.length - 1) return;
    const newItems = [...orderedAccounts];
    const temp = newItems[index];
    newItems[index] = newItems[index + 1];
    newItems[index + 1] = temp;
    setOrderedAccounts(newItems);
  };

  const handleToggleVisibility = (accountId: number) => {
    const nextHidden = new Set(hiddenSet);
    if (nextHidden.has(accountId)) {
      nextHidden.delete(accountId);
    } else {
      nextHidden.add(accountId);
    }
    setHiddenSet(nextHidden);
  };

  const handleReset = () => {
    setOrderedAccounts([...accounts]);
    setHiddenSet(new Set());
  };

  const handleSave = () => {
    const newOrder = orderedAccounts.map((a) => a.account_id);
    onSave(newOrder, Array.from(hiddenSet));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white dark:bg-[#121824] rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-xl">
              <SlidersHorizontal className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                Customize Accounts Layout
              </h3>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Reorder accounts or toggle visibility on the dashboard
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Account List */}
        <div className="p-4 overflow-y-auto flex-1 space-y-2">
          {orderedAccounts.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400">
              No accounts available.
            </div>
          ) : (
            <ul className="space-y-1.5">
              {orderedAccounts.map((acc, index) => {
                const isHidden = hiddenSet.has(acc.account_id);
                const isBank = acc.account_type === "bank";

                return (
                  <li
                    key={acc.account_id}
                    className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${
                      isHidden
                        ? "bg-slate-50/50 dark:bg-slate-900/30 border-slate-200/60 dark:border-slate-800/40 opacity-60"
                        : "bg-white dark:bg-[#182030] border-slate-200 dark:border-slate-800 shadow-2xs"
                    }`}
                  >
                    {/* Left: Icon & Info */}
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div
                        className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${
                          isBank
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-800/50 dark:text-emerald-300"
                            : "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:border-blue-800/50 dark:text-blue-300"
                        }`}
                      >
                        {isBank ? <Landmark className="w-3.5 h-3.5" /> : <Building2 className="w-3.5 h-3.5" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className={`font-bold text-xs truncate ${isHidden ? "line-through text-slate-400" : "text-slate-800 dark:text-slate-100"}`}>
                          {acc.account_name}
                        </div>
                        <div className="text-[10px] text-slate-400 dark:text-slate-500 font-medium flex items-center gap-1.5">
                          <span>{acc.broker_name || (isBank ? "Bank" : "Broker")}</span>
                          <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-[9px] font-bold px-1 rounded">
                            {acc.currency}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      {/* Visibility Toggle */}
                      <button
                        type="button"
                        onClick={() => handleToggleVisibility(acc.account_id)}
                        className={`p-1.5 rounded-lg border transition-colors ${
                          isHidden
                            ? "text-slate-400 border-slate-200 hover:text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                            : "text-blue-600 border-blue-200 bg-blue-50/50 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-400"
                        }`}
                        title={isHidden ? "Show account" : "Hide account"}
                        aria-label="Toggle visibility"
                      >
                        {isHidden ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>

                      {/* Move Up */}
                      <button
                        type="button"
                        onClick={() => handleMoveUp(index)}
                        disabled={index === 0}
                        className="p-1.5 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Move Up"
                        aria-label="Move up"
                      >
                        <ChevronUp className="w-3.5 h-3.5" />
                      </button>

                      {/* Move Down */}
                      <button
                        type="button"
                        onClick={() => handleMoveDown(index)}
                        disabled={index === orderedAccounts.length - 1}
                        className="p-1.5 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Move Down"
                        aria-label="Move down"
                      >
                        <ChevronDown className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 shrink-0">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset to Default</span>
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold text-white bg-[#0F172A] hover:bg-slate-800 dark:bg-blue-600 dark:hover:bg-blue-700 rounded-lg shadow-xs transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Save Changes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
