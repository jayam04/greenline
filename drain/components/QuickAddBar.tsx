'use client';

import React, { useState } from 'react';
import { Sparkles, ArrowRight, CheckCircle2, AlertCircle, Zap } from 'lucide-react';
import { SpendItem, SpendClassification } from '@/lib/types';

interface QuickAddBarProps {
  onSpendAdded?: (item: SpendItem) => void;
}

const PRESET_EXAMPLES = [
  'bought coffee for $4',
  'Trader Joe groceries for $48.20',
  'Uber ride to airport $34.50',
  'Electric utility bill $82.00',
];

export function QuickAddBar({ onSpendAdded }: QuickAddBarProps) {
  const [text, setText] = useState('');
  const [engine, setEngine] = useState<'local' | 'auto'>('local');
  const [loading, setLoading] = useState(false);
  const [lastAdded, setLastAdded] = useState<{
    classification: SpendClassification;
    item: SpendItem;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(spendText: string) {
    const query = spendText.trim();
    if (!query || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/spends/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: query,
          autoSave: true,
          engine: engine,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Classification failed');
      }

      const data = await res.json();
      setLastAdded({
        classification: data.classification,
        item: data.item,
      });
      setText('');

      if (onSpendAdded && data.item) {
        onSpendAdded(data.item);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to classify spend';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full space-y-3">
      {/* Engine Selector Pill */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-zinc-900 border border-zinc-800 text-xs">
          <button
            type="button"
            onClick={() => setEngine('local')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium transition-all ${
              engine === 'local'
                ? 'bg-emerald-500 text-zinc-950 font-semibold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Instant Local</span>
            <span className={`text-[10px] px-1 py-0.2 rounded font-mono ${
              engine === 'local' ? 'bg-emerald-600 text-white' : 'bg-zinc-800 text-emerald-400'
            }`}>
              &lt;5ms
            </span>
          </button>

          <button
            type="button"
            onClick={() => setEngine('auto')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium transition-all ${
              engine === 'auto'
                ? 'bg-emerald-500 text-zinc-950 font-semibold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Gemini Flash</span>
            <span className={`text-[10px] px-1 py-0.2 rounded font-mono ${
              engine === 'auto' ? 'bg-emerald-600 text-white' : 'bg-zinc-800 text-zinc-400'
            }`}>
              AI
            </span>
          </button>
        </div>

        <span className="text-[11px] text-zinc-500">
          {engine === 'local'
            ? '⚡ Instant in-memory NLP (zero latency, zero cost)'
            : '✨ Cloud Gemini 2.5 Flash for nuanced semantics'}
        </span>
      </div>

      {/* Input container */}
      <div className="relative flex items-center bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg shadow-black/20 focus-within:border-emerald-500/60 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all p-1.5">
        <div className="pl-3.5 pr-2 text-emerald-400">
          {engine === 'local' ? (
            <Zap className="w-5 h-5 text-emerald-400" />
          ) : (
            <Sparkles className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          )}
        </div>
        <input
          type="text"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSubmit(text);
            }
          }}
          disabled={loading}
          placeholder='Describe your spend in pure English (e.g. "bought coffee for $4")...'
          className="flex-1 bg-transparent px-2 py-3 text-sm md:text-base text-zinc-100 placeholder-zinc-500 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={() => handleSubmit(text)}
          disabled={!text.trim() || loading}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold text-sm transition-all disabled:opacity-30 disabled:pointer-events-none shadow-sm shadow-emerald-500/20"
        >
          {loading ? (
            <span>Classifying...</span>
          ) : (
            <>
              <span>Add Spend</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>

      {/* Suggested chips */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-zinc-500 font-medium">Try asking:</span>
        {PRESET_EXAMPLES.map((example, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => {
              setText(example);
              handleSubmit(example);
            }}
            disabled={loading}
            className="px-2.5 py-1 rounded-full bg-zinc-900/90 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 transition-colors cursor-pointer"
          >
            &ldquo;{example}&rdquo;
          </button>
        ))}
      </div>

      {/* Error notification */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Success classification confirmation banner */}
      {lastAdded && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 via-zinc-900/90 to-zinc-900 border border-emerald-500/30 text-zinc-200 text-sm shadow-md animate-in fade-in duration-300">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 font-medium text-emerald-400">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>Added to Spends:</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-300 font-mono text-[11px] border border-zinc-700">
                {lastAdded.classification.engineUsed === 'local' ? '⚡ Instant Local' : '✨ Gemini Flash'}
                {lastAdded.classification.latencyMs ? ` (${lastAdded.classification.latencyMs}ms)` : ''}
              </span>
            </div>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-md bg-zinc-800 font-medium text-zinc-100 border border-zinc-700/60">
              🏪 {lastAdded.classification.merchant}
            </span>
            <span className="px-2.5 py-1 rounded-md bg-zinc-800 font-medium text-zinc-100 border border-zinc-700/60">
              ☕ {lastAdded.classification.item}
            </span>
            <span className="px-2.5 py-1 rounded-md bg-zinc-800/80 text-zinc-300 border border-zinc-700/40">
              📅 {lastAdded.classification.formattedDate}
            </span>
            <span className={`px-2.5 py-1 rounded-md font-semibold border ${
              lastAdded.classification.type === 'Wants'
                ? 'bg-purple-950/40 text-purple-300 border-purple-800/50'
                : lastAdded.classification.type === 'Needs'
                ? 'bg-blue-950/40 text-blue-300 border-blue-800/50'
                : 'bg-emerald-950/40 text-emerald-300 border-emerald-800/50'
            }`}>
              {lastAdded.classification.type}
            </span>
            <span className="px-2.5 py-1 rounded-md bg-zinc-800/80 text-zinc-300 border border-zinc-700/40">
              🏷️ {lastAdded.classification.category}
            </span>
            <span className="ml-auto font-bold text-emerald-400 text-sm">
              ${lastAdded.classification.amount.toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
