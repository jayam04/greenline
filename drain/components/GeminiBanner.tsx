'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Zap, Sparkles, ArrowRight, X } from 'lucide-react';

export function GeminiBanner() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setConfigured(d.geminiConfigured))
      .catch(() => setConfigured(false));
  }, []);

  if (dismissed) {
    return null;
  }

  return (
    <div className="relative p-3 rounded-xl bg-gradient-to-r from-emerald-950/30 via-zinc-900 to-zinc-900 border border-emerald-500/20 text-xs text-zinc-300 flex items-center justify-between gap-3 shadow-sm">
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
          <Zap className="w-4 h-4" />
        </div>
        <div>
          <span className="font-semibold text-emerald-300 mr-1.5">
            ⚡ Instant Local Engine Active (&lt;5ms):
          </span>
          <span className="text-zinc-400">
            Running ultra-fast, offline in-memory classification.
            {configured
              ? ' Gemini 2.5 Flash is also connected for receipt OCR.'
              : ' Need multimodal bill OCR? Add GEMINI_API_KEY anytime in Settings.'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <Link
          href="/settings"
          className="flex items-center gap-1 font-semibold text-emerald-400 hover:text-emerald-300 hover:underline"
        >
          <span>Engine Settings</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded text-zinc-500 hover:text-zinc-300"
          aria-label="Dismiss banner"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
