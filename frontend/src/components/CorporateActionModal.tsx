"use client";

import React, { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { X, Search, Sparkles, Check, CheckCircle2 } from "lucide-react";

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

interface CorporateActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function CorporateActionModal({ isOpen, onClose, onSuccess }: CorporateActionModalProps) {
  const [assetId, setAssetId] = useState<number | "">("");
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [actionType, setActionType] = useState<string>("split");
  const [actionDate, setActionDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  
  const [ratioNew, setRatioNew] = useState<string>("2");
  const [ratioOld, setRatioOld] = useState<string>("1");
  
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
      setAssetId("");
      setSelectedAsset(null);
      setSearchQuery("");
      setSearchResults([]);
      setIsDropdownOpen(false);
      setActionType("split");
      setActionDate(new Date().toISOString().split("T")[0]);
      setRatioNew("2");
      setRatioOld("1");
      setNotes("");
    }
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchSearchResults = async () => {
      if (!searchQuery.trim()) {
        setSearchResults([]);
        return;
      }
      setIsSearching(true);
      try {
        const results = await apiFetch<SearchResultItem[]>(`/assets/search?q=${encodeURIComponent(searchQuery)}`);
        setSearchResults(results);
      } catch (err) {
        console.error("Failed to search assets:", err);
      } finally {
        setIsSearching(false);
      }
    };
    const timer = setTimeout(fetchSearchResults, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSelectAsset = async (item: SearchResultItem) => {
    try {
      setCreatingAsset(true);
      let finalAssetId = item.asset_id;
      if (!item.in_master) {
        const newAsset = await apiFetch<Asset>("/assets", {
          method: "POST",
          body: JSON.stringify({
            symbol: item.symbol,
            name: item.name,
            asset_type: item.asset_type,
            exchange: item.exchange,
            isin: item.isin,
            currency: item.currency || "USD"
          }),
        });
        finalAssetId = newAsset.asset_id;
      }
      
      if (finalAssetId) {
        setAssetId(finalAssetId);
        setSelectedAsset({
          asset_id: finalAssetId,
          symbol: item.symbol,
          name: item.name,
          isin: item.isin,
          asset_type: item.asset_type,
          exchange: item.exchange,
        });
        setSearchQuery("");
        setIsDropdownOpen(false);
      }
    } catch (err) {
      console.error("Failed to setup asset:", err);
      setError("Failed to create/select asset.");
    } finally {
      setCreatingAsset(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!assetId) {
      setError("Asset is required.");
      setLoading(false);
      return;
    }
    if (!ratioNew || !ratioOld) {
      setError("Ratio is required.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        asset_id: Number(assetId),
        action_type: actionType,
        action_date: actionDate,
        ratio: `${ratioNew}:${ratioOld}`,
        notes: notes || null,
      };

      await apiFetch("/corporate-actions", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setSuccessBanner(`Corporate Action (${actionType}) recorded successfully!`);
      onSuccess();
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Failed to submit corporate action.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Record Corporate Action</h2>
              <p className="text-sm text-slate-500">Record splits and bonus shares to automatically adjust lots.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Success Banner */}
        {successBanner && (
          <div className="bg-emerald-50 text-emerald-700 px-6 py-3 flex items-center gap-2 border-b border-emerald-100 shrink-0">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-sm font-semibold">{successBanner}</span>
          </div>
        )}

        {/* Content */}
        <div className="p-6 overflow-y-auto">
          {error && (
            <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-xl text-sm font-medium border border-red-100">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="bg-[#F8FAFC] p-5 rounded-xl border border-slate-200 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Action Type</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                  >
                    <option value="split">Stock Split</option>
                    <option value="bonus">Bonus Shares</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Action Date</label>
                  <input
                    type="date"
                    value={actionDate}
                    onChange={(e) => setActionDate(e.target.value)}
                    required
                    className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>

              {/* Security Selection */}
              <div className="relative" ref={searchContainerRef}>
                <label className="block font-semibold text-slate-600 mb-1">Security / Asset</label>
                {!selectedAsset ? (
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Search className="h-4 w-4 text-slate-400" />
                    </div>
                    <input
                      type="text"
                      placeholder="Search ticker, name, or ISIN..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setIsDropdownOpen(true);
                      }}
                      onFocus={() => setIsDropdownOpen(true)}
                      className="w-full bg-white text-slate-900 font-semibold rounded-lg pl-9 pr-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                    />
                    {isSearching && (
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                        <span className="text-xs text-slate-400 font-medium">Searching...</span>
                      </div>
                    )}
                    
                    {isDropdownOpen && searchQuery && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-xl max-h-60 overflow-y-auto">
                        {searchResults.length > 0 ? (
                          <ul className="py-1">
                            {searchResults.map((item, idx) => (
                              <li
                                key={idx}
                                onClick={() => handleSelectAsset(item)}
                                className="px-4 py-2 hover:bg-slate-50 cursor-pointer flex flex-col border-b border-slate-50 last:border-0"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-bold text-slate-900">{item.symbol}</span>
                                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                                    {item.asset_type}
                                  </span>
                                </div>
                                <span className="text-xs text-slate-500 truncate">{item.name}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="px-4 py-3 text-sm text-slate-500 text-center font-medium">
                            {!isSearching && "No matching securities found."}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2">
                    <div>
                      <div className="font-bold text-slate-900 flex items-center gap-2">
                        {selectedAsset.symbol}
                        {selectedAsset.asset_type && (
                          <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                            {selectedAsset.asset_type}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">{selectedAsset.name}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAsset(null);
                        setAssetId("");
                        setSearchQuery("");
                      }}
                      className="text-xs font-bold text-blue-600 hover:text-blue-700 bg-blue-50 px-2 py-1 rounded"
                    >
                      Change
                    </button>
                  </div>
                )}
                {creatingAsset && (
                  <p className="text-xs text-blue-600 mt-1 font-medium animate-pulse">
                    Setting up asset in database...
                  </p>
                )}
              </div>

              {/* Ratio Setup */}
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Ratio</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={ratioNew}
                    onChange={(e) => setRatioNew(e.target.value)}
                    required
                    className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none text-center"
                    placeholder="New"
                  />
                  <span className="font-bold text-slate-400">for</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={ratioOld}
                    onChange={(e) => setRatioOld(e.target.value)}
                    required
                    className="w-full bg-white text-slate-900 font-semibold rounded-lg px-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none text-center"
                    placeholder="Old"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1 font-medium">
                  {actionType === "split" 
                    ? "Example: For a 2-for-1 split, enter '2' for '1'." 
                    : "Example: For a 1:1 bonus (you get 1 new share for every 1 you own), enter '2' for '1', since the total becomes 2 for every 1 old."}
                </p>
              </div>

              {/* Notes */}
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Notes (Optional)</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full bg-white text-slate-900 text-sm rounded-lg px-3 py-2 border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none min-h-[80px]"
                  placeholder="E.g., Board approved bonus issue..."
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2 text-sm font-bold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || creatingAsset || !assetId}
                className="px-5 py-2 text-sm font-bold text-white bg-slate-900 hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? "Recording..." : "Record Action"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
