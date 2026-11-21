"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { X, RefreshCw, AlertCircle } from "lucide-react";

export interface Account {
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

export interface Asset {
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

export interface AssetLookupResult {
  symbol: string;
  isin?: string | null;
  name: string;
  exchange: string;
  sector?: string | null;
  industry?: string | null;
  asset_type: string;
  currency: string;
}

// ----------------------------------------------------
// ACCOUNT MODAL POPUP COMPONENT
// ----------------------------------------------------
export interface AccountModalProps {
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface rounded-card border border-border w-full max-w-md shadow-pop p-6 relative">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-foreground p-1.5 rounded-control hover:bg-surface-2 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>

        <div className="mb-5">
          <h2 className="text-title font-semibold text-foreground">
            {initialData ? "Edit Account" : "Add New Account"}
          </h2>
          <p className="text-label text-muted mt-0.5">
            Configure brokerage, bank, or crypto investment accounts
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-loss-soft border border-loss/20 rounded-control text-loss text-label font-medium flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-body">
          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Account Name <span className="text-loss">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Zerodha Primary, Charles Schwab, Main Bank"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Broker / Platform
              </label>
              <input
                type="text"
                placeholder="e.g. Zerodha, Schwab"
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Account Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
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
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Base Currency
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
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
              <label className="block text-foreground font-semibold text-label mb-1.5 flex items-center justify-between">
                <span>Default Dividend Bank Account</span>
                <span className="text-micro text-subtle font-normal">Optional</span>
              </label>
              <select
                value={defaultDividendAccountId}
                onChange={(e) => setDefaultDividendAccountId(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
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
              <p className="text-micro text-muted mt-1">
                Dividends for stocks in this Demat account will be auto-suggested to deposit into this bank account.
              </p>
            </div>
          )}

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="rounded-control px-4 py-2 text-label font-medium text-muted hover:text-foreground hover:bg-surface-2 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={loading}
              size="sm"
            >
              {loading ? "Saving..." : initialData ? "Update Account" : "Create Account"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ----------------------------------------------------
// ASSET / SECURITY MODAL POPUP COMPONENT
// ----------------------------------------------------
export interface AssetModalProps {
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface rounded-card border border-border w-full max-w-lg shadow-pop p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-foreground p-1.5 rounded-control hover:bg-surface-2 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>

        <div className="mb-5">
          <h2 className="text-title font-semibold text-foreground">
            {initialData ? "Edit Security" : "Add Security to Master"}
          </h2>
          <p className="text-label text-muted mt-0.5">
            Register stock, ETF, or asset details in the security master
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-loss-soft border border-loss/20 rounded-control text-loss text-label font-medium flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-body">
          {/* Symbol & Auto Fetch */}
          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Ticker / Symbol <span className="text-loss">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="e.g. AAPL, MSFT, RELIANCE.NS, BTC-USD"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="flex-1 bg-surface-2 text-foreground font-bold uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
                required
              />
              <button
                type="button"
                onClick={handleLookup}
                disabled={lookingUp}
                className="rounded-control px-3 py-2 text-label font-medium text-foreground bg-surface-2 hover:bg-border border border-border shrink-0 cursor-pointer flex items-center gap-1.5 transition-colors"
                title="Fetch metadata automatically from Yahoo Finance"
              >
                <RefreshCw className={`size-3.5 ${lookingUp ? "animate-spin text-primary" : ""}`} />
                <span>{lookingUp ? "Fetching..." : "Fetch Info"}</span>
              </button>
            </div>
            {lookupError && (
              <p className="text-micro font-medium text-loss mt-1">{lookupError}</p>
            )}
          </div>

          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Security Full Name <span className="text-loss">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Apple Inc., Microsoft Corporation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Asset Type
              </label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all uppercase"
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
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Exchange
              </label>
              <input
                type="text"
                placeholder="NASDAQ, NYSE, NSE, BSE"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Trading Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
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
              <label className="block text-foreground font-semibold text-label mb-1.5">
                ISIN (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. US0378331005"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Sector (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Technology, Healthcare"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Industry (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Consumer Electronics"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="rounded-control px-4 py-2 text-label font-medium text-muted hover:text-foreground hover:bg-surface-2 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={loading}
              size="sm"
            >
              {loading ? "Saving..." : initialData ? "Update Security" : "Add Security"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
