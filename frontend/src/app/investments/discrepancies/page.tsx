"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatQty } from "@/lib/format";
import { 
  AlertCircle, CheckCircle2, RefreshCw, Landmark, 
  ArrowRight, Check, Zap, Building2, HelpCircle
} from "lucide-react";

interface CandidateMatch {
  match_id: number;
  match_type: string;
  account_id: number;
  account_name: string;
  date: string;
  amount: number;
  title: string;
}

interface DiscrepancyItem {
  transaction_id: number;
  account_id: number;
  account_name: string;
  asset_id: number;
  asset_symbol: string;
  asset_name: string;
  currency: string;
  transaction_date: string;
  quantity: number;
  price_per_unit: number;
  total_amount: number;
  taxes: number;
  net_amount: number;
  source: string;
  suggested_funding_account_id?: number | null;
  suggested_funding_account_name?: string | null;
  candidate_matches?: CandidateMatch[];
  notes?: string | null;
}

interface DiscrepancySummary {
  total_count: number;
  total_unlinked_amount: number;
  auto_linkable_count: number;
  unlinked_items: DiscrepancyItem[];
}

interface AccountOption {
  account_id: number;
  account_name: string;
  account_type: string;
  currency: string;
}

export default function DiscrepanciesPage() {
  const [data, setData] = useState<DiscrepancySummary | null>(null);
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectedBankPerTx, setSelectedBankPerTx] = useState<Record<number, number>>({});
  const [selectedDatePerTx, setSelectedDatePerTx] = useState<Record<number, string>>({});
  const [batchBankId, setBatchBankId] = useState<number | "">("");
  const [setDefaultDemat, setSetDefaultDemat] = useState<Record<number, boolean>>({});

  useEffect(() => {
    document.title = "Discrepancies · greenline";
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [discRes, accsRes] = await Promise.all([
        apiFetch<DiscrepancySummary>("/discrepancies"),
        apiFetch<AccountOption[]>("/accounts"),
      ]);

      setData(discRes);
      const bankAccounts = (accsRes || []).filter((a) => a.account_type === "bank");
      setAccounts(bankAccounts);

      // Pre-fill initial bank and date selections
      const initialBankMap: Record<number, number> = {};
      const initialDateMap: Record<number, string> = {};

      discRes.unlinked_items.forEach((item) => {
        initialDateMap[item.transaction_id] = item.transaction_date;

        if (item.candidate_matches && item.candidate_matches.length > 0) {
          initialBankMap[item.transaction_id] = item.candidate_matches[0].account_id;
          initialDateMap[item.transaction_id] = item.candidate_matches[0].date;
        } else if (item.suggested_funding_account_id) {
          initialBankMap[item.transaction_id] = item.suggested_funding_account_id;
        } else if (bankAccounts.length > 0) {
          initialBankMap[item.transaction_id] = bankAccounts[0].account_id;
        }
      });

      setSelectedBankPerTx(initialBankMap);
      setSelectedDatePerTx(initialDateMap);

      if (bankAccounts.length > 0) {
        setBatchBankId(bankAccounts[0].account_id);
      }
    } catch (err) {
      console.error("Failed to load discrepancies:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncDividends = async () => {
    try {
      setSyncing(true);
      await apiFetch("/discrepancies/sync-dividends", { method: "POST" });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to sync dividends");
    } finally {
      setSyncing(false);
    }
  };

  const handleResolveSingle = async (txId: number, dematId: number) => {
    const bankId = selectedBankPerTx[txId];
    if (!bankId) {
      alert("Please select a destination bank account.");
      return;
    }

    try {
      setResolving(true);
      const shouldSetDefault = setDefaultDemat[txId];
      const creditDate = selectedDatePerTx[txId];

      await apiFetch("/discrepancies/resolve", {
        method: "POST",
        body: JSON.stringify({
          resolutions: [
            {
              transaction_id: txId,
              funding_account_id: bankId,
              transaction_date: creditDate || undefined,
            }
          ],
          set_default_for_demat: shouldSetDefault
            ? { demat_account_id: dematId, default_dividend_account_id: bankId }
            : null,
        }),
      });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to resolve dividend");
    } finally {
      setResolving(false);
    }
  };

  const handleResolveBatch = async () => {
    if (selectedIds.size === 0) return;
    if (!batchBankId) {
      alert("Please choose a bank account for batch linking.");
      return;
    }

    try {
      setResolving(true);
      const resolutions = Array.from(selectedIds).map((txId) => ({
        transaction_id: txId,
        funding_account_id: Number(batchBankId),
        transaction_date: selectedDatePerTx[txId] || undefined,
      }));

      await apiFetch("/discrepancies/resolve", {
        method: "POST",
        body: JSON.stringify({ resolutions }),
      });
      setSelectedIds(new Set());
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to batch resolve dividends");
    } finally {
      setResolving(false);
    }
  };

  const toggleSelectAll = () => {
    if (!data) return;
    if (selectedIds.size === data.unlinked_items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.unlinked_items.map((i) => i.transaction_id)));
    }
  };

  const toggleSelectItem = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9] dark:border-[#1E293B]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0F172A] dark:text-white tracking-tight">
              Investments Discrepancies
            </h1>
            {data && data.total_count > 0 && (
              <span className="px-2 py-0.5 text-xs font-bold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 rounded-full">
                {data.total_count} Unlinked
              </span>
            )}
          </div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
            Match automated and unlinked dividend distributions to your receiving bank accounts
          </p>
        </div>

        {/* Global Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncDividends}
            disabled={syncing}
            className="btn-pill-black text-xs cursor-pointer flex items-center gap-1.5"
            title="Fetch latest dividend corporate distributions from Yahoo Finance"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} />
            <span>{syncing ? "Syncing..." : "Sync Dividends"}</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {data && data.total_count > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="getquin-card p-4 space-y-1">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Unlinked Distributions
            </div>
            <div className="text-2xl font-black text-amber-600 dark:text-amber-400">
              {data.total_count}
            </div>
            <p className="text-[11px] text-slate-500">
              Awaiting cash deposit routing
            </p>
          </div>

          <div className="getquin-card p-4 space-y-1">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Total Unlinked Value
            </div>
            <div className="text-2xl font-black text-[#0F172A] dark:text-white">
              {formatCurrency(data.total_unlinked_amount, "USD")}
            </div>
            <p className="text-[11px] text-slate-500">
              Net payout after withheld taxes
            </p>
          </div>
        </div>
      )}

      {/* Discrepancies Table Container */}
      <div className="getquin-card p-5 space-y-4">
        {/* Table Header & Batch Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#F1F5F9] dark:border-[#1E293B]">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-lg">
              <Landmark className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Unlinked Dividend Payouts
              </h2>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Securities held on record date that distributed cash dividends
              </p>
            </div>
          </div>

          {/* Batch Selector Bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/70 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-xs">
              <span className="font-bold text-slate-700 dark:text-slate-300">
                {selectedIds.size} selected
              </span>
              <select
                value={batchBankId}
                onChange={(e) => setBatchBankId(e.target.value ? Number(e.target.value) : "")}
                className="bg-white dark:bg-[#151D2B] text-slate-900 dark:text-slate-100 font-semibold rounded-lg px-2.5 py-1 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none"
              >
                {accounts.map((b) => (
                  <option key={b.account_id} value={b.account_id}>
                    {b.account_name} ({b.currency})
                  </option>
                ))}
              </select>
              <button
                onClick={handleResolveBatch}
                disabled={resolving}
                className="btn-pill-black text-[11px] px-3 py-1 cursor-pointer"
              >
                Link All Selected
              </button>
            </div>
          )}
        </div>

        {/* Table / Empty State */}
        {loading ? (
          <div className="py-16 text-center text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-400" />
            <p className="text-xs font-semibold">Loading discrepancies...</p>
          </div>
        ) : data && data.unlinked_items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#F1F5F9] dark:border-[#1E293B] text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === data.unlinked_items.length && data.unlinked_items.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-slate-300 text-black focus:ring-black cursor-pointer"
                    />
                  </th>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Security</th>
                  <th className="py-2.5 px-3">Demat Account</th>
                  <th className="py-2.5 px-3 text-right">Shares & Rate</th>
                  <th className="py-2.5 px-3 text-right">Gross Amount</th>
                  <th className="py-2.5 px-3 text-right">Taxes</th>
                  <th className="py-2.5 px-3 text-right">Net Payout</th>
                  <th className="py-2.5 px-3">Deposit To Bank</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B]">
                {data.unlinked_items.map((item) => {
                  const isSelected = selectedIds.has(item.transaction_id);
                  const selectedBank = selectedBankPerTx[item.transaction_id];
                  const hasSuggested = Boolean(item.suggested_funding_account_id);

                  return (
                    <tr 
                      key={item.transaction_id}
                      className={`hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors ${
                        isSelected ? "bg-slate-50/80 dark:bg-slate-800/50" : ""
                      }`}
                    >
                      <td className="py-3 px-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectItem(item.transaction_id)}
                          className="rounded border-slate-300 text-black focus:ring-black cursor-pointer"
                        />
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-600 dark:text-slate-400 whitespace-nowrap">
                        <div>{item.transaction_date}</div>
                        <span className="text-[10px] text-slate-400">Ex-Date</span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-bold text-[#0F172A] dark:text-white flex items-center gap-1.5">
                          <span>{item.asset_symbol}</span>
                          {item.source === "yfinance_auto" && (
                            <span className="px-1.5 py-0.2 text-[9px] font-bold bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 rounded">
                              Auto
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate max-w-[160px]">
                          {item.asset_name}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">
                          {item.account_name}
                        </div>
                        {item.suggested_funding_account_name && (
                          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-0.5">
                            <Check className="w-3 h-3" />
                            <span>Default: {item.suggested_funding_account_name}</span>
                          </div>
                        )}
                        {item.candidate_matches && item.candidate_matches.length > 0 && (
                          <div className="mt-1 space-y-1">
                            {item.candidate_matches.map((m, mIdx) => (
                              <button
                                key={mIdx}
                                type="button"
                                onClick={() => {
                                  setSelectedBankPerTx((prev) => ({ ...prev, [item.transaction_id]: m.account_id }));
                                  setSelectedDatePerTx((prev) => ({ ...prev, [item.transaction_id]: m.date }));
                                }}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800 transition-colors cursor-pointer text-left"
                                title={`Use matched bank ${m.account_name} on ${m.date}`}
                              >
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                                <span>Match: {m.account_name} · {m.date} ({formatCurrency(m.amount, item.currency)})</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-slate-600 dark:text-slate-400 whitespace-nowrap">
                        {formatQty(item.quantity)} @ {formatCurrency(item.price_per_unit, item.currency)}
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-slate-800 dark:text-slate-200">
                        {formatCurrency(item.total_amount, item.currency)}
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-rose-500">
                        {item.taxes > 0 ? `-${formatCurrency(item.taxes, item.currency)}` : "—"}
                      </td>
                      <td className="py-3 px-3 text-right font-black text-emerald-600 dark:text-emerald-400">
                        +{formatCurrency(item.net_amount, item.currency)}
                      </td>
                      <td className="py-3 px-3 min-w-[220px]">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-bold text-slate-400 uppercase">Credit Date:</span>
                            <input
                              type="date"
                              value={selectedDatePerTx[item.transaction_id] || item.transaction_date}
                              onChange={(e) => {
                                const val = e.target.value;
                                setSelectedDatePerTx((prev) => ({ ...prev, [item.transaction_id]: val }));
                              }}
                              className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-medium rounded-md px-2 py-0.5 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none"
                            />
                          </div>

                          <select
                            value={selectedBank || ""}
                            onChange={(e) => {
                              const val = Number(e.target.value);
                              setSelectedBankPerTx((prev) => ({ ...prev, [item.transaction_id]: val }));
                            }}
                            className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none"
                          >
                            {accounts.map((b) => (
                              <option key={b.account_id} value={b.account_id}>
                                {b.account_name} ({b.currency})
                              </option>
                            ))}
                          </select>

                          {!hasSuggested && (
                            <label className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={Boolean(setDefaultDemat[item.transaction_id])}
                                onChange={(e) =>
                                  setSetDefaultDemat((prev) => ({
                                    ...prev,
                                    [item.transaction_id]: e.target.checked,
                                  }))
                                }
                                className="rounded text-xs border-slate-300"
                              />
                              <span>Set as default for {item.account_name}</span>
                            </label>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => handleResolveSingle(item.transaction_id, item.account_id)}
                          disabled={resolving}
                          className="btn-pill-black text-[11px] px-3 py-1.5 cursor-pointer whitespace-nowrap"
                        >
                          Link & Confirm
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl bg-emerald-50/20 dark:bg-emerald-950/10">
            <div className="p-3 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-300 rounded-full w-fit mx-auto mb-3">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h3 className="text-sm font-bold text-[#0F172A] dark:text-white">
              No Discrepancies Found
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
              All dividend distributions and cash movements are currently matched to their respective bank accounts.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
