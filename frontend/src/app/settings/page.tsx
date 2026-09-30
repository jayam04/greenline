"use client";

import React, { useState, useEffect } from "react";
import { apiFetch, removeAuthToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { 
  Settings, User, ShieldCheck, 
  Coins, CheckCircle2, AlertCircle, LogOut, ArrowRight,
  HelpCircle, Sliders, Database, Check, Calendar, Download,
  RefreshCw, Trash2, RotateCcw, Clock, HardDrive, FileJson, AlertTriangle,
  Key, Copy, Type
} from "lucide-react";
import { SUPPORTED_CURRENCIES, CurrencyOption } from "@/lib/format";
import { useFont, AppFont, FONT_STORAGE_KEY } from "@/components/FontProvider";

const FONT_PRESETS = [
  {
    id: "general-sans" as const,
    label: "General Sans",
    tag: "Default",
    description: "Modern geometric sans-serif with distinct character and punchy numbers",
    preview: "The quick brown fox jumps over 134.50 EUR",
    fontFamily: "var(--font-general-sans)",
  },
  {
    id: "inter" as const,
    label: "Inter",
    tag: "Clean UI",
    description: "Precision neo-grotesque typeface optimized for high-density screen legibility",
    preview: "The quick brown fox jumps over 134.50 EUR",
    fontFamily: "var(--font-inter)",
  },
  {
    id: "rx100" as const,
    label: "RX100",
    tag: "Ledger",
    description: "Crisp monospace font perfect for financial ledgers and statements",
    preview: "The quick brown fox jumps over 134.50 EUR",
    fontFamily: "var(--font-rx100)",
  },
];

const FISCAL_YEAR_PRESETS = [
  { label: "January 1st (Calendar Year)", value: "01-01", description: "Standard calendar year (Global/US)" },
  { label: "April 1st (Fiscal Year)", value: "04-01", description: "Standard fiscal year (India, UK, Canada, Japan)" },
  { label: "July 1st (Fiscal Year)", value: "07-01", description: "Mid-year fiscal cycle (Australia, Egypt)" },
  { label: "October 1st (Federal Fiscal Year)", value: "10-01", description: "Q4 fiscal cycle (US Federal, Thailand)" },
];

const INTERVAL_PRESETS = [
  { label: "Every 6 Hours", value: 6 },
  { label: "Every 12 Hours", value: 12 },
  { label: "Daily (24 Hours)", value: 24 },
  { label: "Every 2 Days (48 Hours)", value: 48 },
  { label: "Weekly (7 Days)", value: 168 },
];

const RETENTION_PRESETS = [
  { label: "Keep Last 5 Backups", value: 5 },
  { label: "Keep Last 10 Backups", value: 10 },
  { label: "Keep Last 20 Backups", value: 20 },
  { label: "Keep Last 50 Backups", value: 50 },
];

interface BackupConfig {
  database_file: string;
  data_dir: string;
  active_db_path: string;
  autobackup_enabled: boolean;
  autobackup_interval_hours: number;
  autobackup_max_copies: number;
  last_backup_timestamp: string | null;
  next_backup_timestamp: string | null;
  is_overdue: boolean;
  total_backups_count: number;
}

interface BackupItem {
  filename: string;
  filepath: string;
  size_bytes: number;
  size_formatted: string;
  created_at: string;
  kind: string;
  note?: string | null;
}

interface ApiKeyItem {
  key_id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
}

export default function SettingsPage() {
  const router = useRouter();
  const { font, setFont } = useFont();
  const [masterCurrency, setMasterCurrency] = useState("EUR");
  const [fiscalYearStart, setFiscalYearStart] = useState("01-01");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  // MCP API Keys State
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false);
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);

  // Backup State
  const [backupConfig, setBackupConfig] = useState<BackupConfig | null>(null);
  const [backupsList, setBackupsList] = useState<BackupItem[]>([]);
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [restoringFile, setRestoringFile] = useState<string | null>(null);
  const [restoreConfirmFile, setRestoreConfirmFile] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Settings · greenline";
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const [res, bConfig, bList] = await Promise.all([
        apiFetch<{ 
          master_currency: string;
          fiscal_year_start?: string;
          app_font?: string;
        }>("/settings"),
        apiFetch<BackupConfig>("/backup/config").catch(() => null),
        apiFetch<{ total_count: number; backups: BackupItem[] }>("/backup/list").catch(() => ({ total_count: 0, backups: [] }))
      ]);
      
      if (res) {
        if (res.master_currency) {
          const curr = res.master_currency.trim().toUpperCase();
          setMasterCurrency(curr);
          localStorage.setItem("greenline_master_currency", curr);
        }
        if (res.fiscal_year_start) {
          const fy = res.fiscal_year_start.trim();
          setFiscalYearStart(fy);
          localStorage.setItem("greenline_fiscal_year_start", fy);
        }
        if (res.app_font) {
          const raw = res.app_font.trim().toLowerCase();
          const normFont: AppFont = raw === "inter" ? "inter" : raw === "rx100" ? "rx100" : "general-sans";
          setFont(normFont);
        }
      }

      if (bConfig) setBackupConfig(bConfig);
      if (bList) setBackupsList(bList.backups || []);
      loadApiKeys();
    } catch (e) {
      console.error("Failed to load settings from server, using localStorage:", e);
      const localCurr = localStorage.getItem("greenline_master_currency") || "EUR";
      const localFy = localStorage.getItem("greenline_fiscal_year_start") || "01-01";
      const localFont = (localStorage.getItem(FONT_STORAGE_KEY) || "general-sans") as AppFont;
      setMasterCurrency(localCurr);
      setFiscalYearStart(localFy);
      setFont(localFont);
    } finally {
      setLoading(false);
    }
  };

  const loadApiKeys = async () => {
    try {
      const keys = await apiFetch<ApiKeyItem[]>("/auth/api-keys");
      if (keys && Array.isArray(keys)) setApiKeys(keys);
      else setApiKeys([]);
    } catch (e) {
      console.error("Failed to load API keys:", e);
      setApiKeys([]);
    }
  };

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    try {
      setCreatingKey(true);
      const res = await apiFetch<{ key: string } & ApiKeyItem>("/auth/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: newKeyName.trim() })
      });
      setCreatedRawKey(res.key);
      setNewKeyName("");
      loadApiKeys();
    } catch (err: any) {
      alert(err.message || "Failed to create API key");
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (keyId: number, name: string) => {
    if (!confirm(`Are you sure you want to revoke API key '${name}'? Any AI agent using this key will immediately lose access.`)) return;
    try {
      await apiFetch(`/auth/api-keys/${keyId}`, { method: "DELETE" });
      setApiKeys(prev => prev.filter(k => k.key_id !== keyId));
      setSavedMessage("API key revoked.");
      setTimeout(() => setSavedMessage(""), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to revoke API key");
    }
  };

  const handleCopyKey = () => {
    if (!createdRawKey) return;
    navigator.clipboard.writeText(createdRawKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2500);
  };

  const handleChangeFont = async (newFont: AppFont) => {
    setFont(newFont);
    saveSettings({ master_currency: masterCurrency, fiscal_year_start: fiscalYearStart, app_font: newFont });
  };

  const handleChangeMasterCurrency = async (newCurrency: string) => {
    setMasterCurrency(newCurrency);
    localStorage.setItem("greenline_master_currency", newCurrency);
    saveSettings({ master_currency: newCurrency, fiscal_year_start: fiscalYearStart, app_font: font });
  };

  const handleChangeFiscalYearStart = async (newFy: string) => {
    setFiscalYearStart(newFy);
    localStorage.setItem("greenline_fiscal_year_start", newFy);
    saveSettings({ master_currency: masterCurrency, fiscal_year_start: newFy, app_font: font });
  };

  const saveSettings = async (payload: { master_currency: string; fiscal_year_start: string; app_font?: string }) => {
    setSaving(true);
    setSavedMessage("");

    try {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({
          ...payload,
          app_font: payload.app_font || font,
        }),
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

  // Backup Handlers
  const handleUpdateBackupConfig = async (payload: {
    autobackup_enabled?: boolean;
    autobackup_interval_hours?: number;
    autobackup_max_copies?: number;
  }) => {
    try {
      setSaving(true);
      const updated = await apiFetch<BackupConfig>("/backup/config", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (updated) setBackupConfig(updated);
      setSavedMessage("Backup settings updated!");
      setTimeout(() => setSavedMessage(""), 3500);
    } catch (err: any) {
      alert(err.message || "Failed to update backup settings");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateManualBackup = async () => {
    try {
      setCreatingBackup(true);
      await apiFetch("/backup/create", {
        method: "POST",
        body: JSON.stringify({ note: "Manual Snapshot" }),
      });
      // Refresh list and config
      const [bConfig, bList] = await Promise.all([
        apiFetch<BackupConfig>("/backup/config"),
        apiFetch<{ total_count: number; backups: BackupItem[] }>("/backup/list"),
      ]);
      if (bConfig) setBackupConfig(bConfig);
      if (bList) setBackupsList(bList.backups || []);
      setSavedMessage("Manual backup snapshot created successfully!");
      setTimeout(() => setSavedMessage(""), 3500);
    } catch (err: any) {
      alert(err.message || "Failed to create backup snapshot");
    } finally {
      setCreatingBackup(false);
    }
  };

  const handleDownloadBackup = (filename: string) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.open(`${apiBase}/api/v1/backup/download/${filename}`, "_blank");
  };

  const handleExportFullJSON = () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.open(`${apiBase}/api/v1/backup/export`, "_blank");
  };

  const handleConfirmRestore = async () => {
    if (!restoreConfirmFile) return;
    try {
      setRestoringFile(restoreConfirmFile);
      await apiFetch(`/backup/restore/${restoreConfirmFile}`, { method: "POST" });
      setRestoreConfirmFile(null);
      setSavedMessage(`Database successfully restored from ${restoreConfirmFile}!`);
      setTimeout(() => setSavedMessage(""), 4000);
      loadSettings();
    } catch (err: any) {
      alert(err.message || "Failed to restore database from backup");
    } finally {
      setRestoringFile(null);
    }
  };

  const handleDeleteBackup = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete backup '${filename}'?`)) return;
    try {
      await apiFetch(`/backup/${filename}`, { method: "DELETE" });
      setBackupsList((prev) => prev.filter((b) => b.filename !== filename));
      setSavedMessage("Backup deleted.");
      setTimeout(() => setSavedMessage(""), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to delete backup");
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    router.push("/login");
  };

  const selectedCurrencyObj = SUPPORTED_CURRENCIES.find((c) => c.code === masterCurrency) || SUPPORTED_CURRENCIES[0];
  const activeFiscalPreset = FISCAL_YEAR_PRESETS.find((p) => p.value === fiscalYearStart) || FISCAL_YEAR_PRESETS[0];

  return (
    <div className="max-w-[1200px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0F172A] dark:text-white tracking-tight">System Settings</h1>
            <span className="px-2 py-0.5 text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-full">
              Configuration
            </span>
          </div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
            Configure reporting currency, financial year cycles, and automated database backups
          </p>
        </div>

        {savedMessage && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 text-xs font-bold rounded-xl animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>{savedMessage}</span>
          </div>
        )}
      </div>

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Preferences & Backup Hub */}
        <div className="lg:col-span-2 space-y-6">
          {/* Card 1: Master Valuation Currency */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 rounded-xl">
                  <Coins className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                    Master Reporting Currency
                  </h2>
                  <p className="text-[11px] font-medium text-slate-400">
                    Primary denominator used for portfolio aggregation and net worth calculations
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1">
              {SUPPORTED_CURRENCIES.map((curr) => {
                const isSelected = masterCurrency === curr.code;
                return (
                  <button
                    key={curr.code}
                    onClick={() => handleChangeMasterCurrency(curr.code)}
                    disabled={loading || saving}
                    className={`p-3 rounded-xl border text-left transition-all flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10 font-bold"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-[#151D2B]"
                    }`}
                  >
                    <div>
                      <div className="text-xs font-bold text-[#0F172A] dark:text-white flex items-center gap-1.5">
                        <span className="text-sm">{curr.symbol}</span>
                        <span>{curr.code}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 truncate max-w-[110px]">
                        {curr.label}
                      </div>
                    </div>
                    {isSelected && (
                      <div className="w-4 h-4 rounded-full bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 2: Financial Year Baseline */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="p-2 bg-purple-50 dark:bg-purple-950/40 text-purple-600 rounded-xl">
                <Calendar className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                  Annual Breakdown Baseline
                </h2>
                <p className="text-[11px] font-medium text-slate-400">
                  Fiscal year cycle start date for annual snapshots and performance reporting
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {FISCAL_YEAR_PRESETS.map((preset) => {
                const isSelected = fiscalYearStart === preset.value;
                return (
                  <button
                    key={preset.value}
                    onClick={() => handleChangeFiscalYearStart(preset.value)}
                    disabled={loading || saving}
                    className={`p-3 rounded-xl border text-left transition-all flex items-start justify-between cursor-pointer ${
                      isSelected
                        ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-[#151D2B]"
                    }`}
                  >
                    <div className="space-y-0.5">
                      <div className="text-xs font-bold text-[#0F172A] dark:text-white">
                        {preset.label}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {preset.description}
                      </div>
                    </div>
                    {isSelected && (
                      <div className="w-4 h-4 rounded-full bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] flex items-center justify-center shrink-0 ml-2 mt-0.5">
                        <Check className="w-2.5 h-2.5" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 3: Interface Typography */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="p-2 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 rounded-xl">
                <Type className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                  Interface Typography
                </h2>
                <p className="text-[11px] font-medium text-slate-400">
                  Select between the default geometric font (General Sans), high-density screen font (Inter), or a crisp monospace font (RX100)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {FONT_PRESETS.map((preset) => {
                const isSelected = font === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handleChangeFont(preset.id)}
                    disabled={loading || saving}
                    className={`p-3.5 rounded-xl border text-left transition-all flex flex-col justify-between cursor-pointer space-y-2.5 ${
                      isSelected
                        ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-[#151D2B]"
                    }`}
                  >
                    <div className="flex items-start justify-between w-full">
                      <div className="flex items-center gap-2">
                        <span
                          className="text-xs font-bold text-[#0F172A] dark:text-white"
                          style={{ fontFamily: preset.fontFamily }}
                        >
                          {preset.label}
                        </span>
                        <span className="px-1.5 py-0.5 text-[9px] font-extrabold uppercase rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                          {preset.tag}
                        </span>
                      </div>
                      {isSelected && (
                        <div className="w-4 h-4 rounded-full bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] flex items-center justify-center shrink-0">
                          <Check className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>

                    <div className="text-[10px] text-slate-500 dark:text-slate-400 leading-snug">
                      {preset.description}
                    </div>

                    <div
                      className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-700 dark:text-slate-300 truncate"
                      style={{ fontFamily: preset.fontFamily }}
                    >
                      {preset.preview}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 4: MCP & AI Agent API Keys */}
          <div className="getquin-card p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-amber-50 dark:bg-amber-950/40 text-amber-600 rounded-xl">
                  <Key className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                    MCP & AI Agent API Keys
                  </h2>
                  <p className="text-[11px] font-medium text-slate-400">
                    Create permanent API keys for ChatGPT Actions, Claude, and Greenline MCP servers
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => { setShowCreateKeyModal(true); setCreatedRawKey(null); }}
                className="btn-pill-black text-xs px-3 py-1.5 cursor-pointer flex items-center gap-1.5 self-start sm:self-auto"
              >
                <Key className="w-3.5 h-3.5" />
                <span>+ Create API Key</span>
              </button>
            </div>

            {/* List of Keys */}
            {apiKeys.length === 0 ? (
              <div className="py-6 text-center text-slate-400 dark:text-slate-500 text-xs">
                No active API keys yet. Click <strong className="text-slate-600 dark:text-slate-300">Create API Key</strong> to connect ChatGPT or MCP.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden text-xs">
                {apiKeys.map((k) => (
                  <div key={k.key_id} className="p-3 bg-white dark:bg-[#151D2B] flex items-center justify-between gap-4">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[#0F172A] dark:text-white">{k.name}</span>
                        <span className="font-mono text-[10px] px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded">
                          {k.key_prefix}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-2">
                        <span>Created: {new Date(k.created_at).toLocaleDateString()}</span>
                        {k.last_used_at && (
                          <span>• Last used: {new Date(k.last_used_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRevokeKey(k.key_id, k.name)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                      title="Revoke this API Key"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Card 4: Database & Auto-Backup Management */}
          <div className="getquin-card p-5 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-50 dark:bg-blue-950/40 text-blue-600 rounded-xl">
                  <Database className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                    Database & Auto-Backup Management
                  </h2>
                  <p className="text-[11px] font-medium text-slate-400">
                    Automated snapshots, retention policies, and database restore
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCreateManualBackup}
                  disabled={creatingBackup}
                  className="btn-pill-black text-xs cursor-pointer flex items-center gap-1.5 whitespace-nowrap"
                  title="Create an instant snapshot of the active database"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${creatingBackup ? "animate-spin" : ""}`} />
                  <span>{creatingBackup ? "Backing up..." : "Backup Now"}</span>
                </button>

                <button
                  onClick={handleExportFullJSON}
                  className="px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
                  title="Export entire system state as JSON"
                >
                  <FileJson className="w-3.5 h-3.5" />
                  <span>Export JSON</span>
                </button>
              </div>
            </div>

            {/* Active Database Info */}
            {backupConfig && (
              <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200/70 dark:border-slate-700/60 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-[10px] font-bold uppercase text-slate-400">Active Database</div>
                  <div className="font-bold text-[#0F172A] dark:text-white mt-0.5 flex items-center gap-1.5">
                    <HardDrive className="w-3.5 h-3.5 text-blue-500" />
                    <span>{backupConfig.database_file}</span>
                  </div>
                </div>

                <div>
                  <div className="text-[10px] font-bold uppercase text-slate-400">Storage Directory</div>
                  <div className="font-semibold text-slate-600 dark:text-slate-300 mt-0.5 truncate" title={backupConfig.active_db_path}>
                    {backupConfig.data_dir}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] font-bold uppercase text-slate-400">Last Backup</div>
                  <div className="font-semibold text-slate-700 dark:text-slate-300 mt-0.5">
                    {backupConfig.last_backup_timestamp 
                      ? new Date(backupConfig.last_backup_timestamp).toLocaleString()
                      : "No backup yet"}
                  </div>
                </div>
              </div>
            )}

            {/* Auto-Backup Controls */}
            {backupConfig && (
              <div className="space-y-4 pt-1">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#151D2B]">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#0F172A] dark:text-white">
                        Automated Database Backups
                      </span>
                      <span className={`px-2 py-0.2 text-[9px] font-extrabold uppercase rounded ${
                        backupConfig.autobackup_enabled 
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" 
                          : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-400"
                      }`}>
                        {backupConfig.autobackup_enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <p className="text-[11px] font-medium text-slate-400">
                      Creates timestamped SQLite snapshots and purges old files automatically
                    </p>
                  </div>

                  <label className="relative inline-flex items-center cursor-pointer shrink-0">
                    <input
                      type="checkbox"
                      checked={backupConfig.autobackup_enabled}
                      onChange={(e) => handleUpdateBackupConfig({ autobackup_enabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-200 dark:bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#0F172A] dark:peer-checked:bg-white dark:peer-checked:after:border-slate-800 dark:peer-checked:after:bg-[#0F172A]"></div>
                  </label>
                </div>

                {/* Interval & Retention Selectors */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Backup Interval
                    </label>
                    <select
                      value={backupConfig.autobackup_interval_hours}
                      onChange={(e) => handleUpdateBackupConfig({ autobackup_interval_hours: Number(e.target.value) })}
                      disabled={!backupConfig.autobackup_enabled}
                      className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none disabled:opacity-50"
                    >
                      {INTERVAL_PRESETS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Retention Policy
                    </label>
                    <select
                      value={backupConfig.autobackup_max_copies}
                      onChange={(e) => handleUpdateBackupConfig({ autobackup_max_copies: Number(e.target.value) })}
                      disabled={!backupConfig.autobackup_enabled}
                      className="w-full bg-[#F8F9FA] dark:bg-[#1A2333] text-slate-900 dark:text-slate-100 font-semibold rounded-xl px-3 py-2 border border-slate-200 dark:border-slate-700 text-xs focus:outline-none disabled:opacity-50"
                    >
                      {RETENTION_PRESETS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Backups Table */}
            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white uppercase tracking-wider">
                  Stored Snapshots ({backupsList.length})
                </h3>
              </div>

              {backupsList.length > 0 ? (
                <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-400 font-bold uppercase text-[10px]">
                        <th className="py-2.5 px-3">Filename</th>
                        <th className="py-2.5 px-3">Date & Time</th>
                        <th className="py-2.5 px-3 text-right">Size</th>
                        <th className="py-2.5 px-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {backupsList.map((b) => (
                        <tr key={b.filename} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors">
                          <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-[11px]">{b.filename}</span>
                              {b.kind === "auto" && (
                                <span className="px-1.5 py-0.2 text-[9px] font-bold bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 rounded">
                                  Auto
                                </span>
                              )}
                              {b.kind === "safety" && (
                                <span className="px-1.5 py-0.2 text-[9px] font-bold bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 rounded">
                                  Pre-Restore
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400 whitespace-nowrap text-[11px]">
                            {new Date(b.created_at).toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3 text-right font-medium text-slate-600 dark:text-slate-400 text-[11px] whitespace-nowrap">
                            {b.size_formatted}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleDownloadBackup(b.filename)}
                                className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded transition-colors"
                                title="Download backup file"
                              >
                                <Download className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setRestoreConfirmFile(b.filename)}
                                className="p-1 text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 rounded transition-colors"
                                title="Restore active database from this snapshot"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteBackup(b.filename)}
                                className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                                title="Delete backup"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl text-slate-400 text-xs">
                  No backups stored yet. Click "Backup Now" to create your first snapshot.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right 1 Col: User & Session Info Card */}
        <div className="space-y-4">
          <div className="getquin-card p-5 space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="p-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0F172A] dark:text-white">Current Profile</h3>
                <p className="text-[11px] font-medium text-slate-400">Authenticated account</p>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">Username</span>
                <span className="font-bold text-[#0F172A] dark:text-white">admin</span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">Role</span>
                <span className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-extrabold text-[10px] rounded uppercase">
                  Administrator
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">Master Currency</span>
                <span className="font-bold text-emerald-700 dark:text-emerald-400">
                  {selectedCurrencyObj.symbol} {selectedCurrencyObj.code}
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">Year Baseline</span>
                <span className="font-bold text-purple-700 dark:text-purple-400">
                  {activeFiscalPreset.value} ({activeFiscalPreset.label.split(" (")[0]})
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">Interface Font</span>
                <span className="font-bold text-indigo-700 dark:text-indigo-400">
                  {font === "inter" ? "Inter" : "General Sans"}
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-500">MCP Auth</span>
                <span className="text-amber-600 dark:text-amber-400 font-bold flex items-center gap-1">
                  <Key className="w-3.5 h-3.5" /> {apiKeys.length} Active Key{apiKeys.length === 1 ? "" : "s"}
                </span>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="w-full mt-2 py-2 px-3 text-xs font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Log out of Greenline</span>
            </button>
          </div>
        </div>
      </div>

      {/* Create / Reveal API Key Modal */}
      {showCreateKeyModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#151D2B] rounded-2xl max-w-md w-full p-6 space-y-4 border border-slate-200 dark:border-slate-800 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 rounded-full">
                <Key className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[#0F172A] dark:text-white">
                  {createdRawKey ? "API Key Generated" : "Create MCP API Key"}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {createdRawKey ? "Save this secret key securely" : "Enter a descriptive name for this client"}
                </p>
              </div>
            </div>

            {createdRawKey ? (
              <div className="space-y-4">
                <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded-xl text-xs text-amber-800 dark:text-amber-300 space-y-1">
                  <p className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    Copy this key now!
                  </p>
                  <p className="text-[11px] leading-relaxed">
                    For your security, this full key will <strong>never be shown again</strong>. Paste it as your Bearer token or <code className="font-mono bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded">X-API-Key</code> in ChatGPT Actions or MCP configs.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-500 uppercase">Secret API Key</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={createdRawKey}
                      className="w-full px-3 py-2 text-xs font-mono bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-900 dark:text-slate-100 select-all"
                    />
                    <button
                      type="button"
                      onClick={handleCopyKey}
                      className="px-3 py-2 bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-bold rounded-xl transition-colors shrink-0 flex items-center gap-1 cursor-pointer"
                    >
                      {copiedKey ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedKey ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-end">
                  <button
                    type="button"
                    onClick={() => { setShowCreateKeyModal(false); setCreatedRawKey(null); }}
                    className="btn-pill-black text-xs px-4 py-2 cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateApiKey} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    Key Name / Description
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. ChatGPT Actions, Claude Desktop, Local Agent"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-[#151D2B] text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowCreateKeyModal(false)}
                    disabled={creatingKey}
                    className="px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creatingKey || !newKeyName.trim()}
                    className="btn-pill-black text-xs px-4 py-2 cursor-pointer flex items-center gap-1.5"
                  >
                    {creatingKey ? (
                      <>
                        <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <Key className="w-3.5 h-3.5" />
                        <span>Generate Key</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {restoreConfirmFile && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#151D2B] rounded-2xl max-w-md w-full p-6 space-y-4 border border-slate-200 dark:border-slate-800 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 rounded-full">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[#0F172A] dark:text-white">Confirm Database Restore</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">Overwriting active database</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Are you sure you want to restore the database from <strong className="font-mono text-slate-900 dark:text-white">{restoreConfirmFile}</strong>? 
              A pre-restore safety copy will be generated automatically before applying this snapshot.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setRestoreConfirmFile(null)}
                disabled={Boolean(restoringFile)}
                className="px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmRestore}
                disabled={Boolean(restoringFile)}
                className="btn-pill-black text-xs px-4 py-2 cursor-pointer flex items-center gap-1.5"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${restoringFile ? "animate-spin" : ""}`} />
                <span>{restoringFile ? "Restoring..." : "Confirm & Restore"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

