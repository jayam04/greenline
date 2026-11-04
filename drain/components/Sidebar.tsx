'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Receipt,
  FileUp,
  Settings,
  Sparkles,
  ChevronRight,
  Menu,
  X,
  CreditCard,
} from 'lucide-react';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/spends', label: 'Spends Ledger', icon: Receipt },
  { href: '/upload', label: 'Upload Bills', icon: FileUp },
  { href: '/settings', label: 'Settings & Key', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [geminiStatus, setGeminiStatus] = useState<boolean | null>(null);

  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setGeminiStatus(d.geminiConfigured))
      .catch(() => setGeminiStatus(false));
  }, []);

  return (
    <>
      {/* Mobile hamburger header */}
      <div className="lg:hidden flex items-center justify-between px-4 py-3 bg-zinc-950 text-white border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold">
            <CreditCard className="w-4 h-4" />
          </div>
          <span className="font-semibold text-lg tracking-tight">Drain</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-2 rounded-md hover:bg-zinc-800 text-zinc-300"
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Sidebar container */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-40
          w-64 bg-zinc-950 text-zinc-200 border-r border-zinc-800 flex flex-col justify-between
          transition-transform duration-200 ease-in-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="flex flex-col">
          {/* Brand header */}
          <div className="p-6 border-b border-zinc-800/80">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 text-white flex items-center justify-center shadow-md shadow-emerald-950/40 group-hover:scale-105 transition-transform">
                <CreditCard className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
                  Drain
                  <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                    AI
                  </span>
                </span>
                <span className="text-xs text-zinc-400 font-normal">Spend Tracker for Greenline</span>
              </div>
            </Link>
          </div>

          {/* Navigation links */}
          <nav className="p-4 space-y-1.5">
            {NAV_ITEMS.map(item => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`
                    flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors
                    ${
                      active
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900'
                    }
                  `}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${active ? 'text-emerald-400' : 'text-zinc-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {active && <ChevronRight className="w-4 h-4 text-emerald-400" />}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Engine status footer */}
        <div className="p-4 border-t border-zinc-800/80">
          <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-zinc-300 flex items-center gap-1.5 font-medium">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                Classification Engine
              </span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            </div>
            <p className="text-[11px] text-zinc-400">
              {geminiStatus === true
                ? '⚡ Instant Local + ✨ Gemini 2.5 Active'
                : '⚡ Instant Local Active (<5ms ultra-fast)'}
            </p>
          </div>
        </div>
      </aside>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 bg-black/60 z-30 lg:hidden"
        />
      )}
    </>
  );
}
