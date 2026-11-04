'use client';

import React, { useEffect, useState } from 'react';
import { Sparkles, Receipt, RefreshCw, FileUp } from 'lucide-react';
import { QuickAddBar } from '@/components/QuickAddBar';
import { MetricsCards } from '@/components/MetricsCards';
import { SpendsTable } from '@/components/SpendsTable';
import { ReceiptDropzone } from '@/components/ReceiptDropzone';
import { GeminiBanner } from '@/components/GeminiBanner';
import { SpendItem, SpendMetrics } from '@/lib/types';

export default function DashboardPage() {
  const [items, setItems] = useState<SpendItem[]>([]);
  const [metrics, setMetrics] = useState<SpendMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'upload'>('all');

  async function loadSpends() {
    try {
      const res = await fetch('/api/spends');
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
        setMetrics(data.metrics || null);
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
            setMetrics(data.metrics || null);
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

  function handleSpendAdded(newItem: SpendItem) {
    setItems(prev => [newItem, ...prev.filter(i => i.id !== newItem.id)]);
    loadSpends();
  }

  function handleReceiptProcessed() {
    loadSpends();
    setActiveTab('all');
  }

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this spend entry?')) return;
    try {
      const res = await fetch(`/api/spends/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setItems(prev => prev.filter(i => i.id !== id));
        loadSpends();
      }
    } catch (err) {
      console.error('Failed deleting spend:', err);
    }
  }

  function handleRefresh() {
    setLoading(true);
    loadSpends();
  }

  return (
    <div className="space-y-8">
      {/* Configuration alert banner if key is not set */}
      <GeminiBanner />

      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>Spends Dashboard</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              Drain v0.1
            </span>
          </h1>
          <p className="text-xs md:text-sm text-zinc-400 mt-1">
            Zero-friction spend capture. Add spends in pure English or upload bills.
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={loading}
          className="self-start md:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-medium text-zinc-300 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Natural Language Classification Input */}
      <section className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
          <span>Classify with Gemini</span>
        </div>
        <QuickAddBar onSpendAdded={handleSpendAdded} />
      </section>

      {/* KPI Metrics Cards */}
      <section>
        <MetricsCards metrics={metrics} />
      </section>

      {/* Tabs navigation */}
      <div className="border-b border-zinc-800 flex items-center justify-between">
        <div className="flex gap-6 text-sm font-medium">
          <button
            onClick={() => setActiveTab('all')}
            className={`pb-3 flex items-center gap-2 transition-colors relative ${
              activeTab === 'all'
                ? 'text-emerald-400 border-b-2 border-emerald-400 font-semibold'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Receipt className="w-4 h-4" />
            <span>Recent Transactions ({items.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`pb-3 flex items-center gap-2 transition-colors relative ${
              activeTab === 'upload'
                ? 'text-emerald-400 border-b-2 border-emerald-400 font-semibold'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <FileUp className="w-4 h-4" />
            <span>Upload Bills & Receipts</span>
          </button>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'all' ? (
        <section className="space-y-4">
          <SpendsTable items={items} onDelete={handleDelete} loading={loading} />
        </section>
      ) : (
        <section className="max-w-2xl mx-auto py-4">
          <ReceiptDropzone onReceiptProcessed={handleReceiptProcessed} />
        </section>
      )}
    </div>
  );
}
