'use client';

import React, { useState } from 'react';
import {
  Search,
  Trash2,
  Receipt,
  Tag,
  Building2,
  Calendar,
  Sparkles,
  Filter,
} from 'lucide-react';
import { SpendItem, SpendBucket } from '@/lib/types';

interface SpendsTableProps {
  items: SpendItem[];
  onDelete?: (id: string) => void;
  loading?: boolean;
}

export function SpendsTable({ items, onDelete, loading }: SpendsTableProps) {
  const [search, setSearch] = useState('');
  const [selectedBucket, setSelectedBucket] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  // Compute unique categories
  const categories = Array.from(new Set(items.map(i => i.category))).filter(Boolean);

  // Filter items
  const filtered = items.filter(item => {
    const matchesSearch =
      !search ||
      item.merchant.toLowerCase().includes(search.toLowerCase()) ||
      item.item.toLowerCase().includes(search.toLowerCase()) ||
      item.category.toLowerCase().includes(search.toLowerCase()) ||
      (item.rawInput && item.rawInput.toLowerCase().includes(search.toLowerCase()));

    const matchesBucket = selectedBucket === 'all' || item.type === selectedBucket;
    const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;

    return matchesSearch && matchesBucket && matchesCategory;
  });

  function getBucketBadge(bucket: SpendBucket) {
    switch (bucket) {
      case 'Needs':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      case 'Wants':
        return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
      case 'Savings':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'Debt':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  }

  return (
    <div className="w-full space-y-4">
      {/* Filter toolbar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search merchant, item, or category..."
            className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/60"
          />
        </div>

        {/* Dropdowns */}
        <div className="flex items-center gap-2">
          {/* Bucket filter */}
          <div className="relative">
            <select
              value={selectedBucket}
              onChange={e => setSelectedBucket(e.target.value)}
              className="appearance-none bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 pr-8 text-xs text-zinc-300 font-medium focus:outline-none focus:border-emerald-500/60"
            >
              <option value="all">All Buckets</option>
              <option value="Needs">Needs</option>
              <option value="Wants">Wants</option>
              <option value="Savings">Savings</option>
              <option value="Debt">Debt</option>
            </select>
            <Filter className="w-3 h-3 absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>

          {/* Category filter */}
          <div className="relative">
            <select
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              className="appearance-none bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 pr-8 text-xs text-zinc-300 font-medium focus:outline-none focus:border-emerald-500/60"
            >
              <option value="all">All Categories</option>
              {categories.map(c => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <Tag className="w-3 h-3 absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Table container */}
      <div className="overflow-x-auto rounded-2xl border border-zinc-800/80 bg-zinc-900/60 shadow-sm">
        <table className="w-full text-left text-sm text-zinc-300">
          <thead className="bg-zinc-950/80 text-[11px] uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="py-3 px-4 font-semibold">Merchant / Store</th>
              <th className="py-3 px-4 font-semibold">Item & Details</th>
              <th className="py-3 px-4 font-semibold">Date</th>
              <th className="py-3 px-4 font-semibold">Bucket</th>
              <th className="py-3 px-4 font-semibold">Category</th>
              <th className="py-3 px-4 font-semibold text-right">Amount</th>
              <th className="py-3 px-4 font-semibold text-center w-12">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 font-normal">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-zinc-500 text-sm">
                  Loading spends ledger...
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-zinc-500 text-sm">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Receipt className="w-8 h-8 text-zinc-600" />
                    <span>No spends match your query.</span>
                    <span className="text-xs text-zinc-600">
                      Try typing &quot;bought coffee for $4&quot; in the quick add bar above!
                    </span>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map(item => (
                <tr
                  key={item.id}
                  className="hover:bg-zinc-800/30 transition-colors group"
                >
                  {/* Merchant */}
                  <td className="py-3.5 px-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-300 shrink-0">
                        <Building2 className="w-4 h-4" />
                      </div>
                      <div className="flex flex-col">
                        <span className="font-semibold text-zinc-100">{item.merchant}</span>
                        {item.source === 'receipt' && (
                          <span className="text-[10px] text-teal-400 flex items-center gap-1">
                            <Sparkles className="w-2.5 h-2.5" /> From Receipt
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Item Description */}
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="text-zinc-200 font-medium">{item.item}</span>
                      {item.rawInput && item.rawInput !== item.item && (
                        <span className="text-[11px] text-zinc-500 italic truncate max-w-xs">
                          &ldquo;{item.rawInput}&rdquo;
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Date */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-1.5 text-zinc-400 text-xs">
                      <Calendar className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{item.formattedDate || item.date}</span>
                    </div>
                  </td>

                  {/* Bucket */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${getBucketBadge(
                        item.type
                      )}`}
                    >
                      {item.type}
                    </span>
                  </td>

                  {/* Category */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs bg-zinc-800/80 text-zinc-300 border border-zinc-700/60 font-medium">
                      <Tag className="w-3 h-3 text-zinc-400" />
                      {item.category}
                    </span>
                  </td>

                  {/* Amount */}
                  <td className="py-3.5 px-4 text-right whitespace-nowrap">
                    <span className="font-bold text-emerald-400 text-sm">
                      ${Number(item.amount).toFixed(2)}
                    </span>
                  </td>

                  {/* Action */}
                  <td className="py-3.5 px-4 text-center">
                    {onDelete && (
                      <button
                        onClick={() => onDelete(item.id)}
                        className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-950/30 transition-colors opacity-70 group-hover:opacity-100"
                        title="Delete spend"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
