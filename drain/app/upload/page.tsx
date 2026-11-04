'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, Sparkles, Receipt } from 'lucide-react';
import { ReceiptDropzone } from '@/components/ReceiptDropzone';
import { SpendItem } from '@/lib/types';

export default function UploadPage() {
  const [receiptSpends, setReceiptSpends] = useState<SpendItem[]>([]);

  useEffect(() => {
    fetch('/api/spends')
      .then(r => r.json())
      .then(d => {
        const receiptItems = (d.items || []).filter((i: SpendItem) => i.source === 'receipt');
        setReceiptSpends(receiptItems);
      })
      .catch(console.error);
  }, []);

  function handleProcessed(items: SpendItem[]) {
    setReceiptSpends(prev => [...items, ...prev]);
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Dashboard</span>
          </Link>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <span>Upload Bills & Receipts</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> Gemini Vision
          </span>
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Upload snapshots or PDFs of invoices, supermarket bills, restaurant tabs, or utility bills. Gemini extracts merchant names, itemizes lines, and classifies your spending automatically.
        </p>
      </div>

      <ReceiptDropzone onReceiptProcessed={handleProcessed} />

      {/* History of uploaded receipts */}
      <div className="space-y-3 pt-6 border-t border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
          <Receipt className="w-4 h-4 text-emerald-400" />
          <span>Receipt Capture History ({receiptSpends.length})</span>
        </h2>

        {receiptSpends.length === 0 ? (
          <div className="p-8 text-center rounded-2xl bg-zinc-900/40 border border-zinc-800/60 text-xs text-zinc-500">
            No bills uploaded yet. Drop a receipt above to get started!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {receiptSpends.map(item => (
              <div
                key={item.id}
                className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-800/80 flex items-start justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-zinc-100">{item.merchant}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-medium">
                      {item.type}
                    </span>
                  </div>
                  <p className="text-zinc-400 font-medium">{item.item}</p>
                  <p className="text-[11px] text-zinc-500">
                    {item.formattedDate || item.date} • {item.category}
                  </p>
                </div>
                <div className="font-bold text-emerald-400 text-sm">
                  ${Number(item.amount).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
