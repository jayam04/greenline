"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { PageHeader, EmptyState } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { 
  Calculator, CheckCircle2, Trash2, AlertCircle 
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
    document.title = "Valuations · greenline";
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

  const selectedAsset = assets.find((a) => a.asset_id === selectedAssetId);

  return (
    <>
      <PageHeader
        title="Valuations"
        description="Log manual price points for private equity, real estate, gold or unlisted assets."
      />

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Left Column: Log Valuation Form */}
        <Card className="rounded-card border border-border bg-surface shadow-card">
          <CardHeader>
            <CardTitle>Log valuation point</CardTitle>
            <CardDescription>Kept across market price refreshes</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddValuation} className="space-y-4">
              {errorMsg && (
                <div className="p-3 bg-loss-soft border border-loss/20 rounded-control text-loss text-label font-medium flex items-center gap-2">
                  <AlertCircle className="size-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="asset-select" className="text-label font-semibold text-foreground">
                  Asset
                </label>
                <select
                  id="asset-select"
                  aria-label="Select Asset"
                  value={selectedAssetId}
                  onChange={(e) => setSelectedAssetId(Number(e.target.value))}
                  className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none text-label"
                >
                  {assets.map((a) => (
                    <option key={a.asset_id} value={a.asset_id}>
                      {a.symbol} · {a.name} ({a.asset_type.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="valuation-date" className="text-label font-semibold text-foreground">
                  Valuation date
                </label>
                <input
                  id="valuation-date"
                  aria-label="Valuation Date"
                  type="date"
                  value={priceDate}
                  onChange={(e) => setPriceDate(e.target.value)}
                  required
                  className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none text-label"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="unit-price" className="text-label font-semibold text-foreground">
                    Unit price
                  </label>
                  <span className="text-micro text-muted">
                    {selectedAsset ? `In ${selectedAsset.currency}` : ""}
                  </span>
                </div>
                <input
                  id="unit-price"
                  aria-label="Unit Valuation Price"
                  type="number"
                  step="any"
                  placeholder="150.00"
                  value={closePrice}
                  onChange={(e) => setClosePrice(e.target.value)}
                  required
                  className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none text-label"
                />
              </div>

              <Button
                type="submit"
                disabled={submitting}
                className="w-full"
              >
                <CheckCircle2 className="size-4" />
                <span>{submitting ? "Saving..." : "Save valuation"}</span>
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Right Column: Historical Valuation Points */}
        <Card className="rounded-card border border-border bg-surface shadow-card">
          <CardHeader>
            <CardTitle>Historical valuation points</CardTitle>
            <CardDescription>Used in the net worth timeline</CardDescription>
          </CardHeader>
          <CardContent>
            {prices.length > 0 ? (
              <div className="overflow-x-auto rounded-control border border-border">
                <table className="w-full text-left text-body">
                  <thead className="border-b border-border text-micro uppercase tracking-wider text-muted font-semibold bg-surface-2/40">
                    <tr>
                      <th className="py-2.5 px-3.5">Date</th>
                      <th className="py-2.5 px-3.5">Asset</th>
                      <th className="py-2.5 px-3.5 text-right">Price per unit</th>
                      <th className="py-2.5 px-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {prices.map((p) => (
                      <tr key={p.price_id} className="hover:bg-surface-2/30 transition-colors group">
                        <td className="py-2.5 px-3.5 text-label font-medium text-muted tabular-nums">
                          {p.price_date}
                        </td>
                        <td className="py-2.5 px-3.5 font-semibold text-foreground">
                          <div>{p.asset_symbol}</div>
                          <div className="text-micro font-normal text-muted">{p.asset_name}</div>
                        </td>
                        <td className="py-2.5 px-3.5 text-right font-semibold text-foreground tabular-nums">
                          {formatCurrency(p.close_price, p.currency)}
                        </td>
                        <td className="py-2.5 px-3.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleDeleteValuation(p.price_id)}
                            disabled={deletingId === p.price_id}
                            className="p-1.5 text-loss/70 hover:text-loss hover:bg-loss-soft rounded-control transition-colors"
                            aria-label="Delete Valuation"
                            title="Delete valuation point"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={<Calculator />}
                title="No custom valuations yet"
                body="Add periodic valuation points for unlisted assets using the form on the left."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
