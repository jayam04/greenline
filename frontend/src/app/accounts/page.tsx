"use client";

import React, { useEffect, useState, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { Building2, Plus, Trash2, Edit, X, Layers, RefreshCw, Download, Upload } from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  broker_name: string;
  account_type: string;
  currency: string;
}

interface Asset {
  asset_id: number;
  symbol: string;
  isin?: string | null;
  name: string;
  asset_type: string;
  exchange: string;
  sector: string;
  industry?: string | null;
}

interface AssetLookupResult {
  symbol: string;
  isin?: string | null;
  name: string;
  exchange: string;
  sector: string;
  industry?: string | null;
  asset_type: string;
  currency: string;
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  // Account form state
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [accName, setAccName] = useState("");
  const [brokerName, setBrokerName] = useState("");
  const [accType, setAccType] = useState("demat");
  const [accCurrency, setAccCurrency] = useState("USD");

  // Asset form state
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [symbol, setSymbol] = useState("");
  const [isin, setIsin] = useState("");
  const [assetName, setAssetName] = useState("");
  const [assetType, setAssetType] = useState("stock");
  const [exchange, setExchange] = useState("NASDAQ");
  const [sector, setSector] = useState("");
  const [industry, setIndustry] = useState("");
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState("");

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
      alert(`Import successful! Restored ${result.imported.accounts} accounts, ${result.imported.assets} assets, and ${result.imported.transactions} transactions.`);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to import portfolio backup");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleEditAccount = (acc: Account) => {
    setEditingAccount(acc);
    setAccName(acc.account_name);
    setBrokerName(acc.broker_name || "");
    setAccType(acc.account_type);
    setAccCurrency(acc.currency || "USD");
  };

  const handleCancelAccountEdit = () => {
    setEditingAccount(null);
    setAccName("");
    setBrokerName("");
    setAccType("demat");
    setAccCurrency("USD");
  };

  const handleSaveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        account_name: accName,
        broker_name: brokerName,
        account_type: accType,
        currency: accCurrency,
      };

      if (editingAccount) {
        await apiFetch(`/accounts/${editingAccount.account_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/accounts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      handleCancelAccountEdit();
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm("Are you sure you want to delete this account?")) return;
    try {
      await apiFetch(`/accounts/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete account");
    }
  };

  const handleEditAsset = (ast: Asset) => {
    setEditingAsset(ast);
    setSymbol(ast.symbol);
    setIsin(ast.isin || "");
    setAssetName(ast.name);
    setAssetType(ast.asset_type);
    setExchange(ast.exchange || "NASDAQ");
    setSector(ast.sector || "");
    setIndustry(ast.industry || "");
  };

  const handleCancelAssetEdit = () => {
    setEditingAsset(null);
    setSymbol("");
    setIsin("");
    setAssetName("");
    setAssetType("stock");
    setExchange("NASDAQ");
    setSector("");
    setIndustry("");
    setLookupError("");
  };

  const handleLookupSymbol = async () => {
    const cleanSym = symbol.trim().toUpperCase();
    if (!cleanSym) {
      setLookupError("Please enter a ticker symbol first.");
      return;
    }

    try {
      setLookingUp(true);
      setLookupError("");
      const data = await apiFetch<AssetLookupResult>(`/assets/lookup?symbol=${encodeURIComponent(cleanSym)}`);
      
      if (data.name) setAssetName(data.name);
      if (data.exchange) setExchange(data.exchange);
      if (data.sector) setSector(data.sector);
      if (data.industry) setIndustry(data.industry);
      if (data.isin) setIsin(data.isin);
      if (data.asset_type) setAssetType(data.asset_type);
    } catch (err: any) {
      setLookupError(err.message || "Could not auto-fetch metadata from Yahoo Finance");
    } finally {
      setLookingUp(false);
    }
  };

  const handleSaveAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        symbol: symbol.trim().toUpperCase(),
        isin: isin.trim() || null,
        name: assetName,
        asset_type: assetType,
        exchange: exchange,
        sector: sector.trim() || null,
        industry: industry.trim() || null,
        currency: "USD",
      };

      if (editingAsset) {
        await apiFetch(`/assets/${editingAsset.asset_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/assets", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      handleCancelAssetEdit();
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteAsset = async (id: number) => {
    if (!confirm("Are you sure you want to delete this security? All associated transactions will be removed!")) return;
    try {
      await apiFetch(`/assets/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete security");
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
            Manage brokerage accounts, tax status, and master asset registries
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
            className="btn-pill-gray text-xs"
            title="Import JSON portfolio backup"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{importing ? "Importing..." : "Import Data"}</span>
          </button>

          <button
            onClick={handleExportData}
            className="btn-pill-black text-xs"
            title="Export complete portfolio backup as JSON"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Backup</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Accounts Section */}
        <div className="space-y-5">
          <div className="getquin-card p-5">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#F1F5F9]">
              <h2 className="text-sm font-bold text-[#0F172A]">
                {editingAccount ? "Edit Investment Account" : "Add New Account"}
              </h2>
              {editingAccount && (
                <button onClick={handleCancelAccountEdit} className="text-xs font-bold text-rose-600 flex items-center gap-1 hover:underline">
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              )}
            </div>

            <form onSubmit={handleSaveAccount} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Account Name</label>
                <input
                  type="text"
                  placeholder="e.g. Zerodha Primary, Charles Schwab, Binance"
                  value={accName}
                  onChange={(e) => setAccName(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-slate-600 font-semibold mb-1">Broker / Platform</label>
                  <input
                    type="text"
                    placeholder="e.g. Zerodha, Schwab, Interactive Brokers"
                    value={brokerName}
                    onChange={(e) => setBrokerName(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-600 font-semibold mb-1">Account Type</label>
                  <select
                    value={accType}
                    onChange={(e) => setAccType(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
                  >
                    <option value="demat">Demat / Brokerage (Stocks & ETFs)</option>
                    <option value="mutual_fund">Mutual Funds Account</option>
                    <option value="crypto_exchange">Crypto Wallet / Exchange</option>
                    <option value="pf">Provident Fund (PF / 401k)</option>
                    <option value="nps">NPS / Pension</option>
                    <option value="bank">Bank / Cash Account</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">Account Base Currency</label>
                <select
                  value={accCurrency}
                  onChange={(e) => setAccCurrency(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
                >
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="INR">INR (₹)</option>
                  <option value="GBP">GBP (£)</option>
                  <option value="CAD">CAD ($)</option>
                  <option value="AUD">AUD ($)</option>
                </select>
              </div>

              <button
                type="submit"
                className="w-full btn-pill-black justify-center py-2 text-xs"
              >
                {editingAccount ? "Update Account" : "Create Account"}
              </button>
            </form>
          </div>

          {/* Accounts List */}
          <div className="getquin-card p-5">
            <h3 className="text-xs font-bold text-slate-400 pb-2 mb-2 border-b border-slate-100 uppercase tracking-wider">
              Configured Accounts ({accounts.length})
            </h3>
            <div className="space-y-2">
              {accounts.map((acc) => (
                <div key={acc.account_id} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:bg-slate-50">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-slate-100 rounded-lg text-slate-700">
                      <Building2 className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5">
                        {acc.account_name}
                        <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-slate-100 text-slate-600 rounded">
                          {acc.currency}
                        </span>
                      </div>
                      <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                        {acc.broker_name ? `${acc.broker_name} • ` : ""}{acc.account_type.toUpperCase()}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleEditAccount(acc)}
                      className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
                      title="Edit"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteAccount(acc.account_id)}
                      className="p-1.5 text-rose-400 hover:text-rose-600 rounded-lg hover:bg-rose-50"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Assets Section */}
        <div className="space-y-5">
          <div className="getquin-card p-5">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#F1F5F9]">
              <h2 className="text-sm font-bold text-[#0F172A]">
                {editingAsset ? "Edit Security Master" : "Add Security to Master"}
              </h2>
              {editingAsset && (
                <button onClick={handleCancelAssetEdit} className="text-xs font-bold text-rose-600 flex items-center gap-1 hover:underline">
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              )}
            </div>

            <form onSubmit={handleSaveAsset} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Ticker / Symbol</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="e.g. AAPL, MSFT, or RELIANCE.NS"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="flex-1 bg-[#F3F4F6] text-slate-900 font-bold uppercase rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                    required
                  />
                  <button
                    type="button"
                    onClick={handleLookupSymbol}
                    disabled={lookingUp}
                    className="btn-pill-gray text-xs shrink-0 cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${lookingUp ? "animate-spin text-blue-600" : ""}`} />
                    <span>{lookingUp ? "Fetching..." : "Fetch"}</span>
                  </button>
                </div>
                {lookupError && (
                  <p className="text-[11px] font-bold text-rose-600 mt-1">{lookupError}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-slate-600 font-semibold mb-1">Asset Type</label>
                  <select
                    value={assetType}
                    onChange={(e) => setAssetType(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none uppercase"
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
                  <label className="block text-slate-600 font-semibold mb-1">Exchange</label>
                  <input
                    type="text"
                    placeholder="NASDAQ / NSE / BSE"
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold uppercase rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">Security Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Apple Inc."
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">ISIN (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. US0378331005"
                  value={isin}
                  onChange={(e) => setIsin(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 font-semibold uppercase rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-slate-600 font-semibold mb-1">Sector (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. Technology"
                    value={sector}
                    onChange={(e) => setSector(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-600 font-semibold mb-1">Industry (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. Consumer Electronics"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full btn-pill-black justify-center py-2 text-xs cursor-pointer"
              >
                {editingAsset ? "Update Security" : "Add Security"}
              </button>
            </form>
          </div>

          {/* Master Securities List */}
          <div className="getquin-card p-5">
            <h3 className="text-xs font-bold text-slate-400 pb-2 mb-2 border-b border-slate-100 uppercase tracking-wider">
              Security Master Entries ({assets.length})
            </h3>
            <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
              {assets.map((ast) => (
                <div key={ast.asset_id} className="flex items-center justify-between p-2.5 rounded-lg hover:bg-slate-50 border border-slate-100">
                  <div>
                    <div className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5 flex-wrap">
                      {ast.symbol}
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-slate-100 text-slate-600 rounded">
                        {ast.exchange || "N/A"}
                      </span>
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-blue-50 text-blue-700 rounded">
                        {ast.asset_type}
                      </span>
                      {ast.isin && (
                        <span className="text-[10px] font-mono text-slate-400">
                          {ast.isin}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] font-medium text-slate-400 mt-0.5">
                      {ast.name}
                      {ast.sector ? ` • ${ast.sector}` : ""}
                      {ast.industry ? ` (${ast.industry})` : ""}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleEditAsset(ast)}
                      className="p-1 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 cursor-pointer"
                      title="Edit"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteAsset(ast.asset_id)}
                      className="p-1 text-rose-400 hover:text-rose-600 rounded hover:bg-rose-50 cursor-pointer"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
