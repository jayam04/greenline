"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { 
  Building2, Plus, Trash2, Edit, X, RefreshCw, Download, 
  Upload, Search, Landmark, Briefcase, Coins, PiggyBank, 
  ShieldCheck, AlertCircle, CheckCircle2, Layers, Sparkles
} from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  broker_name?: string;
  account_type: string;
  currency: string;
  current_balance?: number;
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

  useEffect(() => {
    loadData();
  }, []);

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
        return <Landmark className="w-4 h-4 text-emerald-600" />;
      case "crypto_exchange":
        return <Coins className="w-4 h-4 text-amber-600" />;
      case "pf":
      case "nps":
        return <PiggyBank className="w-4 h-4 text-purple-600" />;
      default:
        return <Briefcase className="w-4 h-4 text-blue-600" />;
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Accounts & Securities Master
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
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
        <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9] flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0F172A] text-white rounded-lg">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A]">Configured Accounts</h2>
              <p className="text-[11px] font-medium text-slate-400">
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
        {accounts.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
            {accounts.map((acc) => (
              <div
                key={acc.account_id}
                className="bg-white rounded-xl border border-slate-200/80 p-3 hover:shadow-xs hover:border-slate-300 transition-all flex items-center justify-between gap-3 group"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="p-2 bg-slate-50 border border-slate-100 rounded-lg shrink-0">
                    {getAccountIcon(acc.account_type)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h3 className="text-xs font-bold text-[#0F172A] truncate">
                        {acc.account_name}
                      </h3>
                      <span className="px-1.5 py-0.2 text-[9px] font-extrabold uppercase bg-slate-100 text-slate-700 rounded shrink-0">
                        {acc.currency || "USD"}
                      </span>
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-blue-50 text-blue-700 rounded shrink-0">
                        {acc.account_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    {acc.broker_name && (
                      <p className="text-[11px] font-medium text-slate-400 truncate mt-0.5">
                        {acc.broker_name}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-0.5 shrink-0 opacity-80 group-hover:opacity-100">
                  <button
                    onClick={() => {
                      setEditingAccount(acc);
                      setIsAccountModalOpen(true);
                    }}
                    className="p-1.5 text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                    title="Edit account"
                  >
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDeleteAccount(acc.account_id)}
                    className="p-1.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                    title="Delete account"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <Building2 className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-xs font-bold text-slate-600">No Accounts Configured Yet</p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
              Add your investment brokerage accounts, bank wallets, or mutual fund accounts to start tracking your net worth.
            </p>
          </div>
        )}
      </div>

      {/* SECTION 2: Security Master Entries (Full Width with Search Bar) */}
      <div className="getquin-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-[#F1F5F9] gap-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0F172A] text-white rounded-lg">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A]">Security Master Entries</h2>
              <p className="text-[11px] font-medium text-slate-400">
                Centralized registry of stocks, ETFs, crypto, and market securities ({filteredAssets.length} of {assets.length})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-1 max-w-lg justify-end">
            {/* Search Box */}
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search by ticker, company name, ISIN, sector..."
                value={assetSearchQuery}
                onChange={(e) => setAssetSearchQuery(e.target.value)}
                className="w-full bg-[#F3F4F6] text-xs font-semibold text-slate-800 placeholder-slate-400 pl-8 pr-7 py-1.5 rounded-lg border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none transition-all"
              />
              {assetSearchQuery && (
                <button
                  onClick={() => setAssetSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <button
              onClick={() => {
                setEditingAsset(null);
                setIsAssetModalOpen(true);
              }}
              className="btn-pill-black text-xs shrink-0 cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Security</span>
            </button>
          </div>
        </div>

        {/* Securities Grid */}
        {filteredAssets.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1 max-h-[600px] overflow-y-auto pr-1">
            {filteredAssets.map((ast) => (
              <div
                key={ast.asset_id}
                className="bg-white rounded-xl border border-slate-200/80 p-3.5 hover:shadow-xs hover:border-slate-300 transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-extrabold text-[#0F172A] text-xs uppercase">
                        {ast.symbol}
                      </span>
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-slate-100 text-slate-700 rounded">
                        {ast.exchange || "GLOBAL"}
                      </span>
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-blue-50 text-blue-700 rounded">
                        {ast.asset_type}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                      <button
                        onClick={() => {
                          setEditingAsset(ast);
                          setIsAssetModalOpen(true);
                        }}
                        className="p-1 text-slate-400 hover:text-[#0F172A] hover:bg-slate-100 rounded cursor-pointer"
                        title="Edit security"
                      >
                        <Edit className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteAsset(ast.asset_id)}
                        className="p-1 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded cursor-pointer"
                        title="Delete security"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <h4 className="text-xs font-semibold text-slate-800 line-clamp-1">
                    {ast.name}
                  </h4>

                  <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-400 flex items-center justify-between">
                    <span className="line-clamp-1 font-medium">
                      {ast.sector ? `${ast.sector}` : "General"}
                      {ast.industry ? ` • ${ast.industry}` : ""}
                    </span>
                    {ast.isin && (
                      <span className="font-mono text-[10px] text-slate-400 shrink-0 ml-2">
                        {ast.isin}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-xs font-bold text-slate-600">
              {assetSearchQuery ? `No securities matching "${assetSearchQuery}"` : "No Securities in Master"}
            </p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
              Add your stocks, ETFs, or mutual funds to the security master to record transactions.
            </p>
          </div>
        )}
      </div>

      {/* POPUP MODAL: Account Modal */}
      {isAccountModalOpen && (
        <AccountModal
          isOpen={isAccountModalOpen}
          initialData={editingAccount}
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
  onClose: () => void;
  onSuccess: () => void;
}

function AccountModal({ isOpen, initialData, onClose, onSuccess }: AccountModalProps) {
  const [name, setName] = useState(initialData?.account_name || "");
  const [broker, setBroker] = useState(initialData?.broker_name || "");
  const [type, setType] = useState(initialData?.account_type || "demat");
  const [currency, setCurrency] = useState(initialData?.currency || "USD");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please provide an account name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const payload = {
        account_name: name.trim(),
        broker_name: broker.trim() || null,
        account_type: type,
        currency: currency.toUpperCase(),
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-900 p-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-[#0F172A] text-white rounded-xl">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Account" : "Add New Account"}
            </h2>
            <p className="text-xs font-medium text-slate-400">
              Configure brokerage, bank, or crypto investment accounts
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-700 font-bold mb-1.5">
              Account Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Zerodha Primary, Charles Schwab, Main Bank"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Broker / Platform
              </label>
              <input
                type="text"
                placeholder="e.g. Zerodha, Schwab"
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Account Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
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
            <label className="block text-slate-700 font-bold mb-1.5">
              Base Currency
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
            >
              <option value="USD">USD ($ - US Dollar)</option>
              <option value="EUR">EUR (€ - Euro)</option>
              <option value="INR">INR (₹ - Indian Rupee)</option>
              <option value="GBP">GBP (£ - British Pound)</option>
              <option value="CAD">CAD ($ - Canadian Dollar)</option>
              <option value="AUD">AUD ($ - Australian Dollar)</option>
              <option value="JPY">JPY (¥ - Japanese Yen)</option>
              <option value="CHF">CHF (Fr - Swiss Franc)</option>
              <option value="SGD">SGD ($ - Singapore Dollar)</option>
            </select>
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
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

function AssetModal({ isOpen, initialData, onClose, onSuccess }: AssetModalProps) {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-lg shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-900 p-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-[#0F172A] text-white rounded-xl">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Security" : "Add Security to Master"}
            </h2>
            <p className="text-xs font-medium text-slate-400">
              Register stock, ETF, or asset details in the security master
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Symbol & Auto Fetch */}
          <div>
            <label className="block text-slate-700 font-bold mb-1.5">
              Ticker / Symbol <span className="text-rose-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="e.g. AAPL, MSFT, RELIANCE.NS, BTC-USD"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="flex-1 bg-[#F8F9FA] text-slate-900 font-extrabold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
                required
              />
              <button
                type="button"
                onClick={handleLookup}
                disabled={lookingUp}
                className="btn-pill-gray text-xs shrink-0 cursor-pointer flex items-center gap-1.5 py-2.5"
                title="Fetch metadata automatically from Yahoo Finance"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${lookingUp ? "animate-spin text-blue-600" : ""}`} />
                <span>{lookingUp ? "Fetching..." : "Fetch Info"}</span>
              </button>
            </div>
            {lookupError && (
              <p className="text-[11px] font-bold text-rose-600 mt-1">{lookupError}</p>
            )}
          </div>

          <div>
            <label className="block text-slate-700 font-bold mb-1.5">
              Security Full Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Apple Inc., Microsoft Corporation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Asset Type
              </label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all uppercase"
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
              <label className="block text-slate-700 font-bold mb-1.5">
                Exchange
              </label>
              <input
                type="text"
                placeholder="NASDAQ, NYSE, NSE, BSE"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Trading Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="INR">INR (₹)</option>
                <option value="GBP">GBP (£)</option>
                <option value="CAD">CAD ($)</option>
                <option value="AUD">AUD ($)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                ISIN (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. US0378331005"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold uppercase rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Sector (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Technology, Healthcare"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-bold mb-1.5">
                Industry (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Consumer Electronics"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-[#F8F9FA] text-slate-900 font-semibold rounded-xl px-3.5 py-2.5 border border-slate-200 focus:border-slate-400 focus:bg-white focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
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
