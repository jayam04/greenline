"use client";

import React, { useEffect, useState, useMemo, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { CashflowTransactionItem } from "@/components/CashflowModal";
import { TransactionItem } from "@/components/TransactionModal";

function PrintTransactionsContent() {
  const searchParams = useSearchParams();
  const accountIdsParam = searchParams.get("accounts");
  const typesParam = searchParams.get("types");
  const startDateParam = searchParams.get("startDate");
  const endDateParam = searchParams.get("endDate");

  const [cashflowTxs, setCashflowTxs] = useState<CashflowTransactionItem[]>([]);
  const [tradeTxs, setTradeTxs] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const hasPrinted = useRef(false);

  useEffect(() => {
    document.title = "Greenline - Transactions Ledger (Print)";
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [cfRes, tradeRes] = await Promise.all([
        apiFetch<CashflowTransactionItem[]>("/cashflow"),
        apiFetch<TransactionItem[]>("/transactions")
      ]);
      setCashflowTxs(cfRes || []);
      setTradeTxs(tradeRes || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      if (!hasPrinted.current) {
        hasPrinted.current = true;
        setTimeout(() => window.print(), 500);
      }
    }
  };

  const rows = useMemo(() => {
    let rawRows: any[] = [];
    cashflowTxs.forEach(cf => {
      const isTransfer = cf.transaction_kind === "TRANSFER" || cf.items.some((i) => i.category_type === "TRANSFER");
      const isIncome = !isTransfer && cf.items.some((i) => i.category_type === "INCOME");
      rawRows.push({
        type: isTransfer ? "transfer" : isIncome ? "income" : "expense",
        date: cf.transaction_date,
        title: cf.title,
        accounts: cf.payments.map(p => p.account_name).join(", "),
        accountIds: cf.payments.map(p => p.account_id),
        amount: cf.total_amount,
        currency: cf.currency || "EUR",
        category: cf.items[0]?.category_name || "Uncategorized"
      });
    });

    tradeTxs.forEach(t => {
      rawRows.push({
        type: "investment",
        date: t.transaction_date,
        title: t.asset_name || t.asset_symbol || "Trade",
        accounts: t.account_name,
        accountIds: [t.account_id, t.funding_account_id].filter(Boolean),
        amount: t.total_amount,
        currency: t.account_currency || "USD",
        category: t.transaction_type
      });
    });

    rawRows.sort((a, b) => a.date.localeCompare(b.date));

    if (accountIdsParam) {
      const ids = accountIdsParam.split(",").map(Number);
      rawRows = rawRows.filter(r => r.accountIds.some((id: number) => ids.includes(id)));
    }

    if (typesParam) {
      const allowed = typesParam.split(",");
      rawRows = rawRows.filter(r => allowed.includes(r.type));
    }

    if (startDateParam) {
      rawRows = rawRows.filter(r => r.date >= startDateParam);
    }
    
    if (endDateParam) {
      rawRows = rawRows.filter(r => r.date <= endDateParam);
    }

    return rawRows;
  }, [cashflowTxs, tradeTxs, accountIdsParam, typesParam, startDateParam, endDateParam]);

  if (loading) {
    return <div className="p-8 font-mono">Loading data for print...</div>;
  }

  return (
    <div className="bg-white text-black p-8 max-w-5xl mx-auto font-rx100 text-xs">
      <div className="mb-8 border-b-2 border-black pb-4">
        <h1 className="text-2xl font-black uppercase tracking-widest mb-1">greenline</h1>
        <h2 className="text-sm font-bold uppercase text-gray-600">Transactions Ledger Statement</h2>
        <div className="mt-2 text-gray-500">
          Generated on {new Date().toLocaleString()}
        </div>
      </div>

      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b-2 border-black text-gray-700">
            <th className="py-2 pr-4 font-bold uppercase">Date</th>
            <th className="py-2 pr-4 font-bold uppercase">Title</th>
            <th className="py-2 pr-4 font-bold uppercase">Category</th>
            <th className="py-2 pr-4 font-bold uppercase">Account(s)</th>
            <th className="py-2 text-right font-bold uppercase">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {rows.map((row, i) => (
            <tr key={i} className="align-top">
              <td className="py-2 pr-4 whitespace-nowrap">{row.date}</td>
              <td className="py-2 pr-4 max-w-[200px] truncate" title={row.title}>{row.title}</td>
              <td className="py-2 pr-4 text-gray-600 uppercase">{row.category}</td>
              <td className="py-2 pr-4 text-gray-600">{row.accounts}</td>
              <td className="py-2 text-right font-bold whitespace-nowrap">
                {formatCurrency(row.amount, row.currency)}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={5} className="py-8 text-center text-gray-500 italic">
                No transactions matched the specified criteria.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function PrintTransactionsPage() {
  return (
    <Suspense fallback={<div className="p-8 font-mono">Loading...</div>}>
      <PrintTransactionsContent />
    </Suspense>
  );
}
