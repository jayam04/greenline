"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum } from "@/lib/format";
import { ChevronDown, ChevronRight, Briefcase } from "lucide-react";

interface Lot {
  lot_id: number;
  buy_date: string;
  quantity_original: number;
  quantity_remaining: number;
  cost_per_unit: number;
}

interface Holding {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  sector: string;
  quantity_held: number;
  avg_cost_price: number;
  total_cost: number;
  latest_price: number;
  latest_price_date: string;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  xirr: number | null;
  open_lots: Lot[];
}

export default function HoldingsPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  useEffect(() => {
    loadHoldings();
  }, []);

  const loadHoldings = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<Holding[]>("/portfolio/holdings");
      setHoldings(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (assetId: number) => {
    setExpandedRow(expandedRow === assetId ? null : assetId);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
          <Briefcase className="w-6 h-6 text-emerald-400" />
          Active Holdings & Position Ledger
        </h1>
        <p className="text-xs text-slate-400 mt-1">Detailed breakdown of holding quantities, average costs, unrealized & realized P&L, and open FIFO lots</p>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4 w-10"></th>
                <th className="py-3 px-4">Asset</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-right">Quantity</th>
                <th className="py-3 px-4 text-right">Avg Cost</th>
                <th className="py-3 px-4 text-right">Total Cost</th>
                <th className="py-3 px-4 text-right">Current Price</th>
                <th className="py-3 px-4 text-right">Current Value</th>
                <th className="py-3 px-4 text-right">Unrealized P&L</th>
                <th className="py-3 px-4 text-right">Realized Profit</th>
                <th className="py-3 px-4 text-right">Per-Stock XIRR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {holdings.length > 0 ? (
                holdings.map((h) => {
                  const isExpanded = expandedRow === h.asset_id;
                  return (
                    <React.Fragment key={h.asset_id}>
                      <tr
                        onClick={() => toggleRow(h.asset_id)}
                        className="hover:bg-slate-800/50 cursor-pointer transition-colors"
                      >
                        <td className="py-3.5 px-4 text-slate-500">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </td>
                        <td className="py-3.5 px-4 font-bold text-white">
                          <div>{h.symbol}</div>
                          <div className="text-xs text-slate-400 font-normal">{h.name}</div>
                        </td>
                        <td className="py-3.5 px-4 text-xs font-semibold text-slate-400 uppercase">{h.asset_type}</td>
                        <td className="py-3.5 px-4 text-right font-mono font-medium">{formatQty(h.quantity_held)}</td>
                        <td className="py-3.5 px-4 text-right font-mono">${formatNum(h.avg_cost_price)}</td>
                        <td className="py-3.5 px-4 text-right font-mono text-slate-300">${formatNum(h.total_cost)}</td>
                        <td className="py-3.5 px-4 text-right font-mono">${formatNum(h.latest_price)}</td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-white">${formatNum(h.current_value)}</td>
                        <td className={`py-3.5 px-4 text-right font-mono font-semibold ${h.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {h.unrealized_pnl >= 0 ? "+" : ""}${formatNum(h.unrealized_pnl)} ({formatNum(h.unrealized_pnl_pct, 1)}%)
                        </td>
                        <td className={`py-3.5 px-4 text-right font-mono font-bold ${h.realized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {h.realized_pnl >= 0 ? "+" : ""}${formatNum(h.realized_pnl)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-emerald-400">
                          {h.xirr != null ? `${formatNum(h.xirr * 100, 1)}%` : "-"}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-slate-950/60">
                          <td colSpan={11} className="p-4">
                            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                                Open FIFO Lots for {h.symbol}
                              </h4>
                              {h.open_lots && h.open_lots.length > 0 ? (
                                <>
                                  <div className="grid grid-cols-5 text-xs text-slate-400 font-medium py-1 border-b border-slate-800">
                                    <span>Lot ID</span>
                                    <span>Buy Date</span>
                                    <span className="text-right">Original Qty</span>
                                    <span className="text-right">Remaining Qty</span>
                                    <span className="text-right">Cost Basis / Unit</span>
                                  </div>
                                  {h.open_lots.map((lot) => (
                                    <div key={lot.lot_id} className="grid grid-cols-5 text-xs text-slate-300 font-mono py-1">
                                      <span>#{lot.lot_id}</span>
                                      <span>{lot.buy_date}</span>
                                      <span className="text-right">{formatQty(lot.quantity_original)}</span>
                                      <span className="text-right font-bold text-emerald-400">{formatQty(lot.quantity_remaining)}</span>
                                      <span className="text-right">${formatNum(lot.cost_per_unit)}</span>
                                    </div>
                                  ))}
                                </>
                              ) : (
                                <div className="text-xs text-slate-500 italic py-1">No open lots remaining (position fully closed).</div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-500 text-sm">
                    No holdings found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
