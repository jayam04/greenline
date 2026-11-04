'use client';

import React, { useEffect, useState } from 'react';
import { Download, RefreshCw, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { SpendsTable } from '@/components/SpendsTable';
import { SpendItem } from '@/lib/types';

export default function SpendsLedgerPage() {
  const [items, setItems] = useState<SpendItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadSpends() {
    try {
      const res = await fetch('/api/spends');
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
      }
    } catch (err) {
      console.error('Failed loading spends:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const res = await fetch('/api/spends');
        if (res.ok) {
          const data = await res.json();
          if (!ignore) {
            setItems(data.items || []);
          }
        }
      } catch (err) {
        console.error('Failed loading initial spends:', err);
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, []);

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this spend?')) return;
    try {
      const res = await fetch(`/api/spends/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setItems(prev => prev.filter(i => i.id !== id));
      }
    } catch (err) {
      console.error('Failed deleting spend:', err);
    }
  }

  function handleRefresh() {
    setLoading(true);
    loadSpends();
  }

  function exportCSV() {
    if (items.length === 0) return;
    const headers = ['ID', 'Merchant', 'Item', 'Date', 'Type/Bucket', 'Category', 'Amount', 'Currency', 'Source', 'Raw Input'];
    const rows = items.map(i => [
      i.id,
      `"${i.merchant.replace(/"/g, '""')}"`,
      `"${i.item.replace(/"/g, '""')}"`,
      i.formattedDate || i.date,
      i.type,
      `"${i.category.replace(/"/g, '""')}"`,
      i.amount,
      i.currency,
      i.source,
      `"${(i.rawInput || '').replace(/"/g, '""')}"`,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `drain_spends_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Dashboard</span>
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Spends Ledger
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Complete transaction history categorized by Needs, Wants, and Savings.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-medium text-zinc-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-medium text-zinc-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <SpendsTable items={items} onDelete={handleDelete} loading={loading} />
    </div>
  );
}
