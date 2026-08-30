"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { 
  Calculator, Plus, Trash2, RefreshCw, Layers, 
  TrendingUp, Calendar, AlertCircle, CheckCircle2 
} from "lucide-react";

interface CustomPrice {
  price_id: number;
  asset_id: number;
  asset_symbol: string;
  asset_name: string;
  currency: string;
  price_date: string;
  close_price: number;
  source: string;
}

interface AssetOption {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
}

export default function ValuationsPage() {
  const [prices, setPrices] = useState<CustomPrice[]>([]);
  const [assets, setAssets] = useState<AssetOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form State
  const [selectedAssetId, setSelectedAssetId] = useState<number | "">("");
  const [priceDate, setPriceDate] = useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [closePrice, setClosePrice] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Custom Valuations · greenline";
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [customPrices, assetList] = await Promise.all([
        apiFetch<CustomPrice[]>("/prices/custom"),
        apiFetch<AssetOption[]>("/assets"),
      ]);

      setPrices(customPrices || []);
      setAssets(assetList || []);

      if (assetList && assetList.length > 0 && selectedAssetId === "") {
        setSelectedAssetId(assetList[0].asset_id);
      }
    } catch (err) {
      console.error("Failed to load custom valuations:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddValuation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAssetId) {
      setErrorMsg("Please select an asset.");
      return;
    }
    const numPrice = parseFloat(closePrice);
    if (isNaN(numPrice) || numPrice <= 0) {
      setErrorMsg("Please enter a valid price per unit greater than 0.");
      return;
    }

    try {
      setSubmitting(true);
      setErrorMsg(null);

      await apiFetch("/prices", {
        method: "POST",
        body: JSON.stringify({
          asset_id: Number(selectedAssetId),
          price_date: priceDate,
          close_price: numPrice,
          source: "manual",
        }),
      });

      setClosePrice("");
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save valuation point.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteValuation = async (priceId: number) => {
    try {
      setDeletingId(priceId);
      await apiFetch(`/prices/${priceId}`, { method: "DELETE" });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete valuation point.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9] dark:border-[#1E293B]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0F172A] dark:text-white tracking-tight">
              Custom Valuations
            </h1>
            <span className="px-2 py-0.5 text-xs font-bold bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 rounded-full">
              {prices.length} Entries
            </span>
          </div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
            Log custom manual valuation price points over time for private equity, real estate, gold, or unlisted assets
          </p>
        </div>
      </div>

      {/* Main Grid: Add Valuation Form & Existing Records */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left Col: Add Valuation Form */}
        <div className="getquin-card p-5 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-[#F1F5F9] dark:border-[#1E293B]">
            <div className="p-1.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-lg">
              <Plus className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Log Valuation Point
              </h2>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Preserved across market price refreshes
              </p>
            </div>
          </div>

          <form onSubmit={handleAddValuation} className="space-y-4">
            {errorMsg && (
              <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="asset-select" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Select Asset
              </label>
              <select
                id="asset-select"
                aria-label="Select Asset"
                value={selectedAssetId}
                onChange={(e) => setSelectedAssetId(Number(e.target.value))}
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {assets.map((a) => (
                  <option key={a.asset_id} value={a.asset_id}>
                    {a.symbol} · {a.name} ({a.asset_type.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label htmlFor="valuation-date" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Valuation Date
              </label>
              <input
                id="valuation-date"
                aria-label="Valuation Date"
                type="date"
                value={priceDate}
                onChange={(e) => setPriceDate(e.target.value)}
                required
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="unit-price" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Unit Valuation Price
              </label>
              <input
                id="unit-price"
                aria-label="Unit Valuation Price"
                type="number"
                step="any"
                min="0.0001"
                placeholder="e.g. 150.00"
                value={closePrice}
                onChange={(e) => setClosePrice(e.target.value)}
                required
                className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-lg px-3 py-2 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full btn-pill-black text-xs py-2 cursor-pointer flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{submitting ? "Saving..." : "Save Valuation"}</span>
            </button>
          </form>
        </div>

        {/* Right Col: Valuations History Table */}
        <div className="lg:col-span-2 getquin-card p-5 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-[#F1F5F9] dark:border-[#1E293B]">
            <div className="p-1.5 bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] rounded-lg">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Historical Valuation Points
              </h2>
              <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
                Used in historical net worth timeline computations
              </p>
            </div>
          </div>

          {loading ? (
            <div className="py-16 text-center text-slate-400">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-400" />
              <p className="text-xs font-semibold">Loading valuations...</p>
            </div>
          ) : prices.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#F1F5F9] dark:border-[#1E293B] text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3">Asset</th>
                    <th className="py-2.5 px-3 text-right">Unit Price</th>
                    <th className="py-2.5 px-3">Source</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B]">
                  {prices.map((p) => (
                    <tr 
                      key={p.price_id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="py-3 px-3 font-semibold text-slate-600 dark:text-slate-400 whitespace-nowrap">
                        {p.price_date}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-bold text-[#0F172A] dark:text-white">
                          {p.asset_symbol}
                        </div>
                        {p.asset_name && (
                          <div className="text-[11px] text-slate-400 truncate max-w-[200px]">
                            {p.asset_name}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                        {formatCurrency(p.close_price, p.currency)}
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
                          {p.source.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => handleDeleteValuation(p.price_id)}
                          disabled={deletingId === p.price_id}
                          aria-label="Delete Valuation"
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                          title="Delete valuation point"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl bg-slate-50/50 dark:bg-slate-900/20">
              <Calculator className="w-8 h-8 mx-auto text-slate-400 mb-2" />
              <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">
                No Custom Valuations Logged
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 max-w-xs mx-auto">
                Add periodic valuation points for your unlisted assets using the form on the left.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
