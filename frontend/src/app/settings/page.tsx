"use client";

import React, { useState, useEffect } from "react";
import { apiFetch, removeAuthToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { 
  Settings, User, Link as LinkIcon, ShieldCheck, 
  Coins, CheckCircle2, AlertCircle, LogOut, ArrowRight,
  HelpCircle, Sliders, Database, Check
} from "lucide-react";
import { SUPPORTED_CURRENCIES, CurrencyOption } from "@/lib/format";

export default function SettingsPage() {
  const router = useRouter();
  const [linkBrokerage, setLinkBrokerage] = useState(false);
  const [masterCurrency, setMasterCurrency] = useState("EUR");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const res = await apiFetch<{ link_brokerage_with_bank: boolean; master_currency: string }>("/settings");
      if (res) {
        if (typeof res.link_brokerage_with_bank === "boolean") {
          setLinkBrokerage(res.link_brokerage_with_bank);
          localStorage.setItem("greenline_link_brokerage_with_bank", String(res.link_brokerage_with_bank));
        }
        if (res.master_currency) {
          const curr = res.master_currency.trim().toUpperCase();
          setMasterCurrency(curr);
          localStorage.setItem("greenline_master_currency", curr);
        }
      }
    } catch (e) {
      console.error("Failed to load settings from server, using localStorage:", e);
      const localLink = localStorage.getItem("greenline_link_brokerage_with_bank") === "true";
      const localCurr = localStorage.getItem("greenline_master_currency") || "EUR";
      setLinkBrokerage(localLink);
      setMasterCurrency(localCurr);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleLinkBrokerage = async (newValue: boolean) => {
    setLinkBrokerage(newValue);
    localStorage.setItem("greenline_link_brokerage_with_bank", String(newValue));
    saveSettings({ link_brokerage_with_bank: newValue, master_currency: masterCurrency });
  };

  const handleChangeMasterCurrency = async (newCurrency: string) => {
    setMasterCurrency(newCurrency);
    localStorage.setItem("greenline_master_currency", newCurrency);
    saveSettings({ link_brokerage_with_bank: linkBrokerage, master_currency: newCurrency });
  };

  const saveSettings = async (payload: { link_brokerage_with_bank: boolean; master_currency: string }) => {
    setSaving(true);
    setSavedMessage("");

    try {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setSavedMessage("Settings saved successfully!");
      setTimeout(() => setSavedMessage(""), 3500);
    } catch (e) {
      console.error("Failed to persist settings to server:", e);
      setSavedMessage("Updated locally in session.");
      setTimeout(() => setSavedMessage(""), 3500);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    router.push("/login");
  };

  const selectedCurrencyObj = SUPPORTED_CURRENCIES.find((c) => c.code === masterCurrency) || SUPPORTED_CURRENCIES[0];

  return (
    <div className="max-w-[1200px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-700" />
            <span>Settings & Preferences</span>
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Manage application integration rules, master currency selection, and display behaviors
          </p>
        </div>

        {savedMessage && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-xl border border-emerald-200 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{savedMessage}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
        {/* Left 2 Cols: Main Configuration Cards */}
        <div className="md:col-span-2 space-y-5">
          {/* Card 1: Master Currency Selection */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-emerald-50 text-emerald-600 rounded-xl">
                  <Coins className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A]">
                    Master Portfolio Currency
                  </h2>
                  <p className="text-[11px] font-medium text-slate-400">
                    Base currency used for portfolio net worth, KPI summaries, and cashflow charts
                  </p>
                </div>
              </div>

              <div className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-[#0F172A]">
                Active: {selectedCurrencyObj.symbol} {selectedCurrencyObj.code}
              </div>
            </div>

            {/* Currency Grid Picker */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {SUPPORTED_CURRENCIES.map((curr) => {
                const isSelected = curr.code === masterCurrency;
                return (
                  <button
                    key={curr.code}
                    type="button"
                    onClick={() => handleChangeMasterCurrency(curr.code)}
                    disabled={loading || saving}
                    className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                      isSelected
                        ? "border-[#0F172A] bg-slate-50/80 shadow-xs"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-1.5 font-bold text-xs text-[#0F172A]">
                        <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-[11px]">
                          {curr.symbol}
                        </span>
                        <span>{curr.code}</span>
                      </div>
                      <div className="text-[10px] font-semibold text-slate-400 mt-0.5">
                        {curr.country}
                      </div>
                    </div>

                    {isSelected && (
                      <div className="w-5 h-5 rounded-full bg-[#0F172A] text-white flex items-center justify-center">
                        <Check className="w-3 h-3" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 2: Account & Cashflow Integration Rules */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
              <div className="p-2 bg-blue-50 text-blue-600 rounded-xl">
                <LinkIcon className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#0F172A]">
                  Account & Cashflow Integration Rules
                </h2>
                <p className="text-[11px] font-medium text-slate-400">
                  Control how funding transfers between bank accounts and brokerage accounts are categorized
                </p>
              </div>
            </div>

            {/* Integration Setting Item */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1 max-w-xl">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-[#0F172A]">
                    Link Brokerage/Demat accounts with Bank Accounts
                  </span>
                  <span className={`px-2 py-0.2 text-[9px] font-extrabold uppercase rounded ${
                    linkBrokerage ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"
                  }`}>
                    {linkBrokerage ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <p className="text-[11px] font-semibold text-slate-500 leading-relaxed">
                  {linkBrokerage ? (
                    <span>
                      <strong className="text-slate-800">Linked:</strong> Transfers between bank and brokerage accounts are treated as internal account balance movements. Investments will <strong className="text-slate-800">not</strong> appear in the <code className="bg-white px-1 py-0.5 rounded border border-slate-200 text-[10px]">/cashflow</code> Sankey chart.
                    </span>
                  ) : (
                    <span>
                      <strong className="text-slate-800">Unlinked:</strong> Investments and savings allocations will appear as distinct outflows in the <code className="bg-white px-1 py-0.5 rounded border border-slate-200 text-[10px]">/cashflow</code> Sankey chart.
                    </span>
                  )}
                </p>
              </div>

              {/* Toggle Switch */}
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={linkBrokerage}
                  onChange={(e) => handleToggleLinkBrokerage(e.target.checked)}
                  disabled={loading || saving}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#0F172A]"></div>
              </label>
            </div>
          </div>
        </div>

        {/* Right 1 Col: User & Session Info Card */}
        <div className="space-y-4">
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
              <div className="p-2 bg-slate-100 text-slate-700 rounded-xl">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">Current Profile</h3>
                <p className="text-[11px] font-medium text-slate-400">Authenticated account</p>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Username</span>
                <span className="font-bold text-[#0F172A]">admin</span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Role</span>
                <span className="px-2 py-0.5 bg-slate-100 text-slate-700 font-extrabold text-[10px] rounded uppercase">
                  Administrator
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Master Currency</span>
                <span className="font-bold text-emerald-700">
                  {selectedCurrencyObj.symbol} {selectedCurrencyObj.code}
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Session Security</span>
                <span className="text-emerald-600 font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Active JWT
                </span>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="w-full mt-2 py-2 px-3 text-xs font-bold text-rose-600 hover:bg-rose-50 border border-rose-200 rounded-xl transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Log out of Greenline</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
