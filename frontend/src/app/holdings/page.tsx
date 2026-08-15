"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatQty, formatNum, formatCleanMoney, convertCurrencyToEUR } from "@/lib/format";
import { 
  ChevronDown, ChevronRight, Layers, ArrowUpRight, ArrowDownRight, 
  Plus, ArrowUpDown, ArrowUp, ArrowDown, CheckCircle2
} from "lucide-react";
import { TransactionModal } from "@/components/TransactionModal";

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
  currency: string;
  quantity_held: number;
  avg_cost_price: number;
  total_cost: number;
  latest_price: number;
  latest_price_date: string;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  realized_pnl_pct: number;
  xirr: number | null;
  open_lots: Lot[];
}

interface PortfolioSummary {
  total_net_worth: number;
  total_invested: number;
  total_current_value: number;
  cash_balance: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  total_fees?: number;
  total_taxes?: number;
  portfolio_xirr: number | null;
  top_holdings: Holding[];
  closed_holdings?: Holding[];
}

type SortField = "current_value" | "unrealized_pnl" | "realized_pnl" | "xirr" | "symbol" | "total_cost" | "avg_cost_price" | "latest_price" | "quantity_held";

export default function HoldingsPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [closedHoldings, setClosedHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Sorting state
  const [sortField, setSortField] = useState<SortField>("current_value");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const sumData = await apiFetch<PortfolioSummary>("/portfolio/summary");
      setSummary(sumData);
      setHoldings(sumData?.top_holdings || []);
      setClosedHoldings(sumData?.closed_holdings || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (assetId: number) => {
    setExpandedRow(expandedRow === assetId ? null : assetId);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  // Convert all holdings & metrics to EUR for the top 6 KPI cards
  const totalValueEUR = holdings.reduce(
    (acc, h) => acc + convertCurrencyToEUR(h.current_value, h.currency),
    0
  );
  const totalCostEUR = holdings.reduce(
    (acc, h) => acc + convertCurrencyToEUR(h.total_cost, h.currency),
    0
  );
  const totalUnrealizedEUR = totalValueEUR - totalCostEUR;
  const totalRealizedEUR = holdings.reduce(
    (acc, h) => acc + convertCurrencyToEUR(h.realized_pnl, h.currency),
    0
  );
  
  const rawFeesTaxes = (summary?.total_fees || 0) + (summary?.total_taxes || 0);
  const totalFeesAndTaxesEUR = convertCurrencyToEUR(rawFeesTaxes, "USD");
  const totalNetPnLEUR = totalRealizedEUR + totalUnrealizedEUR - totalFeesAndTaxesEUR;

  // Sorted holdings
  const sortedHoldings = [...holdings].sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case "symbol":
        comparison = (a.name || a.symbol).localeCompare(b.name || b.symbol);
        break;
      case "quantity_held":
        comparison = a.quantity_held - b.quantity_held;
        break;
      case "avg_cost_price":
        comparison = a.avg_cost_price - b.avg_cost_price;
        break;
      case "total_cost":
        comparison = a.total_cost - b.total_cost;
        break;
      case "latest_price":
        comparison = a.latest_price - b.latest_price;
        break;
      case "current_value":
        comparison = a.current_value - b.current_value;
        break;
      case "unrealized_pnl":
        comparison = a.unrealized_pnl - b.unrealized_pnl;
        break;
      case "realized_pnl":
        comparison = a.realized_pnl - b.realized_pnl;
        break;
      case "xirr": {
        const valA = a.xirr !== null && a.xirr !== undefined ? a.xirr : -999999;
        const valB = b.xirr !== null && b.xirr !== undefined ? b.xirr : -999999;
        comparison = valA - valB;
        break;
      }
      default:
        comparison = 0;
    }
    return sortDirection === "desc" ? -comparison : comparison;
  });

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-300 opacity-60 group-hover:opacity-100" />;
    }
    return sortDirection === "asc" ? (
      <ArrowUp className="w-3 h-3 text-blue-600" />
    ) : (
      <ArrowDown className="w-3 h-3 text-blue-600" />
    );
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-5 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Positions & Holdings
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Active asset positions, FIFO cost lots, current valuations, and annualized return metrics
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsModalOpen(true)}
            className="btn-pill-black text-xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add transaction</span>
          </button>
        </div>
      </div>

      {/* 6 Summary KPI Cards (Converted to EUR, No + / - Signs) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5">
        {/* Card 1: Total Positions Value */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Positions Value</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className="text-xl font-extrabold text-[#0F172A] tabular-nums mt-1 truncate">
            {formatCleanMoney(totalValueEUR, "EUR")}
          </div>
        </div>

        {/* Card 2: Total Invested Cost */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Invested Cost</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className="text-xl font-extrabold text-slate-800 tabular-nums mt-1 truncate">
            {formatCleanMoney(totalCostEUR, "EUR")}
          </div>
        </div>

        {/* Card 3: Total Unrealized P&L */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Unrealized P&L</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className={`text-xl font-extrabold tabular-nums mt-1 flex items-center gap-1 truncate ${totalUnrealizedEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {totalUnrealizedEUR >= 0 ? <ArrowUpRight className="w-4 h-4 shrink-0" /> : <ArrowDownRight className="w-4 h-4 shrink-0" />}
            <span className="truncate">{formatCleanMoney(totalUnrealizedEUR, "EUR")}</span>
          </div>
        </div>

        {/* Card 4: Total Realized P&L */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Realized P&L</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className={`text-xl font-extrabold tabular-nums mt-1 flex items-center gap-1 truncate ${totalRealizedEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {totalRealizedEUR >= 0 ? <ArrowUpRight className="w-4 h-4 shrink-0" /> : <ArrowDownRight className="w-4 h-4 shrink-0" />}
            <span className="truncate">{formatCleanMoney(totalRealizedEUR, "EUR")}</span>
          </div>
        </div>

        {/* Card 5: Fees & Taxes */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Fees & Taxes</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className="text-xl font-extrabold text-slate-700 tabular-nums mt-1 truncate">
            {formatCleanMoney(totalFeesAndTaxesEUR, "EUR")}
          </div>
        </div>

        {/* Card 6: Total Net P&L */}
        <div className="getquin-card p-3.5">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Total Net P&L</span>
            <span className="text-[9px] font-extrabold uppercase bg-slate-100 text-slate-600 px-1 py-0.2 rounded">
              EUR
            </span>
          </div>
          <div className={`text-xl font-extrabold tabular-nums mt-1 flex items-center gap-1 truncate ${totalNetPnLEUR >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
            {totalNetPnLEUR >= 0 ? <ArrowUpRight className="w-4 h-4 shrink-0" /> : <ArrowDownRight className="w-4 h-4 shrink-0" />}
            <span className="truncate">{formatCleanMoney(totalNetPnLEUR, "EUR")}</span>
          </div>
        </div>
      </div>

      {/* Active Holdings Table Card */}
      <div className="getquin-card p-5">
        <div className="flex items-center justify-between pb-3 mb-2 border-b border-[#F1F5F9]">
          <h3 className="text-sm font-bold text-[#0F172A]">Active Holdings</h3>
          <span className="text-[10px] font-bold text-slate-400">{sortedHoldings.length} Positions</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[11px] font-bold text-slate-400 border-b border-slate-100">
                <th className="py-2.5 px-2 w-8"></th>
                
                {/* Asset Column */}
                <th 
                  onClick={() => handleSort("symbol")}
                  className="py-2.5 px-3 cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center gap-1">
                    <span>Asset</span>
                    {renderSortIcon("symbol")}
                  </div>
                </th>

                <th className="py-2.5 px-3">Type</th>

                {/* Quantity Column */}
                <th 
                  onClick={() => handleSort("quantity_held")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Quantity</span>
                    {renderSortIcon("quantity_held")}
                  </div>
                </th>

                {/* Avg Cost Column */}
                <th 
                  onClick={() => handleSort("avg_cost_price")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Avg Cost</span>
                    {renderSortIcon("avg_cost_price")}
                  </div>
                </th>

                {/* Total Cost Column */}
                <th 
                  onClick={() => handleSort("total_cost")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Total Cost</span>
                    {renderSortIcon("total_cost")}
                  </div>
                </th>

                {/* Current Price Column */}
                <th 
                  onClick={() => handleSort("latest_price")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Current Price</span>
                    {renderSortIcon("latest_price")}
                  </div>
                </th>

                {/* Current Value Column */}
                <th 
                  onClick={() => handleSort("current_value")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Current Value</span>
                    {renderSortIcon("current_value")}
                  </div>
                </th>

                {/* Unrealized P&L Column */}
                <th 
                  onClick={() => handleSort("unrealized_pnl")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Unrealized P&L</span>
                    {renderSortIcon("unrealized_pnl")}
                  </div>
                </th>

                {/* Realized P&L Column */}
                <th 
                  onClick={() => handleSort("realized_pnl")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Realized P&L</span>
                    {renderSortIcon("realized_pnl")}
                  </div>
                </th>

                {/* XIRR Column */}
                <th 
                  onClick={() => handleSort("xirr")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none hover:text-slate-900 transition-colors group"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>XIRR</span>
                    {renderSortIcon("xirr")}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 tabular-nums">
              {sortedHoldings.length > 0 ? (
                sortedHoldings.map((h) => {
                  const isExpanded = expandedRow === h.asset_id;
                  const initials = h.symbol.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase();
                  const isPositiveUnrealized = h.unrealized_pnl >= 0;
                  const isPositiveRealized = h.realized_pnl >= 0;
                  const hasRealized = Math.abs(h.realized_pnl) > 0.0001;
                  const hasXirr = h.xirr !== null && h.xirr !== undefined;
                  const isPositiveXirr = hasXirr && h.xirr! >= 0;

                  return (
                    <React.Fragment key={h.asset_id}>
                      <tr
                        onClick={() => toggleRow(h.asset_id)}
                        className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                      >
                        <td className="py-3 px-2 text-slate-400">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-blue-600" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-slate-300" />
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-800 font-extrabold text-[10px] flex items-center justify-center border border-slate-200/80 shrink-0">
                              {initials}
                            </div>
                            <div>
                              <div className="font-bold text-[#0F172A] text-xs">{h.name || h.symbol}</div>
                              <div className="text-[11px] font-semibold text-slate-400">{h.symbol}</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 text-[10px] font-bold uppercase bg-slate-100 text-slate-700 rounded-md">
                            {h.asset_type}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-bold">{formatQty(h.quantity_held)}</td>
                        <td className="py-3 px-3 text-right">{formatCleanMoney(h.avg_cost_price, h.currency)}</td>
                        <td className="py-3 px-3 text-right font-semibold text-slate-700">{formatCleanMoney(h.total_cost, h.currency)}</td>
                        <td className="py-3 px-3 text-right">{formatCleanMoney(h.latest_price, h.currency)}</td>
                        <td className="py-3 px-3 text-right font-extrabold text-[#0F172A]">{formatCleanMoney(h.current_value, h.currency)}</td>

                        {/* 2-Line Unrealized P&L: Line 1 Amount, Line 2 % with Arrow */}
                        <td className="py-3 px-3 text-right">
                          <div className={`font-bold text-xs ${isPositiveUnrealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                            {formatCleanMoney(h.unrealized_pnl, h.currency)}
                          </div>
                          <div className={`text-[11px] font-semibold flex items-center justify-end gap-0.5 mt-0.5 ${isPositiveUnrealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                            {isPositiveUnrealized ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                            <span>{formatNum(Math.abs(h.unrealized_pnl_pct), 2)}%</span>
                          </div>
                        </td>

                        {/* 2-Line Realized P&L: Line 1 Amount, Line 2 % with Arrow */}
                        <td className="py-3 px-3 text-right">
                          <div className={`font-bold text-xs ${isPositiveRealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                            {formatCleanMoney(h.realized_pnl, h.currency)}
                          </div>
                          {hasRealized ? (
                            <div className={`text-[11px] font-semibold flex items-center justify-end gap-0.5 mt-0.5 ${isPositiveRealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                              {isPositiveRealized ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                              <span>{formatNum(Math.abs(h.realized_pnl_pct || 0), 2)}%</span>
                            </div>
                          ) : (
                            <div className="text-[11px] font-medium text-slate-400 mt-0.5">-</div>
                          )}
                        </td>

                        {/* XIRR Column with Sign-free Arrow */}
                        <td className="py-3 px-3 text-right">
                          {hasXirr ? (
                            isPositiveXirr ? (
                              <span className="font-extrabold text-[#16A34A] flex items-center justify-end gap-0.5">
                                <ArrowUpRight className="w-3 h-3" />
                                {(Math.abs(h.xirr!) * 100).toFixed(1)}%
                              </span>
                            ) : (
                              <span className="font-extrabold text-[#DC2626] flex items-center justify-end gap-0.5">
                                <ArrowDownRight className="w-3 h-3" />
                                {(Math.abs(h.xirr!) * 100).toFixed(1)}%
                              </span>
                            )
                          ) : (
                            <span className="text-slate-400 font-medium">-</span>
                          )}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-slate-50/70">
                          <td colSpan={11} className="p-3">
                            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
                              <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider mb-2.5 flex items-center gap-2">
                                <Layers className="w-3.5 h-3.5 text-blue-600" />
                                FIFO Lots Breakdown for {h.symbol}
                              </h4>
                              {h.open_lots && h.open_lots.length > 0 ? (
                                <table className="w-full text-left text-xs tabular-nums">
                                  <thead>
                                    <tr className="text-slate-400 text-[11px] font-semibold border-b border-slate-100">
                                      <th className="py-1.5 px-2">Lot ID</th>
                                      <th className="py-1.5 px-2">Buy Date</th>
                                      <th className="py-1.5 px-2 text-right">Original Qty</th>
                                      <th className="py-1.5 px-2 text-right">Remaining Qty</th>
                                      <th className="py-1.5 px-2 text-right">Unit Cost Basis</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100">
                                    {h.open_lots.map((lot) => (
                                      <tr key={lot.lot_id} className="hover:bg-slate-50">
                                        <td className="py-1.5 px-2 font-bold text-slate-700">#{lot.lot_id}</td>
                                        <td className="py-1.5 px-2 text-slate-600">{lot.buy_date}</td>
                                        <td className="py-1.5 px-2 text-right">{formatQty(lot.quantity_original)}</td>
                                        <td className="py-1.5 px-2 text-right font-bold text-[#16A34A]">{formatQty(lot.quantity_remaining)}</td>
                                        <td className="py-1.5 px-2 text-right font-bold">{formatCleanMoney(lot.cost_per_unit, h.currency)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              ) : (
                                <div className="text-xs text-slate-400 italic">No open lots remaining.</div>
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
                  <td colSpan={11} className="py-12 text-center text-slate-400 font-medium">
                    {loading ? "Loading positions..." : "No active holdings logged."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dedicated Closed Positions Table (Conditional: Only visible if closed positions exist) */}
      {closedHoldings.length > 0 && (
        <div className="getquin-card p-5">
          <div className="flex items-center justify-between pb-3 mb-2 border-b border-[#F1F5F9]">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-slate-500" />
              <h3 className="text-sm font-bold text-[#0F172A]">Closed Positions</h3>
            </div>
            <span className="text-[10px] font-extrabold uppercase bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
              {closedHoldings.length} Sold Out
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[11px] font-bold text-slate-400 border-b border-slate-100">
                  <th className="py-2.5 px-3">Asset</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Cost Basis</th>
                  <th className="py-2.5 px-3 text-right">Last Price</th>
                  <th className="py-2.5 px-3 text-right">Realized P&L</th>
                  <th className="py-2.5 px-3 text-right">XIRR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 tabular-nums">
                {closedHoldings.map((c) => {
                  const initials = c.symbol.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase();
                  const isPositiveRealized = c.realized_pnl >= 0;
                  const hasXirr = c.xirr !== null && c.xirr !== undefined;
                  const isPositiveXirr = hasXirr && c.xirr! >= 0;

                  return (
                    <tr key={c.asset_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-500 font-bold text-[10px] flex items-center justify-center border border-slate-200 shrink-0">
                            {initials}
                          </div>
                          <div>
                            <div className="font-bold text-[#0F172A] text-xs">{c.name || c.symbol}</div>
                            <div className="text-[11px] font-semibold text-slate-400">{c.symbol}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 text-[10px] font-bold uppercase bg-slate-100 text-slate-600 rounded-md">
                          {c.asset_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-semibold text-slate-700">
                        {formatCleanMoney(c.total_cost, c.currency)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500">
                        {formatCleanMoney(c.latest_price, c.currency)}
                      </td>

                      {/* 2-Line Realized P&L */}
                      <td className="py-3 px-3 text-right">
                        <div className={`font-bold text-xs ${isPositiveRealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                          {formatCleanMoney(c.realized_pnl, c.currency)}
                        </div>
                        <div className={`text-[11px] font-semibold flex items-center justify-end gap-0.5 mt-0.5 ${isPositiveRealized ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                          {isPositiveRealized ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          <span>{formatNum(Math.abs(c.realized_pnl_pct || 0), 2)}%</span>
                        </div>
                      </td>

                      {/* XIRR Column */}
                      <td className="py-3 px-3 text-right">
                        {hasXirr ? (
                          isPositiveXirr ? (
                            <span className="font-extrabold text-[#16A34A] flex items-center justify-end gap-0.5">
                              <ArrowUpRight className="w-3 h-3" />
                              {(Math.abs(c.xirr!) * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span className="font-extrabold text-[#DC2626] flex items-center justify-end gap-0.5">
                              <ArrowDownRight className="w-3 h-3" />
                              {(Math.abs(c.xirr!) * 100).toFixed(1)}%
                            </span>
                          )
                        ) : (
                          <span className="text-slate-400 font-medium">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadData}
      />
    </div>
  );
}
