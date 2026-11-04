'use client';

import React from 'react';
import { DollarSign, Layers, ShoppingBag, ArrowUpRight } from 'lucide-react';
import { SpendMetrics } from '@/lib/types';

interface MetricsCardsProps {
  metrics: SpendMetrics | null;
}

export function MetricsCards({ metrics }: MetricsCardsProps) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-pulse">
        {[1, 2, 3, 4].map(n => (
          <div key={n} className="h-28 rounded-xl bg-zinc-900 border border-zinc-800" />
        ))}
      </div>
    );
  }

  // Find top category
  let topCategory = 'None';
  let topCategoryAmount = 0;
  for (const [cat, amt] of Object.entries(metrics.byCategory || {})) {
    if (amt > topCategoryAmount) {
      topCategory = cat;
      topCategoryAmount = amt;
    }
  }

  const needsAmt = metrics.byBucket?.Needs || 0;
  const wantsAmt = metrics.byBucket?.Wants || 0;
  const savingsAmt = metrics.byBucket?.Savings || 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Spent */}
      <div className="p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800/80 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400">
          <span className="text-xs font-medium uppercase tracking-wider">Total Spends</span>
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
            <DollarSign className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold text-white tracking-tight">
            ${metrics.totalSpent.toFixed(2)}
          </span>
          <p className="text-xs text-zinc-500 mt-0.5">
            Across {metrics.transactionCount} tracked spends
          </p>
        </div>
      </div>

      {/* Needs vs Wants */}
      <div className="p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800/80 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400">
          <span className="text-xs font-medium uppercase tracking-wider">Needs vs. Wants</span>
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-blue-400 font-medium">Needs: {metrics.needsPercentage}% (${needsAmt.toFixed(0)})</span>
            <span className="text-purple-400 font-medium">Wants: {metrics.wantsPercentage}% (${wantsAmt.toFixed(0)})</span>
          </div>
          {/* Progress bar */}
          <div className="h-2 w-full rounded-full bg-zinc-800 overflow-hidden flex">
            <div
              style={{ width: `${metrics.needsPercentage}%` }}
              className="bg-blue-500 transition-all duration-500"
              title={`Needs: ${metrics.needsPercentage}%`}
            />
            <div
              style={{ width: `${metrics.wantsPercentage}%` }}
              className="bg-purple-500 transition-all duration-500"
              title={`Wants: ${metrics.wantsPercentage}%`}
            />
          </div>
        </div>
      </div>

      {/* Top Category */}
      <div className="p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800/80 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400">
          <span className="text-xs font-medium uppercase tracking-wider">Top Category</span>
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center">
            <ShoppingBag className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-base font-bold text-zinc-100 truncate block">
            {topCategory}
          </span>
          <p className="text-xs text-amber-400 font-medium mt-0.5">
            ${topCategoryAmount.toFixed(2)} spent
          </p>
        </div>
      </div>

      {/* Savings & Investments */}
      <div className="p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800/80 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400">
          <span className="text-xs font-medium uppercase tracking-wider">Savings / Retained</span>
          <div className="w-8 h-8 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20 flex items-center justify-center">
            <ArrowUpRight className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <span className="text-2xl font-bold text-teal-300 tracking-tight">
            ${savingsAmt.toFixed(2)}
          </span>
          <p className="text-xs text-zinc-500 mt-0.5">
            50/30/20 Wealth Builder
          </p>
        </div>
      </div>
    </div>
  );
}
