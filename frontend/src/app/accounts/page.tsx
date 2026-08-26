"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { 
  Building2, Plus, Trash2, Edit, X, RefreshCw, Download, 
  Upload, Search, Landmark, Briefcase, Coins, PiggyBank, 
  AlertCircle, Layers
} from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  broker_name?: string;
  account_type: string;
  currency: string;
  current_balance?: number;
  cash_balance?: number;
  securities_value?: number;
  default_dividend_account_id?: number | null;
  default_dividend_account_name?: string | null;
  created_at?: string;
}

interface Asset {
  asset_id: number;
  symbol: string;
  isin?: string | null;
  name: string;
  asset_type: string;
  exchange: string;
  sector?: string | null;
  industry?: string | null;
  currency?: string;
}

interface AssetLookupResult {
  symbol: string;
  isin?: string | null;
  name: string;
  exchange: string;
  sector?: string | null;
  industry?: string | null;
  asset_type: string;
  currency: string;
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  // Modals state
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);

  const [isAssetModalOpen, setIsAssetModalOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);

  // Search filter for Security Master
  const [assetSearchQuery, setAssetSearchQuery] = useState("");

  // Import / Export state
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [accountOrder, setAccountOrder] = useState<number[]>([]);

  useEffect(() => {
    document.title = "Accounts · greenline";
    try {
      const rawLayout = typeof window !== "undefined" ? localStorage.getItem("greenline_account_layout") : null;
      if (rawLayout) {
        const parsed = JSON.parse(rawLayout);
        if (Array.isArray(parsed.order) && parsed.order.length > 0) {
          setAccountOrder(parsed.order);
        }
      }
    } catch (e) {
      console.error("Failed to load account order in accounts page:", e);
    }
    loadData();
  }, []);

  const orderedAccounts = useMemo(() => {
    const list = [...accounts];
    if (accountOrder.length > 0) {
      const orderMap = new Map<number, number>();
      accountOrder.forEach((id: number, idx: number) => orderMap.set(id, idx));
      list.sort((a, b) => {
        const orderA = orderMap.has(a.account_id) ? orderMap.get(a.account_id)! : 9999;
        const orderB = orderMap.has(b.account_id) ? orderMap.get(b.account_id)! : 9999;
        return orderA - orderB;
      });
    }
    return list;
  }, [accounts, accountOrder]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [accs, asts] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Asset[]>("/assets"),
      ]);
      setAccounts(accs || []);
      setAssets(asts || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Export Data Handler
  const handleExportData = async () => {
    try {
      const data = await apiFetch<any>("/backup/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `greenline_portfolio_backup_${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message || "Failed to export data");
    }
  };

  // Import Data Handler
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!confirm("Importing will restore your portfolio and recalculate all snapshots. Continue?")) {
      e.target.value = "";
      return;
    }

    try {
      setImporting(true);
      const formData = new FormData();
      formData.append("file", file);

      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("http://localhost:8000/api/v1/backup/import", {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Import failed");
      }

      const result = await res.json();
      alert(`Import successful! Restored ${result.imported?.accounts || 0} accounts, ${result.imported?.assets || 0} assets, and ${result.imported?.transactions || 0} transactions.`);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to import portfolio backup");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm("Are you sure you want to delete this account? Any associated transactions and balances will be removed!")) return;
    try {
      await apiFetch(`/accounts/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete account");
    }
  };

  const handleDeleteAsset = async (id: number) => {
    if (!confirm("Are you sure you want to delete this security? All associated transactions and tax lots will be removed!")) return;
    try {
      await apiFetch(`/assets/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete security");
    }
  };

  // Filtered Assets based on Search Query
  const filteredAssets = useMemo(() => {
    if (!assetSearchQuery.trim()) return assets;
    const q = assetSearchQuery.toLowerCase().trim();
    return assets.filter(
      (a) =>
        a.symbol.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        (a.isin && a.isin.toLowerCase().includes(q)) ||
        (a.sector && a.sector.toLowerCase().includes(q)) ||
        (a.industry && a.industry.toLowerCase().includes(q)) ||
        (a.exchange && a.exchange.toLowerCase().includes(q)) ||
        a.asset_type.toLowerCase().includes(q)
    );
  }, [assets, assetSearchQuery]);

  const getAccountIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "bank":
        return <Landmark className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case "crypto_exchange":
        return <Coins className="w-4 h-4 text-amber-600 dark:text-amber-400" />;
      case "pf":
      case "nps":
        return <PiggyBank className="w-4 h-4 text-purple-600 dark:text-purple-400" />;
      default:
        return <Briefcase className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9] dark:border-[#1E293B]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] dark:text-white tracking-tight">
            Accounts & Securities Master
          </h1>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
            Manage brokerage accounts, cash wallets, and master security entries
          </p>
        </div>

        {/* Data Backup & Export / Import Actions */}
        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".json"
            className="hidden"
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="btn-pill-gray text-xs cursor-pointer"
            title="Import JSON portfolio backup"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{importing ? "Importing..." : "Import Backup"}</span>
          </button>

          <button
            onClick={handleExportData}
            className="btn-pill-black text-xs cursor-pointer"
            title="Export complete portfolio backup as JSON"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Backup</span>
          </button>
        </div>
      </div>

      {/* SECTION 1: Configured Accounts (Full Width Cards) */}
      <div className="getquin-card p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9] dark:border-[#1E293B] flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-lg">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">Configured Accounts</h2>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Connected investment portfolios, bank wallets, and retirement funds ({accounts.length})
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setEditingAccount(null);
              setIsAccountModalOpen(true);
            }}
            className="btn-pill-black text-xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Account</span>
          </button>
        </div>

        {/* Accounts Cards Grid */}
        {orderedAccounts.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
            {orderedAccounts.map((acc) => (
              <div
                key={acc.account_id}
                className="bg-white dark:bg-[#121824] rounded-xl border border-slate-200/80 dark:border-slate-800 p-3 hover:shadow-xs hover:border-slate-300 dark:hover:border-slate-700 transition-all flex items-center justify-between gap-3 group"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="p-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700 rounded-lg shrink-0">
                    {getAccountIcon(acc.account_type)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h3 className="text-xs font-bold text-[#0F172A] dark:text-white truncate">
                        {acc.account_name}
                      </h3>
                      <span className="px-1.5 py-0.2 text-[9px] font-extrabold uppercase bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded shrink-0">
                        {acc.currency || "USD"}
                      </span>
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 rounded shrink-0">
                        {acc.account_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                      {acc.broker_name && (
                        <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500 truncate">
                          {acc.broker_name}
                        </p>
                      )}
                      {acc.default_dividend_account_name && (
                        <span className="text-[9px] font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 px-1.5 py-0.2 rounded border border-emerald-200 dark:border-emerald-900/50">
                          Div Bank: {acc.default_dividend_account_name}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-0.5 shrink-0 opacity-80 group-hover:opacity-100">
                  <button
                    onClick={() => {
                      setEditingAccount(acc);
                      setIsAccountModalOpen(true);
                    }}
                    className="p-1.5 text-slate-400 dark:text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md transition-colors cursor-pointer"
                    title="Edit account"
                  >
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDeleteAccount(acc.account_id)}
                    className="p-1.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-md transition-colors cursor-pointer"
                    title="Delete account"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-800/20">
            <Building2 className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
            <p className="text-xs font-bold text-slate-600 dark:text-slate-400">No Accounts Configured Yet</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1 max-w-sm mx-auto">
              Add your investment brokerage accounts, bank wallets, or mutual fund accounts to start tracking your net worth.
            </p>
          </div>
        )}
      </div>

      {/* SECTION 2: Security Master Entries (Full Width with Search Bar) */}
      <div className="getquin-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-[#F1F5F9] dark:border-[#1E293B] gap-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-lg">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">Security Master Entries</h2>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Centralized registry of stocks, ETFs, crypto, and market securities ({filteredAssets.length} of {assets.length})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Real-time Filter Bar */}
            <div className="relative min-w-[220px]">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter securities by name, ticker, ISIN..."
                value={assetSearchQuery}
                onChange={(e) => setAssetSearchQuery(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 placeholder:text-slate-400 text-xs font-semibold rounded-xl pl-8 pr-3.5 py-1.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
              {assetSearchQuery && (
                <button
                  onClick={() => setAssetSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <button
              onClick={() => {
                setEditingAsset(null);
                setIsAssetModalOpen(true);
              }}
              className="btn-pill-black text-xs cursor-pointer shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Security</span>
            </button>
          </div>
        </div>

        {/* Security Master Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#F1F5F9] dark:border-[#1E293B] text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3">Symbol / ISIN</th>
                <th className="py-2.5 px-3">Asset Name</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Exchange</th>
                <th className="py-2.5 px-3">Sector / Industry</th>
                <th className="py-2.5 px-3 text-right">Currency</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B]">
              {filteredAssets.map((ast) => (
                <tr key={ast.asset_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group">
                  <td className="py-2.5 px-3 font-bold text-[#0F172A] dark:text-white">
                    <div>{ast.symbol}</div>
                    {ast.isin && (
                      <div className="text-[10px] font-normal text-slate-400">{ast.isin}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-slate-700 dark:text-slate-300">
                    {ast.name}
                  </td>
                  <td className="py-2.5 px-3 font-semibold">
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">
                      {ast.asset_type}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-slate-500 dark:text-slate-400">
                    {ast.exchange || "US"}
                  </td>
                  <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400">
                    {ast.sector ? (
                      <div>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">{ast.sector}</span>
                        {ast.industry && <span className="text-[10px] block opacity-75">{ast.industry}</span>}
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-slate-600 dark:text-slate-400 uppercase">
                    {ast.currency || "USD"}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100">
                      <button
                        onClick={() => {
                          setEditingAsset(ast);
                          setIsAssetModalOpen(true);
                        }}
                        className="p-1.5 text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md transition-colors cursor-pointer"
                        title="Edit security"
                      >
                        <Edit className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteAsset(ast.asset_id)}
                        className="p-1.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-md transition-colors cursor-pointer"
                        title="Delete security"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredAssets.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400 font-medium">
                    No matching securities found in master directory.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* POPUP MODAL: Account Modal */}
      {isAccountModalOpen && (
        <AccountModal
          isOpen={isAccountModalOpen}
          initialData={editingAccount}
          allAccounts={accounts}
          onClose={() => {
            setIsAccountModalOpen(false);
            setEditingAccount(null);
          }}
          onSuccess={() => {
            setIsAccountModalOpen(false);
            setEditingAccount(null);
            loadData();
          }}
        />
      )}

      {/* POPUP MODAL: Asset Modal */}
      {isAssetModalOpen && (
        <AssetModal
          isOpen={isAssetModalOpen}
          initialData={editingAsset}
          onClose={() => {
            setIsAssetModalOpen(false);
            setEditingAsset(null);
          }}
          onSuccess={() => {
            setIsAssetModalOpen(false);
            setEditingAsset(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

// ----------------------------------------------------
// ACCOUNT MODAL POPUP COMPONENT
// ----------------------------------------------------
interface AccountModalProps {
  isOpen: boolean;
  initialData: Account | null;
  allAccounts?: Account[];
  onClose: () => void;
  onSuccess: () => void;
}

export function AccountModal({ isOpen, initialData, allAccounts = [], onClose, onSuccess }: AccountModalProps) {
  const [name, setName] = useState(initialData?.account_name || "");
  const [broker, setBroker] = useState(initialData?.broker_name || "");
  const [type, setType] = useState(initialData?.account_type || "demat");
  const [currency, setCurrency] = useState(initialData?.currency || "USD");
  const [defaultDividendAccountId, setDefaultDividendAccountId] = useState<number | "">(
    initialData?.default_dividend_account_id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please provide an account name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const payload: any = {
        account_name: name.trim(),
        broker_name: broker.trim() || null,
        account_type: type,
        currency: currency.toUpperCase(),
        default_dividend_account_id: type === "demat" && defaultDividendAccountId ? Number(defaultDividendAccountId) : null,
      };

      if (initialData) {
        await apiFetch(`/accounts/${initialData.account_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/accounts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to save account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 font-sans"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-[#121824] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-md shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-xl">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A] dark:text-white">
              {initialData ? "Edit Account" : "Add New Account"}
            </h2>
            <p className="text-xs font-medium text-slate-400 dark:text-slate-500">
              Configure brokerage, bank, or crypto investment accounts
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 rounded-xl text-rose-700 dark:text-rose-400 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
              Account Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Zerodha Primary, Charles Schwab, Main Bank"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Broker / Platform
              </label>
              <input
                type="text"
                placeholder="e.g. Zerodha, Schwab"
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Account Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              >
                <option value="demat">Demat / Stocks</option>
                <option value="mutual_fund">Mutual Funds</option>
                <option value="crypto_exchange">Crypto Wallet</option>
                <option value="bank">Bank / Cash</option>
                <option value="pf">Provident Fund (PF)</option>
                <option value="nps">NPS / Pension</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
              Base Currency
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
            >
              <option value="USD">USD ($ - US Dollar)</option>
              <option value="EUR">EUR (€ - Euro)</option>
              <option value="INR">INR (₹ - Indian Rupee)</option>
              <option value="GBP">GBP (£ - British Pound)</option>
              <option value="CAD">CAD (CA$ - Canadian Dollar)</option>
              <option value="AUD">AUD (A$ - Australian Dollar)</option>
              <option value="JPY">JPY (¥ - Japanese Yen)</option>
              <option value="CHF">CHF (CHF - Swiss Franc)</option>
              <option value="SGD">SGD (S$ - Singapore Dollar)</option>
            </select>
          </div>

          {type === "demat" && (
            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5 flex items-center justify-between">
                <span>Default Dividend Bank Account</span>
                <span className="text-[10px] text-slate-400 font-normal">Optional</span>
              </label>
              <select
                value={defaultDividendAccountId}
                onChange={(e) => setDefaultDividendAccountId(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              >
                <option value="">-- None (Manual Linking) --</option>
                {allAccounts
                  .filter((a) => a.account_type === "bank" && a.account_id !== initialData?.account_id)
                  .map((b) => (
                    <option key={b.account_id} value={b.account_id}>
                      {b.account_name} ({b.currency})
                    </option>
                  ))}
              </select>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1">
                Dividends for stocks in this Demat account will be auto-suggested to deposit into this bank account.
              </p>
            </div>
          )}

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill-gray text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-pill-black text-xs cursor-pointer"
            >
              {loading ? "Saving..." : initialData ? "Update Account" : "Create Account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ----------------------------------------------------
// ASSET / SECURITY MODAL POPUP COMPONENT
// ----------------------------------------------------
interface AssetModalProps {
  isOpen: boolean;
  initialData: Asset | null;
  onClose: () => void;
  onSuccess: () => void;
}

export function AssetModal({ isOpen, initialData, onClose, onSuccess }: AssetModalProps) {
  const [symbol, setSymbol] = useState(initialData?.symbol || "");
  const [name, setName] = useState(initialData?.name || "");
  const [assetType, setAssetType] = useState(initialData?.asset_type || "stock");
  const [exchange, setExchange] = useState(initialData?.exchange || "NASDAQ");
  const [currency, setCurrency] = useState(initialData?.currency || "USD");
  const [isin, setIsin] = useState(initialData?.isin || "");
  const [sector, setSector] = useState(initialData?.sector || "");
  const [industry, setIndustry] = useState(initialData?.industry || "");

  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleLookup = async () => {
    const cleanSym = symbol.trim().toUpperCase();
    if (!cleanSym) {
      setLookupError("Please enter a ticker symbol first.");
      return;
    }

    try {
      setLookingUp(true);
      setLookupError("");
      const data = await apiFetch<AssetLookupResult>(`/assets/lookup?symbol=${encodeURIComponent(cleanSym)}`);
      
      if (data.name) setName(data.name);
      if (data.exchange) setExchange(data.exchange);
      if (data.sector) setSector(data.sector);
      if (data.industry) setIndustry(data.industry);
      if (data.isin) setIsin(data.isin);
      if (data.asset_type) setAssetType(data.asset_type);
      if (data.currency) setCurrency(data.currency);
    } catch (err: any) {
      setLookupError(err.message || "Could not auto-fetch metadata from Yahoo Finance");
    } finally {
      setLookingUp(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim() || !name.trim()) {
      setError("Please fill in both Symbol and Security Name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const payload = {
        symbol: symbol.trim().toUpperCase(),
        name: name.trim(),
        asset_type: assetType,
        exchange: exchange.trim().toUpperCase(),
        currency: currency.toUpperCase(),
        isin: isin.trim() || null,
        sector: sector.trim() || null,
        industry: industry.trim() || null,
      };

      if (initialData) {
        await apiFetch(`/assets/${initialData.asset_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/assets", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to save security");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 font-sans"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-[#121824] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-lg shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-xl">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A] dark:text-white">
              {initialData ? "Edit Security" : "Add Security to Master"}
            </h2>
            <p className="text-xs font-medium text-slate-400 dark:text-slate-500">
              Register stock, ETF, or asset details in the security master
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 rounded-xl text-rose-700 dark:text-rose-400 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Symbol & Auto Fetch */}
          <div>
            <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
              Ticker / Symbol <span className="text-rose-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="e.g. AAPL, MSFT, RELIANCE.NS, BTC-USD"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="flex-1 bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-extrabold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
                required
              />
              <button
                type="button"
                onClick={handleLookup}
                disabled={lookingUp}
                className="btn-pill-gray text-xs shrink-0 cursor-pointer flex items-center gap-1.5 py-2.5"
                title="Fetch metadata automatically from Yahoo Finance"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${lookingUp ? "animate-spin text-blue-600 dark:text-blue-400" : ""}`} />
                <span>{lookingUp ? "Fetching..." : "Fetch Info"}</span>
              </button>
            </div>
            {lookupError && (
              <p className="text-[11px] font-bold text-rose-600 dark:text-rose-400 mt-1">{lookupError}</p>
            )}
          </div>

          <div>
            <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
              Security Full Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Apple Inc., Microsoft Corporation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Asset Type
              </label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all uppercase"
              >
                <option value="stock">Stock</option>
                <option value="etf">ETF</option>
                <option value="mutual_fund">Mutual Fund</option>
                <option value="crypto">Crypto</option>
                <option value="index">Index</option>
                <option value="bond">Bond</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Exchange
              </label>
              <input
                type="text"
                placeholder="NASDAQ, NYSE, NSE, BSE"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Trading Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="INR">INR (₹)</option>
                <option value="GBP">GBP (£)</option>
                <option value="CAD">CAD (CA$)</option>
                <option value="AUD">AUD (A$)</option>
                <option value="JPY">JPY (¥)</option>
                <option value="CHF">CHF (CHF)</option>
                <option value="SGD">SGD (S$)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                ISIN (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. US0378331005"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Sector (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Technology, Healthcare"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-slate-700 dark:text-slate-300 font-bold mb-1.5">
                Industry (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Consumer Electronics"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:bg-white dark:focus:bg-[#151D2B] focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill-gray text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-pill-black text-xs cursor-pointer"
            >
              {loading ? "Saving..." : initialData ? "Update Security" : "Add Security"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
