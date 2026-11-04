'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Key, CheckCircle2, AlertTriangle, Database, RefreshCw } from 'lucide-react';

export default function SettingsPage() {
  const [geminiConfigured, setGeminiConfigured] = useState<boolean | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setGeminiConfigured(d.geminiConfigured))
      .catch(() => setGeminiConfigured(false));
  }, []);

  function handleRefresh() {
    setRefreshing(true);
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setGeminiConfigured(d.geminiConfigured))
      .catch(() => setGeminiConfigured(false))
      .finally(() => setRefreshing(false));
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Dashboard</span>
          </Link>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Settings & Integrations
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Manage AI models, API keys, and Greenline integration parameters.
        </p>
      </div>

      {/* Gemini API Status Card */}
      <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                <span>Google Gemini API Configuration</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                  gemini-3.8-flash
                </span>
              </h2>
              <p className="text-xs text-zinc-400">
                Powers pure English spend classification and multimodal receipt scanning.
              </p>
            </div>
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs flex items-center gap-1"
            title="Refresh status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/80">
          <div className="flex items-center gap-2 mb-2">
            {geminiConfigured ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-sm font-semibold text-emerald-400">
                  GEMINI_API_KEY is configured and active!
                </span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-sm font-semibold text-emerald-300">
                  ⚡ Instant Local NLP Engine is Active (&lt;5ms latency, offline & private)
                </span>
              </>
            )}
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            The Instant Local engine delivers sub-5 millisecond response times without external API calls or network roundtrips. To additionally enable Gemini 2.5 Flash for multimodal receipt & bill vision, add <code className="text-emerald-400 font-mono">GEMINI_API_KEY</code> to <code className="text-zinc-200 font-mono">drain/.env.local</code>:
          </p>
          <pre className="mt-2.5 p-3 rounded-lg bg-black text-[12px] text-zinc-300 font-mono overflow-x-auto border border-zinc-800">
            GEMINI_API_KEY=&quot;your_google_ai_studio_api_key_here&quot;
          </pre>
        </div>
      </div>

      {/* Dual Engine Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl bg-zinc-900/80 border border-emerald-500/20 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              ⚡ Instant Local Engine
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold uppercase">
              Ultra-Fast
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            In-memory deterministic NLP financial classifier running directly in Node.js runtime.
          </p>
          <div className="space-y-1.5 text-xs text-zinc-300 pt-2 border-t border-zinc-800">
            <div className="flex justify-between">
              <span className="text-zinc-500">Latency:</span>
              <span className="text-emerald-400 font-mono font-bold">&lt; 5 ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Privacy:</span>
              <span className="text-zinc-200">100% on-device / local</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Cost:</span>
              <span className="text-zinc-200">$0.00 / Zero API calls</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Offline support:</span>
              <span className="text-emerald-400 font-medium">Yes (Works without internet)</span>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              ✨ Gemini 2.5 Flash
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold uppercase">
              Multimodal Vision
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            Google DeepMind Gemini cloud model for deep semantic parsing and OCR scanning.
          </p>
          <div className="space-y-1.5 text-xs text-zinc-300 pt-2 border-t border-zinc-800">
            <div className="flex justify-between">
              <span className="text-zinc-500">Latency:</span>
              <span className="text-blue-400 font-mono font-medium">~400 - 800 ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Receipt / Bill OCR:</span>
              <span className="text-emerald-400 font-medium">Yes (Vision multimodal)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Complex sentence reasoning:</span>
              <span className="text-zinc-200">State of the art</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Setup:</span>
              <span className="text-zinc-400">{geminiConfigured ? 'Connected' : 'Requires API Key'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Greenline integration note */}
      <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-100">
              Greenline Sub-Application Architecture
            </h2>
            <p className="text-xs text-zinc-400">
              Ready for unified portfolio and cashflow synchronisation.
            </p>
          </div>
        </div>

        <div className="text-xs text-zinc-400 space-y-2 leading-relaxed">
          <p>
            • <strong>Data Storage</strong>: Stored persistently in <code className="text-zinc-300 font-mono">drain/data/spends.json</code>.
          </p>
          <p>
            • <strong>Budget Framework</strong>: Spends are classified according to the 50/30/20 rule (<span className="text-blue-400">Needs</span>, <span className="text-purple-400">Wants</span>, <span className="text-emerald-400">Savings</span>), directly matching Greenline’s <code className="text-zinc-300 font-mono">CashflowItem.label</code> schema.
          </p>
          <p>
            • <strong>REST API Endpoints</strong>: Available at <code className="text-zinc-300 font-mono">/api/spends</code> and <code className="text-zinc-300 font-mono">/api/spends/classify</code> for monorepo and microservice bridges.
          </p>
        </div>
      </div>
    </div>
  );
}
