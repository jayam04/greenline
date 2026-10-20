"use client";

import React, { useEffect, useState, useMemo, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { CashflowTransactionItem } from "@/components/CashflowModal";
import { TransactionItem } from "@/components/TransactionModal";

interface AccountRow {
  accountId: number;
  accountName: string;
  type: string;
  date: string;
  title: string;
  amount: number;
  currency: string;
  category: string;
}

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

  const accountGroups = useMemo(() => {
    const rawRows: AccountRow[] = [];

    // 1. Process Cashflows
    cashflowTxs.forEach(cf => {
      const isTransfer = cf.transaction_kind === "TRANSFER" || cf.items.some((i) => i.category_type === "TRANSFER");
      const isIncome = !isTransfer && cf.items.some((i) => i.category_type === "INCOME");
      const type = isTransfer ? "transfer" : isIncome ? "income" : "expense";
      
      cf.payments.forEach(p => {
        if (p.amount === 0) return;
        rawRows.push({
          accountId: p.account_id,
          accountName: p.account_name || "Unknown",
          type,
          date: cf.transaction_date,
          title: cf.title,
          amount: p.amount,
          currency: p.account_currency || cf.currency || "USD",
          category: cf.items[0]?.category_name || "Uncategorized"
        });
      });
    });

    // 2. Process Trades
    tradeTxs.forEach(t => {
      const ttype = (t.transaction_type || "").toLowerCase();
      const isBuy = ttype === "buy";
      const isSell = ttype === "sell";
      const isDiv = ttype === "dividend";
      const isDeposit = ttype === "deposit";
      const isWithdrawal = ttype === "withdrawal";

      const title = t.asset_name || t.asset_symbol || "Trade";
      const category = t.transaction_type;

      const grossAmt = (t.quantity && t.price_per_unit) ? (t.quantity * t.price_per_unit) : t.total_amount;
      const fees = t.fees || 0;
      const taxes = t.taxes || 0;
      
      const holdingId = t.account_id;
      const holdingName = t.account_name || "Demat Account";
      const holdingCur = t.account_currency || "USD";

      const fundingId = t.funding_account_id || t.account_id;
      const fundingName = t.funding_account_name || holdingName;
      const fundingCur = t.funding_account_currency || holdingCur;

      if (isBuy) {
        rawRows.push({
          accountId: fundingId,
          accountName: fundingId === holdingId ? `${holdingName} (Cash)` : fundingName,
          type: "investment",
          date: t.transaction_date,
          title,
          amount: -(grossAmt + fees + taxes),
          currency: fundingCur,
          category
        });
      } else if (isSell) {
        rawRows.push({
          accountId: fundingId,
          accountName: fundingId === holdingId ? `${holdingName} (Cash)` : fundingName,
          type: "investment",
          date: t.transaction_date,
          title,
          amount: Math.max(0, grossAmt - fees - taxes),
          currency: fundingCur,
          category
        });
      } else if (isDiv) {
        rawRows.push({
          accountId: fundingId,
          accountName: fundingId === holdingId ? `${holdingName} (Cash)` : fundingName,
          type: "investment",
          date: t.transaction_date,
          title,
          amount: Math.max(0, grossAmt - taxes),
          currency: fundingCur,
          category
        });
      } else if (isDeposit) {
        rawRows.push({
          accountId: holdingId,
          accountName: holdingName,
          type: "transfer",
          date: t.transaction_date,
          title: "Deposit",
          amount: grossAmt,
          currency: holdingCur,
          category
        });
        if (t.funding_account_id && t.funding_account_id !== t.account_id) {
          rawRows.push({
            accountId: fundingId,
            accountName: fundingName,
            type: "transfer",
            date: t.transaction_date,
            title: "Deposit (Outward)",
            amount: -grossAmt,
            currency: fundingCur,
            category
          });
        }
      } else if (isWithdrawal) {
        rawRows.push({
          accountId: holdingId,
          accountName: holdingName,
          type: "transfer",
          date: t.transaction_date,
          title: "Withdrawal",
          amount: -grossAmt,
          currency: holdingCur,
          category
        });
        if (t.funding_account_id && t.funding_account_id !== t.account_id) {
          rawRows.push({
            accountId: fundingId,
            accountName: fundingName,
            type: "transfer",
            date: t.transaction_date,
            title: "Withdrawal (Inward)",
            amount: grossAmt,
            currency: fundingCur,
            category
          });
        }
      }
    });

    // 3. Sort chronologically
    rawRows.sort((a, b) => a.date.localeCompare(b.date));

    // 4. Calculate Balances and Group
    const groups: Record<number, { accountName: string, currency: string, rows: AccountRow[], openingBalance: number, closingBalance: number }> = {};
    
    rawRows.forEach(r => {
      if (!groups[r.accountId]) {
        groups[r.accountId] = { 
          accountName: r.accountName, 
          currency: r.currency,
          rows: [], 
          openingBalance: 0, 
          closingBalance: 0 
        };
      }
      
      const g = groups[r.accountId];
      const isBeforeStart = startDateParam ? r.date < startDateParam : false;
      const isAfterEnd = endDateParam ? r.date > endDateParam : false;

      // Always process for accurate absolute balances
      if (isBeforeStart) {
        g.openingBalance += r.amount;
        g.closingBalance += r.amount;
      } else if (!isAfterEnd) {
        g.closingBalance += r.amount;
        
        // Only push to visible rows if it matches the type filter
        if (!typesParam || typesParam.split(",").includes(r.type)) {
          g.rows.push(r);
        }
      }
    });

    // 5. Convert to array and filter by accountIds
    let result = Object.entries(groups).map(([id, grp]) => ({
      accountId: Number(id),
      accountName: grp.accountName,
      currency: grp.currency,
      openingBalance: grp.openingBalance,
      closingBalance: grp.closingBalance,
      rows: grp.rows
    }));

    if (accountIdsParam) {
      const ids = accountIdsParam.split(",").map(Number);
      result = result.filter(g => ids.includes(g.accountId));
    }

    return result.sort((a, b) => a.accountName.localeCompare(b.accountName));

  }, [cashflowTxs, tradeTxs, accountIdsParam, typesParam, startDateParam, endDateParam]);

  if (loading) {
    return <div className="p-8 font-mono">Loading data for print...</div>;
  }

  return (
    <div className="bg-white text-black p-8 max-w-5xl mx-auto font-rx100 text-xs">
      <div className="mb-8 border-b-2 border-black pb-4 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-black uppercase tracking-widest mb-1">greenline</h1>
          <h2 className="text-sm font-bold uppercase text-gray-600">Transactions Ledger Statement</h2>
        </div>
        <div className="text-right text-gray-500">
          Generated on {new Date().toLocaleString()}
        </div>
      </div>

      {accountGroups.length === 0 && (
        <div className="py-12 text-center text-gray-500 italic">
          No transactions matched the specified criteria.
        </div>
      )}

      {accountGroups.map(group => (
        <div key={group.accountId} className="mb-12 page-break-inside-avoid">
          <h3 className="text-lg font-bold mb-3 border-l-4 border-black pl-3 bg-gray-50 py-1">
            Account: {group.accountName}
          </h3>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-400 text-gray-700">
                <th className="py-2 pr-4 font-bold uppercase w-28">Date</th>
                <th className="py-2 pr-4 font-bold uppercase">Title</th>
                <th className="py-2 pr-4 font-bold uppercase w-48">Category</th>
                <th className="py-2 text-right font-bold uppercase w-32">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr className="align-top bg-gray-50/50">
                <td className="py-2 pr-4 whitespace-nowrap text-gray-600"></td>
                <td className="py-2 pr-4 font-bold text-gray-800">&lt;Opening Balance&gt;</td>
                <td className="py-2 pr-4 text-gray-500 uppercase text-[10px]"></td>
                <td className={`py-2 text-right font-bold whitespace-nowrap ${group.openingBalance < 0 ? 'text-gray-900' : 'text-gray-900'}`}>
                  {formatCurrency(group.openingBalance, group.currency)}
                </td>
              </tr>
              {group.rows.map((row, i) => (
                <tr key={i} className="align-top">
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-600">{row.date}</td>
                  <td className="py-2 pr-4 max-w-[300px] truncate" title={row.title}>{row.title}</td>
                  <td className="py-2 pr-4 text-gray-500 uppercase text-[10px]">{row.category}</td>
                  <td className={`py-2 text-right font-bold whitespace-nowrap ${row.amount < 0 ? 'text-gray-900' : 'text-gray-900'}`}>
                    {row.amount > 0 ? "+" : ""}{formatCurrency(row.amount, row.currency)}
                  </td>
                </tr>
              ))}
              <tr className="align-top bg-gray-100/50 border-t-2 border-gray-200">
                <td className="py-2 pr-4 whitespace-nowrap text-gray-600"></td>
                <td className="py-2 pr-4 font-bold text-gray-900">&lt;Closing Balance&gt;</td>
                <td className="py-2 pr-4 text-gray-500 uppercase text-[10px]"></td>
                <td className={`py-2 text-right font-bold whitespace-nowrap ${group.closingBalance < 0 ? 'text-gray-900' : 'text-gray-900'}`}>
                  {formatCurrency(group.closingBalance, group.currency)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
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
