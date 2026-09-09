"use client";

import React, { useState, useEffect } from "react";
import { apiFetch, removeAuthToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { 
  Settings, User, Link as LinkIcon, ShieldCheck, 
  Coins, CheckCircle2, AlertCircle, LogOut, ArrowRight,
  HelpCircle, Sliders, Database, Check, Calendar, Download,
  RefreshCw, Trash2, RotateCcw, Clock, HardDrive, FileJson, AlertTriangle
} from "lucide-react";
import { SUPPORTED_CURRENCIES, CurrencyOption } from "@/lib/format";

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

export default function SettingsPage() {
  const router = useRouter();
  const [linkBrokerage, setLinkBrokerage] = useState(false);
  const [masterCurrency, setMasterCurrency] = useState("EUR");
  const [fiscalYearStart, setFiscalYearStart] = useState("01-01");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

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
          link_brokerage_with_bank: boolean; 
          master_currency: string;
          fiscal_year_start?: string;
        }>("/settings"),
        apiFetch<BackupConfig>("/backup/config").catch(() => null),
        apiFetch<{ total_count: number; backups: BackupItem[] }>("/backup/list").catch(() => ({ total_count: 0, backups: [] }))
      ]);
      
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
        if (res.fiscal_year_start) {
          const fy = res.fiscal_year_start.trim();
          setFiscalYearStart(fy);
          localStorage.setItem("greenline_fiscal_year_start", fy);
        }
      }

      if (bConfig) setBackupConfig(bConfig);
      if (bList) setBackupsList(bList.backups || []);
    } catch (e) {
      console.error("Failed to load settings from server, using localStorage:", e);
      const localLink = localStorage.getItem("greenline_link_brokerage_with_bank") === "true";
      const localCurr = localStorage.getItem("greenline_master_currency") || "EUR";
      const localFy = localStorage.getItem("greenline_fiscal_year_start") || "01-01";
      setLinkBrokerage(localLink);
      setMasterCurrency(localCurr);
      setFiscalYearStart(localFy);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleLinkBrokerage = async (newValue: boolean) => {
    setLinkBrokerage(newValue);
    localStorage.setItem("greenline_link_brokerage_with_bank", String(newValue));
    saveSettings({ link_brokerage_with_bank: newValue, master_currency: masterCurrency, fiscal_year_start: fiscalYearStart });
  };

  const handleChangeMasterCurrency = async (newCurrency: string) => {
    setMasterCurrency(newCurrency);
    localStorage.setItem("greenline_master_currency", newCurrency);
    saveSettings({ link_brokerage_with_bank: linkBrokerage, master_currency: newCurrency, fiscal_year_start: fiscalYearStart });
  };

  const handleChangeFiscalYearStart = async (newFy: string) => {
    setFiscalYearStart(newFy);
    localStorage.setItem("greenline_fiscal_year_start", newFy);
    saveSettings({ link_brokerage_with_bank: linkBrokerage, master_currency: masterCurrency, fiscal_year_start: newFy });
  };

  const saveSettings = async (payload: { link_brokerage_with_bank: boolean; master_currency: string; fiscal_year_start: string }) => {
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

          {/* Card 3: Database & Auto-Backup Management */}
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
                <span className="font-semibold text-slate-500">Session Security</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Active JWT
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
