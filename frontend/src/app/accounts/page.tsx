"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Building2, Plus, Trash2, Edit, X } from "lucide-react";

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
  name: string;
  asset_type: string;
  exchange: string;
  sector: string;
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  // Account form & edit state
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [accName, setAccName] = useState("");
  const [brokerName, setBrokerName] = useState("");
  const [accType, setAccType] = useState("demat");

  // Asset form & edit state
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [symbol, setSymbol] = useState("");
  const [assetName, setAssetName] = useState("");
  const [assetType, setAssetType] = useState("stock");
  const [exchange, setExchange] = useState("NASDAQ");
  const [sector, setSector] = useState("");

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
      setAccounts(accs);
      setAssets(asts);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Account handlers
  const handleEditAccount = (acc: Account) => {
    setEditingAccount(acc);
    setAccName(acc.account_name);
    setBrokerName(acc.broker_name || "");
    setAccType(acc.account_type);
  };

  const handleCancelAccountEdit = () => {
    setEditingAccount(null);
    setAccName("");
    setBrokerName("");
    setAccType("demat");
  };

  const handleSaveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        account_name: accName,
        broker_name: brokerName,
        account_type: accType,
        currency: "USD",
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

  // Asset handlers
  const handleEditAsset = (ast: Asset) => {
    setEditingAsset(ast);
    setSymbol(ast.symbol);
    setAssetName(ast.name);
    setAssetType(ast.asset_type);
    setExchange(ast.exchange || "NASDAQ");
    setSector(ast.sector || "");
  };

  const handleCancelAssetEdit = () => {
    setEditingAsset(null);
    setSymbol("");
    setAssetName("");
    setAssetType("stock");
    setExchange("NASDAQ");
    setSector("");
  };

  const handleSaveAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        symbol: symbol.trim().toUpperCase(),
        name: assetName,
        asset_type: assetType,
        exchange: exchange,
        sector: sector || null,
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
    if (!confirm("Are you sure you want to delete this security?")) return;
    try {
      await apiFetch(`/assets/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete security");
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
          <Building2 className="w-6 h-6 text-emerald-400" />
          Accounts & Securities Management
        </h1>
        <p className="text-xs text-slate-400 mt-1">Full CRUD management of investment accounts and security master entries</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Accounts Section */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                {editingAccount ? <Edit className="w-4 h-4 text-emerald-400" /> : <Plus className="w-4 h-4 text-emerald-400" />}
                {editingAccount ? "Edit Investment Account" : "Add Investment Account"}
              </h2>
              {editingAccount && (
                <button onClick={handleCancelAccountEdit} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              )}
            </div>

            <form onSubmit={handleSaveAccount} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Account Name</label>
                <input
                  type="text"
                  placeholder="e.g. Zerodha Demat or Fidelity 401k"
                  value={accName}
                  onChange={(e) => setAccName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Broker Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Zerodha"
                    value={brokerName}
                    onChange={(e) => setBrokerName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Account Type</label>
                  <select
                    value={accType}
                    onChange={(e) => setAccType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  >
                    <option value="demat">Demat / Brokerage</option>
                    <option value="mutual_fund">Mutual Fund</option>
                    <option value="pf">Provident Fund (PF)</option>
                    <option value="nps">NPS</option>
                    <option value="crypto_exchange">Crypto Exchange</option>
                    <option value="bank">Bank Account</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-2 bg-emerald-500 hover:bg-emerald-600 font-bold text-slate-950 rounded-lg transition-colors mt-2"
              >
                {editingAccount ? "Update Account" : "Add Account"}
              </button>
            </form>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
            <h3 className="text-sm font-bold text-white mb-3">Configured Accounts</h3>
            <div className="space-y-2">
              {accounts.map((acc) => (
                <div key={acc.account_id} className="flex items-center justify-between p-3 bg-slate-800/60 rounded-xl">
                  <div>
                    <div className="font-bold text-white text-sm">{acc.account_name}</div>
                    <div className="text-xs text-slate-400">{acc.broker_name || "N/A"} • <span className="uppercase">{acc.account_type}</span></div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditAccount(acc)}
                      className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-700 rounded transition-colors"
                      title="Edit Account"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteAccount(acc.account_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-700 rounded transition-colors"
                      title="Delete Account"
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
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                {editingAsset ? <Edit className="w-4 h-4 text-emerald-400" /> : <Plus className="w-4 h-4 text-emerald-400" />}
                {editingAsset ? "Edit Security" : "Add Security to Master"}
              </h2>
              {editingAsset && (
                <button onClick={handleCancelAssetEdit} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              )}
            </div>

            <form onSubmit={handleSaveAsset} className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Ticker / Symbol</label>
                  <input
                    type="text"
                    placeholder="e.g. AAPL or RELIANCE.NS"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 font-mono uppercase"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Asset Type</label>
                  <select
                    value={assetType}
                    onChange={(e) => setAssetType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  >
                    <option value="stock">Stock</option>
                    <option value="etf">ETF</option>
                    <option value="mutual_fund">Mutual Fund</option>
                    <option value="bond">Bond</option>
                    <option value="fd">Fixed Deposit</option>
                    <option value="crypto">Crypto</option>
                    <option value="gold">Gold</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Security Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Apple Inc."
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Exchange</label>
                  <input
                    type="text"
                    placeholder="NASDAQ / NSE / BSE"
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Sector (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. Technology"
                    value={sector}
                    onChange={(e) => setSector(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-2 bg-emerald-500 hover:bg-emerald-600 font-bold text-slate-950 rounded-lg transition-colors mt-2"
              >
                {editingAsset ? "Update Security" : "Add Security to Master"}
              </button>
            </form>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
            <h3 className="text-sm font-bold text-white mb-3">Stock Master List</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {assets.map((ast) => (
                <div key={ast.asset_id} className="flex items-center justify-between p-3 bg-slate-800/60 rounded-xl">
                  <div>
                    <div className="font-bold text-white text-sm font-mono">{ast.symbol}</div>
                    <div className="text-xs text-slate-400">{ast.name}</div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditAsset(ast)}
                      className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-700 rounded transition-colors"
                      title="Edit Security"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteAsset(ast.asset_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-700 rounded transition-colors"
                      title="Delete Security"
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
