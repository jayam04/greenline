"use client";

import React, { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { X, Plus, Edit, Search, Check, Sparkles, AlertCircle, CheckCircle2 } from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
}

interface Asset {
  asset_id: number;
  symbol: string;
  name: string;
  isin?: string | null;
  asset_type?: string;
  exchange?: string;
}

interface SearchResultItem {
  asset_id: number | null;
  symbol: string;
  isin?: string | null;
  name: string;
  exchange: string;
  asset_type: string;
  sector?: string;
  industry?: string;
  currency?: string;
  in_master: boolean;
}

export interface TransactionItem {
  transaction_id: number;
  account_id: number;
  asset_id: number | null;
  transaction_type: string;
  transaction_date: string;
  quantity: number | null;
  price_per_unit: number | null;
  total_amount: number;
  fees: number;
  taxes: number;
  notes: string | null;
}

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialData?: TransactionItem | null;
}

export function TransactionModal({ isOpen, onClose, onSuccess, initialData }: TransactionModalProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  
  const [accountId, setAccountId] = useState<number | "">("");
  const [assetId, setAssetId] = useState<number | "">("");
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [transactionType, setTransactionType] = useState<string>("buy");
  const [transactionDate, setTransactionDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [quantity, setQuantity] = useState<string>("");
  const [pricePerUnit, setPricePerUnit] = useState<string>("");
  const [totalAmount, setTotalAmount] = useState<string>("");
  const [fees, setFees] = useState<string>("0");
  const [taxes, setTaxes] = useState<string>("0");
  const [notes, setNotes] = useState<string>("");
  
  // Security Search Combobox state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [creatingAsset, setCreatingAsset] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successBanner, setSuccessBanner] = useState("");

  useEffect(() => {
    if (isOpen) {
      setError("");
      setSuccessBanner("");
      loadDropdowns();
      if (initialData) {
        setAccountId(initialData.account_id);
        setAssetId(initialData.asset_id ?? "");
        setTransactionType(initialData.transaction_type);
        setTransactionDate(initialData.transaction_date);
        setQuantity(initialData.quantity ? initialData.quantity.toString() : "");
        setPricePerUnit(initialData.price_per_unit ? initialData.price_per_unit.toString() : "");
        setTotalAmount(initialData.total_amount.toString());
        setFees(initialData.fees.toString());
        setTaxes(initialData.taxes.toString());
        setNotes(initialData.notes || "");
      } else {
        setAssetId("");
        setSelectedAsset(null);
        setSearchQuery("");
        setSearchResults([]);
        setIsDropdownOpen(false);
        setTransactionType("buy");
        setTransactionDate(new Date().toISOString().split("T")[0]);
        setQuantity("");
        setPricePerUnit("");
        setTotalAmount("");
        setFees("0");
        setTaxes("0");
        setNotes("");
      }
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

  // Sync selectedAsset when assets or assetId change
  useEffect(() => {
    if (assetId && assets.length > 0) {
      const found = assets.find((a) => a.asset_id === assetId);
      if (found) {
        setSelectedAsset(found);
        setSearchQuery(`${found.symbol} - ${found.name}`);
      }
    } else if (!assetId) {
      setSelectedAsset(null);
    }
  }, [assetId, assets]);

  const loadDropdowns = async () => {
    try {
      const [accData, astData] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Asset[]>("/assets"),
      ]);
      setAccounts(accData || []);
      setAssets(astData || []);

      if (!initialData) {
        if (accData && accData.length > 0) {
          setAccountId(accData[0].account_id);
        }
      } else if (initialData.asset_id && astData && astData.length > 0) {
        const found = astData.find((a) => a.asset_id === initialData.asset_id);
        if (found) {
          setSelectedAsset(found);
          setSearchQuery(`${found.symbol} - ${found.name}`);
        }
      }
    } catch (e: any) {
      console.error("Failed to load accounts/assets dropdowns:", e);
    }
  };

  // Close combobox dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Debounced Live Search for Assets (ISIN, Ticker, Name)
  useEffect(() => {
    if (!isDropdownOpen) return;
    const cleanQuery = searchQuery.trim();
    if (!cleanQuery) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsSearching(true);
        const results = await apiFetch<SearchResultItem[]>(`/assets/search?q=${encodeURIComponent(cleanQuery)}`);
        setSearchResults(results || []);
      } catch (err) {
        console.error("Asset search failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, isDropdownOpen]);

  // Handle selecting an asset from dropdown
  const handleSelectSearchResult = async (item: SearchResultItem) => {
    try {
      if (item.in_master && item.asset_id) {
        setAssetId(item.asset_id);
        setSelectedAsset({
          asset_id: item.asset_id,
          symbol: item.symbol,
          name: item.name,
          isin: item.isin,
          asset_type: item.asset_type,
          exchange: item.exchange,
        });
        setSearchQuery(`${item.symbol} - ${item.name}`);
        setIsDropdownOpen(false);
      } else {
        // Auto-create newly selected asset in backend
        setCreatingAsset(true);
        const newAsset = await apiFetch<Asset>("/assets/get-or-create", {
          method: "POST",
          body: JSON.stringify({
            symbol: item.symbol,
            name: item.name,
            isin: item.isin,
            exchange: item.exchange,
            asset_type: item.asset_type,
            sector: item.sector,
            industry: item.industry,
          }),
        });

        // Add to local assets list and select it
        setAssets((prev) => {
          if (prev.some((a) => a.asset_id === newAsset.asset_id)) return prev;
          return [...prev, newAsset];
        });
        setAssetId(newAsset.asset_id);
        setSelectedAsset(newAsset);
        setSearchQuery(`${newAsset.symbol} - ${newAsset.name}`);
        setIsDropdownOpen(false);
      }
    } catch (err: any) {
      setError(`Failed to register ${item.symbol}: ${err.message}`);
    } finally {
      setCreatingAsset(false);
    }
  };

  useEffect(() => {
    if (quantity && pricePerUnit && !initialData) {
      const calcTotal = (parseFloat(quantity) * parseFloat(pricePerUnit)).toFixed(2);
      setTotalAmount(calcTotal);
    }
  }, [quantity, pricePerUnit, initialData]);

  if (!isOpen) return null;

  const handleSubmit = async (e?: React.FormEvent, isAddNew: boolean = false) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError("");
    setSuccessBanner("");

    if (!accountId) {
      setError("Please select an investment account.");
      setLoading(false);
      return;
    }

    const isAssetTransaction = ["buy", "sell", "dividend"].includes(transactionType);
    if (isAssetTransaction && !assetId) {
      setError("Please select a security from master or search Yahoo Finance.");
      setLoading(false);
      return;
    }

    const parsedTotal = parseFloat(totalAmount);
    if (isNaN(parsedTotal) || parsedTotal < 0) {
      setError("Please enter a valid total amount.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        account_id: Number(accountId),
        asset_id: isAssetTransaction && assetId ? Number(assetId) : null,
        transaction_type: transactionType,
        transaction_date: transactionDate,
        quantity: quantity ? parseFloat(quantity) : null,
        price_per_unit: pricePerUnit ? parseFloat(pricePerUnit) : null,
        total_amount: parsedTotal,
        fees: parseFloat(fees || "0"),
        taxes: parseFloat(taxes || "0"),
        notes: notes || null,
      };

      if (initialData) {
        await apiFetch(`/transactions/${initialData.transaction_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        onSuccess();
        onClose();
      } else {
        await apiFetch("/transactions", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        onSuccess();

        if (isAddNew) {
          // Success notification & keep form ready for next entry
          setSuccessBanner("Transaction saved successfully! Enter next trade details below.");
          setAssetId("");
          setSelectedAsset(null);
          setSearchQuery("");
          setSearchResults([]);
          setIsDropdownOpen(false);
          setQuantity("");
          setPricePerUnit("");
          setTotalAmount("");
          setFees("0");
          setTaxes("0");
          setNotes("");
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
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 font-sans"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-[#121824] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-lg shadow-xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2.5 mb-4">
          <div className="p-2 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-xl">
            {initialData ? <Edit className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A] dark:text-white">
              {initialData ? "Edit Transaction" : "Add Transaction"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">Record buys, sells, dividends, deposits, or withdrawals</p>
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

        <form onSubmit={(e) => handleSubmit(e, false)} className="space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Transaction Type</label>
              <select
                value={transactionType}
                onChange={(e) => setTransactionType(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
                <option value="dividend">Dividend</option>
                <option value="deposit">Deposit (Cash In)</option>
                <option value="withdrawal">Withdrawal (Cash Out)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Date</label>
              <input
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Account</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none cursor-pointer"
                required
              >
                {accounts.map((acc) => (
                  <option key={acc.account_id} value={acc.account_id}>
                    {acc.account_name} ({acc.currency})
                  </option>
                ))}
              </select>
            </div>

            {/* Interactive Search Combobox for Security / Asset */}
            {["buy", "sell", "dividend"].includes(transactionType) && (
              <div className="relative" ref={searchContainerRef}>
                <label className="block font-semibold text-slate-600 mb-1">
                  Security / Asset
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    placeholder="Search ISIN, ticker, name..."
                    value={searchQuery}
                    onFocus={() => setIsDropdownOpen(true)}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setAssetId("");
                      setSelectedAsset(null);
                      setIsDropdownOpen(true);
                    }}
                    className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg pl-3 pr-8 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                    required
                  />
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute right-3 pointer-events-none" />
                </div>

                {/* Dropdown Menu */}
                {isDropdownOpen && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-white rounded-xl border border-slate-200 shadow-xl max-h-60 overflow-y-auto p-1 text-xs">
                    {creatingAsset ? (
                      <div className="py-3 px-3 text-slate-500 font-semibold flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-blue-600 animate-spin" />
                        <span>Fetching & adding security from Yahoo...</span>
                      </div>
                    ) : isSearching ? (
                      <div className="py-3 px-3 text-slate-400 font-semibold text-center">
                        Searching securities...
                      </div>
                    ) : searchResults.length > 0 ? (
                      <div className="space-y-1">
                        {searchResults.map((item, idx) => (
                          <button
                            key={`${item.symbol}-${idx}`}
                            type="button"
                            onClick={() => handleSelectSearchResult(item)}
                            className="w-full text-left p-2 rounded-lg hover:bg-slate-50 flex items-center justify-between transition-colors cursor-pointer group"
                          >
                            <div className="truncate pr-2">
                              <div className="font-bold text-[#0F172A] flex items-center gap-1.5 flex-wrap">
                                <span>{item.symbol}</span>
                                <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-slate-100 text-slate-600 rounded">
                                  {item.exchange}
                                </span>
                                <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-blue-50 text-blue-700 rounded">
                                  {item.asset_type}
                                </span>
                                {item.in_master && (
                                  <span className="px-1.5 py-0.2 text-[9px] font-bold bg-emerald-50 text-emerald-700 rounded">
                                    In Master
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-500 truncate mt-0.5">
                                {item.name}
                                {item.isin ? ` • ${item.isin}` : ""}
                              </div>
                            </div>
                            <div className="shrink-0 text-slate-300 group-hover:text-[#0F172A]">
                              {item.in_master ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : searchQuery.trim().length > 0 ? (
                      <div className="p-3 text-center">
                        <p className="text-slate-400 font-medium mb-1">No matching assets found.</p>
                        <button
                          type="button"
                          onClick={() => handleSelectSearchResult({
                            asset_id: null,
                            symbol: searchQuery.trim().toUpperCase(),
                            name: searchQuery.trim().toUpperCase(),
                            exchange: "CUSTOM",
                            asset_type: "stock",
                            in_master: false
                          })}
                          className="text-blue-600 font-bold hover:underline inline-flex items-center gap-1"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add &ldquo;{searchQuery.trim().toUpperCase()}&rdquo; to Master
                        </button>
                      </div>
                    ) : (
                      <div className="p-3 text-center text-slate-400 font-medium">
                        Type an ISIN, ticker symbol, or company name to search
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {["buy", "sell", "dividend"].includes(transactionType) && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Quantity</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 10"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required={transactionType === "buy" || transactionType === "sell"}
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-600 mb-1">Price Per Unit</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 150.50"
                  value={pricePerUnit}
                  onChange={(e) => setPricePerUnit(e.target.value)}
                  className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                  required={transactionType === "buy" || transactionType === "sell"}
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <label className="block font-semibold text-slate-600 mb-1">Total Amount</label>
              <input
                type="number"
                step="any"
                placeholder="0.00"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Fees</label>
              <input
                type="number"
                step="any"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Taxes</label>
              <input
                type="number"
                step="any"
                value={taxes}
                onChange={(e) => setTaxes(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 tabular-nums font-bold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-600 mb-1">Notes</label>
            <input
              type="text"
              placeholder="Optional notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#F3F4F6] text-slate-900 font-medium rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
            />
          </div>

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
                {loading ? "Saving..." : "Save Transaction And Add New"}
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
