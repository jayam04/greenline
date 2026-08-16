"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatMoney } from "@/lib/format";
import { DollarSign, ShieldCheck, ArrowUpRight, ArrowDownRight } from "lucide-react";

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
      setSales(data || []);
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
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Header Bar */}
      <div>
        <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
          Realized Profit & Loss
        </h1>
        <p className="text-xs font-semibold text-slate-500 mt-0.5">
          Closed positions, cost basis calculations, and short-term vs long-term tax classification
        </p>
      </div>

      {/* Summary KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="getquin-card p-4">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Realized P&L</div>
          <div className={`text-2xl font-extrabold tabular-nums mt-1 flex items-center gap-1 ${totalRealizedPnl >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {totalRealizedPnl >= 0 ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownRight className="w-5 h-5" />}
            {formatMoney(totalRealizedPnl, "USD", 2, true)}
          </div>
          <div className="text-[11px] font-semibold text-slate-400 mt-1">
            Cost Basis: ${formatNum(totalCostBasis, 2)}
          </div>
        </div>

        <div className="getquin-card p-4">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
            <span>Short-Term P&L</span>
            <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-bold">
              ≤ 365 Days
            </span>
          </div>
          <div className={`text-2xl font-extrabold tabular-nums mt-1 ${shortTermPnl >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {formatMoney(shortTermPnl, "USD", 2, true)}
          </div>
          <div className="text-[11px] font-semibold text-slate-400 mt-1">
            STCG Tax Bracket
          </div>
        </div>

        <div className="getquin-card p-4">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
            <span>Long-Term P&L</span>
            <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-bold">
              &gt; 365 Days
            </span>
          </div>
          <div className={`text-2xl font-extrabold tabular-nums mt-1 ${longTermPnl >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {formatMoney(longTermPnl, "USD", 2, true)}
          </div>
          <div className="text-[11px] font-semibold text-slate-400 mt-1">
            LTCG Tax Bracket
          </div>
        </div>
      </div>

      {/* Realized Sales Table */}
      <div className="getquin-card p-5">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[11px] font-bold text-slate-400 border-b border-slate-100">
                <th className="py-2.5 px-3">Asset</th>
                <th className="py-2.5 px-3">Buy Date</th>
                <th className="py-2.5 px-3">Sell Date</th>
                <th className="py-2.5 px-3 text-right">Qty Sold</th>
                <th className="py-2.5 px-3 text-right">Sale Price</th>
                <th className="py-2.5 px-3 text-right">Cost Basis</th>
                <th className="py-2.5 px-3 text-right">Realized P&L</th>
                <th className="py-2.5 px-3 text-right">Holding Days</th>
                <th className="py-2.5 px-3 text-center">Tax Bucket</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 tabular-nums">
              {sales.length > 0 ? (
                sales.map((s) => {
                  const isLongTerm = s.holding_period_days > 365;
                  const isPositive = s.realized_pnl >= 0;
                  const initials = s.asset_symbol ? s.asset_symbol.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase() : "AST";

                  return (
                    <tr key={s.lot_sale_id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-800 font-extrabold text-[10px] flex items-center justify-center border border-slate-200/80 shrink-0">
                            {initials}
                          </div>
                          <span className="font-bold text-[#0F172A] text-xs">{s.asset_symbol}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-medium">{s.buy_date}</td>
                      <td className="py-3 px-3 text-slate-500 font-medium">{s.sell_date}</td>
                      <td className="py-3 px-3 text-right font-bold">{formatQty(s.quantity_sold)}</td>
                      <td className="py-3 px-3 text-right">${formatNum(s.sale_price_per_unit, 2)}</td>
                      <td className="py-3 px-3 text-right font-medium text-slate-600">${formatNum(s.cost_basis, 2)}</td>
                      <td className={`py-3 px-3 text-right font-extrabold ${isPositive ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                        {formatMoney(s.realized_pnl, "USD", 2, true)}
                      </td>
                      <td className="py-3 px-3 text-right font-semibold text-slate-500">{s.holding_period_days} Days</td>
                      <td className="py-3 px-3 text-center">
                        {isLongTerm ? (
                          <span className="px-2 py-0.5 text-[10px] font-bold text-blue-700 bg-blue-50 rounded">
                            LTCG
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-[10px] font-bold text-amber-700 bg-amber-50 rounded">
                            STCG
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400 font-medium">
                    No closed sales logged yet.
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
