"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { DollarSign, ArrowUpRight, Calendar, ShieldCheck } from "lucide-react";

interface LotSale {
  lot_sale_id: number;
  lot_id: number;
  sell_transaction_id: number;
  quantity_sold: number;
  sale_price_per_unit: number;
  cost_basis: number;
  realized_pnl: number;
  holding_period_days: number;
  buy_date: string;
  sell_date: string;
  asset_symbol: string;
}

export default function RealizedPage() {
  const [sales, setSales] = useState<LotSale[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRealizedSales();
  }, []);

  const loadRealizedSales = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<LotSale[]>("/portfolio/realized-pnl");
      setSales(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const totalRealizedPnl = sales.reduce((acc, s) => acc + s.realized_pnl, 0);
  const totalCostBasis = sales.reduce((acc, s) => acc + s.cost_basis, 0);
  const shortTermPnl = sales
    .filter((s) => s.holding_period_days <= 365)
    .reduce((acc, s) => acc + s.realized_pnl, 0);
  const longTermPnl = sales
    .filter((s) => s.holding_period_days > 365)
    .reduce((acc, s) => acc + s.realized_pnl, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
          <DollarSign className="w-6 h-6 text-emerald-400" />
          Realized P&L & FIFO Sales Ledger
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Tax lot sales ledger mapping closed positions, cost basis, realized gains, and short/long-term holding classification
        </p>
      </div>

      {/* Summary Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Realized P&L</div>
          <div className={`text-2xl font-bold font-mono mt-1 ${totalRealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {totalRealizedPnl >= 0 ? "+" : ""}${totalRealizedPnl.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">Total Cost Basis: ${totalCostBasis.toFixed(2)}</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Short-Term P&L</span>
            <span className="text-[10px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full font-sans">≤ 365 Days</span>
          </div>
          <div className={`text-2xl font-bold font-mono mt-1 ${shortTermPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {shortTermPnl >= 0 ? "+" : ""}${shortTermPnl.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">STCG bucket</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Long-Term P&L</span>
            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full font-sans">&gt; 365 Days</span>
          </div>
          <div className={`text-2xl font-bold font-mono mt-1 ${longTermPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {longTermPnl >= 0 ? "+" : ""}${longTermPnl.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">LTCG bucket</div>
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Asset</th>
                <th className="py-3 px-4">Buy Date</th>
                <th className="py-3 px-4">Sell Date</th>
                <th className="py-3 px-4 text-right">Qty Sold</th>
                <th className="py-3 px-4 text-right">Sale Price</th>
                <th className="py-3 px-4 text-right">Cost Basis</th>
                <th className="py-3 px-4 text-right">Realized P&L</th>
                <th className="py-3 px-4 text-right">Holding Days</th>
                <th className="py-3 px-4 text-center">Tax Bucket</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
              {sales.length > 0 ? (
                sales.map((s) => {
                  const isLongTerm = s.holding_period_days > 365;
                  return (
                    <tr key={s.lot_sale_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3.5 px-4 font-sans font-bold text-white">{s.asset_symbol}</td>
                      <td className="py-3.5 px-4 text-slate-300">{s.buy_date}</td>
                      <td className="py-3.5 px-4 text-slate-300">{s.sell_date}</td>
                      <td className="py-3.5 px-4 text-right">{s.quantity_sold}</td>
                      <td className="py-3.5 px-4 text-right">${s.sale_price_per_unit.toFixed(2)}</td>
                      <td className="py-3.5 px-4 text-right text-slate-300">${s.cost_basis.toFixed(2)}</td>
                      <td className={`py-3.5 px-4 text-right font-bold ${s.realized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {s.realized_pnl >= 0 ? "+" : ""}${s.realized_pnl.toFixed(2)}
                      </td>
                      <td className="py-3.5 px-4 text-right text-slate-300">{s.holding_period_days} days</td>
                      <td className="py-3.5 px-4 text-center font-sans">
                        {isLongTerm ? (
                          <span className="px-2 py-0.5 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md">
                            LTCG
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md">
                            STCG
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 font-sans text-sm">
                    No realized sales logged yet.
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
