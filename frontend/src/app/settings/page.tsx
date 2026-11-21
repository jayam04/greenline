"use client";

import React, { useState, useEffect } from "react";
import { apiFetch, removeAuthToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  User,
  Wallet,
  Palette,
  Users,
  Database,
  Check,
  Shuffle,
  Upload,
  Download,
  KeyRound,
  RefreshCw,
  Trash2,
  RotateCcw,
  Clock,
  HardDrive,
  AlertTriangle,
  Copy,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  LogOut,
  Calendar,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { ThemePicker } from "@/components/ThemePicker";
import { useFont, AppFont, FONT_STORAGE_KEY } from "@/components/FontProvider";
import { generateRandomPseudonym } from "@/lib/pseudonym";
import { updateCommunityPseudonym } from "@/lib/community";
import { cn } from "@/lib/utils";

const INTERVAL_PRESETS = [
  { label: "Every 6 Hours", value: 6 },
  { label: "Every 12 Hours", value: 12 },
  { label: "Daily (24 Hours)", value: 24 },
  { label: "Every 2 Days (48 Hours)", value: 48 },
  { label: "Weekly (7 Days)", value: 168 },
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
  prefix: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
}

const currencies = [
  ["EUR", "Euro", "€"],
  ["USD", "US Dollar", "$"],
  ["INR", "Indian Rupee", "₹"],
  ["GBP", "British Pound", "£"],
  ["CAD", "Canadian Dollar", "C$"],
  ["AUD", "Australian Dollar", "A$"],
];

const fiscal = [
  ["01-01", "January 1st (Calendar Year)", "Standard calendar year (Global/US)"],
  ["04-01", "April 1st (Fiscal Year)", "Standard fiscal year (India, UK, Canada, Japan)"],
  ["07-01", "July 1st (Fiscal Year)", "Mid-year fiscal cycle (Australia, Egypt)"],
  ["10-01", "October 1st (Federal Fiscal Year)", "Q4 fiscal cycle (US Federal, Thailand)"],
];

const FONT_PRESETS = [
  {
    id: "spline-sans" as const,
    label: "Spline Sans",
    tag: "Google Font",
    description: "Modern grotesque sans-serif from Google Fonts (Spline Sans / Spine Sans) optimized for clean UI and dashboards",
    preview: "€155,359.24",
    fontFamily: '"Spline Sans", sans-serif',
  },
  {
    id: "general-sans" as const,
    label: "General Sans",
    tag: "Default",
    description: "Modern geometric sans-serif with distinct character and punchy numbers",
    preview: "€155,359.24",
    fontFamily: '"General Sans", Inter, sans-serif',
  },
  {
    id: "inter" as const,
    label: "Inter",
    tag: "Clean UI",
    description: "Precision neo-grotesque typeface optimized for high-density screen legibility",
    preview: "€155,359.24",
    fontFamily: "Inter, sans-serif",
  },
  {
    id: "rx100" as const,
    label: "RX100 / JetBrains Mono",
    tag: "Ledger",
    description: "Crisp monospace font perfect for financial ledgers and statements",
    preview: "€155,359.24",
    fontFamily: '"JetBrains Mono", monospace',
  },
];

const sections = [
  { id: "profile", label: "Profile", icon: User },
  { id: "finance", label: "Finance", icon: Wallet },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "community", label: "Community", icon: Users },
  { id: "data", label: "Data & API", icon: Database },
] as const;

type SectionId = (typeof sections)[number]["id"];

export default function SettingsPage() {
  const router = useRouter();
  const { font, setFont } = useFont();

  const [section, setSection] = useState<SectionId>("profile");
  const [settings, setSettings] = useState<any>({
    master_currency: "EUR",
    fiscal_year_start: "01-01",
    community_pseudonym: "Solar Beaver",
  });
  const [backupConfig, setBackupConfig] = useState<BackupConfig | null>(null);
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);

  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isBackingUp, setIsBackingUp] = useState(false);

  // Community alias
  const [alias, setAlias] = useState<string>("");

  // Load initial settings
  const loadSettings = React.useCallback(async () => {
    try {
      const [sRes, bCfg, bList, keysRes] = await Promise.allSettled([
        apiFetch<{ community_pseudonym?: string; [key: string]: any }>("/settings"),
        apiFetch<BackupConfig>("/backup/config"),
        apiFetch<{ total_count: number; backups: BackupItem[] }>("/backup/list"),
        apiFetch<ApiKeyItem[]>("/auth/api-keys"),
      ]);

      if (sRes.status === "fulfilled" && sRes.value) {
        setSettings(sRes.value);
        if (sRes.value.community_pseudonym !== undefined) {
          setAlias(sRes.value.community_pseudonym || "");
        }
      }
      if (bCfg.status === "fulfilled" && bCfg.value) {
        setBackupConfig(bCfg.value);
      }
      if (bList.status === "fulfilled" && bList.value?.backups) {
        setBackups(bList.value.backups);
      }
      if (keysRes.status === "fulfilled" && Array.isArray(keysRes.value)) {
        setApiKeys(keysRes.value);
      }
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
  }, []);

  useEffect(() => {
    document.title = "Settings · greenline";
    loadSettings();
  }, [loadSettings]);

  const updateSetting = async (key: string, val: any) => {
    try {
      const updated = { ...settings, [key]: val };
      setSettings(updated);
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({ [key]: val }),
      });
      setStatusMsg({ type: "success", text: "Settings updated successfully." });
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to save settings." });
    }
  };

  const handlePickFont = async (fId: AppFont) => {
    setFont(fId);
    try {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({ app_font: fId }),
      });
    } catch {}
  };

  const handleRandomizePseudonym = () => {
    const randomName = generateRandomPseudonym();
    setAlias(randomName);
  };

  const handleSavePseudonym = async () => {
    if (!alias.trim()) return;
    setIsSaving(true);
    try {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({ community_pseudonym: alias.trim() }),
      });
      await updateCommunityPseudonym(alias.trim());
      try {
        localStorage.setItem("greenline_community_pseudonym", alias.trim());
      } catch {}
      setStatusMsg({ type: "success", text: "Pseudonym updated successfully!" });
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to update pseudonym." });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateBackup = async () => {
    setIsBackingUp(true);
    try {
      await apiFetch("/backup/create", {
        method: "POST",
        body: JSON.stringify({ note: "Manual Snapshot" }),
      });
      const [cfg, list] = await Promise.all([
        apiFetch<BackupConfig>("/backup/config"),
        apiFetch<{ total_count: number; backups: BackupItem[] }>("/backup/list"),
      ]);
      setBackupConfig(cfg);
      setBackups(list?.backups || []);
      setStatusMsg({ type: "success", text: "Backup created successfully!" });
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to create backup." });
    } finally {
      setIsBackingUp(false);
    }
  };

  const handleUpdateBackupConfig = async (payload: { autobackup_interval_hours?: number; autobackup_enabled?: boolean }) => {
    try {
      const updated = await apiFetch<BackupConfig>("/backup/config", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (updated) setBackupConfig(updated);
      setStatusMsg({ type: "success", text: "Backup settings updated." });
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to update backup settings." });
    }
  };

  const handleExportJsonBackup = async () => {
    try {
      const data = await apiFetch<any>("/backup/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `greenline_portfolio_backup_${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to export JSON backup." });
    }
  };

  const handleImportJsonBackup = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      await apiFetch("/backup/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatusMsg({ type: "success", text: "Backup imported successfully! Reloading..." });
      setTimeout(() => window.location.reload(), 1500);
    } catch (e: any) {
      setStatusMsg({ type: "error", text: e?.message || "Failed to import backup file." });
    }
  };

  return (
    <>
      <PageHeader title="Settings" description="Manage your preferences, account identities, and data." />

      {statusMsg && (
        <div
          className={cn(
            "mb-6 flex items-center gap-2 rounded-control p-3 text-body font-medium",
            statusMsg.type === "success"
              ? "bg-gain-soft text-gain border border-gain/20"
              : "bg-loss-soft text-loss border border-loss/20"
          )}
        >
          {statusMsg.type === "success" ? <CheckCircle2 className="size-4 shrink-0" /> : <AlertCircle className="size-4 shrink-0" />}
          <span>{statusMsg.text}</span>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)]">
        {/* Navigation list */}
        <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto md:flex-col md:self-start md:sticky md:top-6">
          {sections.map((s) => {
            const Icon = s.icon;
            const active = section === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setSection(s.id);
                  const el = document.getElementById(s.id);
                  if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ behavior: "smooth" });
                }}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 whitespace-nowrap rounded-control px-3 py-2 text-body font-medium transition-colors [&_svg]:size-[18px]",
                  active
                    ? "bg-surface-2 text-foreground font-semibold shadow-xs"
                    : "text-muted hover:bg-surface-2/70 hover:text-foreground"
                )}
              >
                <Icon />
                <span>{s.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Section Content */}
        <div className="space-y-8 max-w-4xl">
          {/* PROFILE SECTION */}
          <section id="profile" className="space-y-6">
            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div className="border-b border-border pb-4">
                <h3 className="text-title font-semibold">Profile</h3>
                <p className="mt-0.5 text-label text-muted">Your sign-in identity and account details</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 pt-4">
                <div>
                  <label className="mb-1.5 block text-label font-medium text-muted">Username</label>
                  <input
                    readOnly
                    defaultValue="admin"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface-2 px-3 text-body text-foreground"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-label font-medium text-muted">Role</label>
                  <input
                    readOnly
                    defaultValue="Administrator"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface-2 px-3 text-body text-foreground"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1.5 block text-label font-medium text-muted">Email</label>
                  <input
                    readOnly
                    defaultValue="sirquackalotfirst@gmail.com"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface-2 px-3 text-body text-foreground"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1.5 block text-label font-medium text-muted">Community Alias</label>
                  <div className="font-semibold text-foreground text-body">{alias || "Not set"}</div>
                </div>
              </div>
            </div>
          </section>

          {/* FINANCE SECTION */}
          <section id="finance" className="space-y-6">
            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div>
                <h3 className="text-title font-semibold">Reporting currency</h3>
                <p className="mt-0.5 text-label text-muted">Everything is converted to this for net worth and reports</p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 mt-4">
                {currencies.map(([c, n, s]) => {
                  const active = (settings.master_currency || "EUR") === c;
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => updateSetting("master_currency", c)}
                      aria-pressed={active}
                      className={cn(
                        "relative rounded-card border p-3.5 text-left transition-colors",
                        active ? "border-primary bg-surface-2 ring-1 ring-primary/20" : "border-border hover:border-border-strong"
                      )}
                    >
                      <div className="font-semibold text-foreground">{s} {c}</div>
                      <div className="text-micro text-muted mt-0.5">{n}</div>
                      {active && <Check className="absolute right-3 top-3 size-4 text-primary" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div>
                <h3 className="text-title font-semibold">Fiscal year starts</h3>
                <p className="mt-0.5 text-label text-muted">Used for annual snapshots and performance baselines</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 mt-4">
                {fiscal.map(([d, l, s]) => {
                  const active = (settings.fiscal_year_start || "01-01") === d;
                  return (
                    <button
                      key={d}
                      type="button"
                      onClick={() => updateSetting("fiscal_year_start", d)}
                      aria-pressed={active}
                      className={cn(
                        "relative rounded-card border p-3.5 text-left transition-colors",
                        active ? "border-primary bg-surface-2 ring-1 ring-primary/20" : "border-border hover:border-border-strong"
                      )}
                    >
                      <div className="font-semibold text-foreground">{l}</div>
                      <div className="text-micro text-muted mt-0.5">{s}</div>
                      {active && <Check className="absolute right-3 top-3 size-4 text-primary" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div>
                <h3 className="text-title font-semibold">Net worth history</h3>
                <p className="mt-0.5 text-label text-muted">Weekly snapshots start from your earliest record or a date you pick</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 mt-4">
                <div>
                  <label className="mb-1.5 block text-label font-medium text-muted">Snapshot start</label>
                  <select
                    defaultValue="auto"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface px-3 text-body text-foreground"
                  >
                    <option value="auto">Automatic (earliest record)</option>
                    <option value="manual">Manual date</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-label font-medium text-muted">Start date</label>
                  <input
                    type="date"
                    defaultValue="2026-01-01"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface px-3 text-body text-foreground tnum"
                  />
                </div>
              </div>
            </div>
          </section>

          {/* APPEARANCE SECTION */}
          <section id="appearance" className="space-y-6">
            <ThemePicker />

            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div>
                <h3 className="text-title font-semibold">Interface Typography</h3>
                <p className="mt-0.5 text-label text-muted">
                  Select between the default geometric font, modern typography, or financial monospace. Applies everywhere instantly.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 mt-4">
                {FONT_PRESETS.map((p) => {
                  const active = font === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handlePickFont(p.id)}
                      aria-pressed={active}
                      className={cn(
                        "relative rounded-card border p-4 text-left transition-colors",
                        active ? "border-primary bg-surface-2 ring-1 ring-primary/20" : "border-border hover:border-border-strong"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-title font-semibold" style={{ fontFamily: p.fontFamily }}>
                          {p.label}
                        </span>
                        <span className="rounded-full bg-surface px-2 py-0.5 text-micro font-medium text-muted border border-border">
                          {p.tag}
                        </span>
                      </div>
                      <div className="text-label text-muted mt-1">{p.description}</div>
                      <div className="mt-3 text-body tnum font-semibold" style={{ fontFamily: p.fontFamily }}>
                        {p.preview}
                      </div>
                      {active && <Check className="absolute right-3 bottom-3 size-4 text-primary" />}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          {/* COMMUNITY SECTION */}
          <section id="community" className="space-y-6">
            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div className="border-b border-border pb-4">
                <h3 className="text-title font-semibold">Community Profile & Pseudonym</h3>
                <p className="mt-0.5 text-label text-muted">
                  Choose a custom community display name or generate a whimsical pseudonym. Posts are anonymous. This name is shown instead of yours.
                </p>
              </div>
              <div className="space-y-4 pt-4">
                <div>
                  <label htmlFor="community-display-name" className="mb-1.5 block text-label font-medium">
                    Community Display Name
                  </label>
                  <input
                    id="community-display-name"
                    value={alias}
                    onChange={(e) => setAlias(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleSavePseudonym();
                      }
                    }}
                    placeholder="Enter display pseudonym"
                    className="h-9 w-full rounded-control border border-border-strong bg-surface px-3 text-body text-foreground placeholder:text-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 focus-visible:border-info"
                  />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={handleRandomizePseudonym}
                    className="inline-flex items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 py-1.5 text-label font-medium hover:bg-surface-2 transition-colors"
                  >
                    <Shuffle className="size-3.5" /> Pick Random Name
                  </button>

                  <div className="flex items-center gap-2">
                    <span className="text-label text-muted">
                      Preview: <Badge tone="warn">@{alias || "—"}</Badge>
                    </span>
                    <button
                      type="button"
                      onClick={handleSavePseudonym}
                      disabled={isSaving || !alias.trim()}
                      className="inline-flex items-center gap-1.5 rounded-control bg-primary px-4 py-1.5 text-label font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* DATA & API SECTION */}
          <section id="data" className="space-y-6">
            {/* Backups card */}
            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
                <div>
                  <h3 className="text-title font-semibold">Database & Auto-Backup Management</h3>
                  <p className="mt-0.5 text-label text-muted">
                    Active database:{" "}
                    <span className="font-semibold text-foreground">
                      {backupConfig?.database_file || "investments.db"}
                    </span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleCreateBackup}
                  disabled={isBackingUp}
                  className="inline-flex items-center gap-1.5 rounded-control bg-primary px-3 py-1.5 text-label font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  <HardDrive className="size-3.5" />
                  <span>{isBackingUp ? "Backing up..." : "Backup Now"}</span>
                </button>
              </div>

              {/* Import / Export JSON */}
              <div className="py-4 border-b border-border flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={handleExportJsonBackup}
                  className="inline-flex items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 py-1.5 text-label font-medium hover:bg-surface-2 transition-colors"
                >
                  <Download className="size-3.5" /> Export JSON backup
                </button>

                <label className="inline-flex items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 py-1.5 text-label font-medium hover:bg-surface-2 cursor-pointer transition-colors">
                  <Upload className="size-3.5" /> Import JSON backup
                  <input
                    type="file"
                    accept=".json"
                    onChange={handleImportJsonBackup}
                    className="hidden"
                  />
                </label>
              </div>

              {/* Auto-backup frequency */}
              <div className="py-4 border-b border-border flex items-center justify-between">
                <div>
                  <label className="text-label font-medium text-foreground block">Auto-backup frequency</label>
                  <p className="text-micro text-muted">Schedule periodic snapshots of your database</p>
                </div>
                <select
                  value={backupConfig?.autobackup_interval_hours || 24}
                  onChange={(e) => handleUpdateBackupConfig({ autobackup_interval_hours: Number(e.target.value) })}
                  className="h-9 rounded-control border border-border-strong bg-surface px-3 text-label text-foreground"
                >
                  {INTERVAL_PRESETS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Backup History Table */}
              <div className="mt-4">
                <h4 className="text-label font-semibold text-muted uppercase tracking-wider mb-2">
                  Backup History
                </h4>
                {backups.length === 0 ? (
                  <p className="text-label text-muted py-4">No backup snapshots recorded yet.</p>
                ) : (
                  <div className="divide-y divide-border overflow-x-auto text-body">
                    {backups.slice(0, 10).map((b) => (
                      <div key={b.filename} className="flex items-center justify-between py-2.5 gap-4">
                        <div className="min-w-0">
                          <div className="font-medium text-foreground truncate">{b.filename}</div>
                          <div className="text-micro text-muted">
                            {b.size_formatted} · {new Date(b.created_at).toLocaleString()}
                          </div>
                        </div>
                        <span className="rounded-full bg-surface-2 px-2 py-0.5 text-micro font-medium text-muted uppercase">
                          {b.kind}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* API Keys */}
            <div className="rounded-card border border-border bg-surface p-5 shadow-card">
              <div className="flex items-center justify-between border-b border-border pb-4">
                <div>
                  <h3 className="text-title font-semibold">API keys</h3>
                  <p className="mt-0.5 text-label text-muted">Scoped tokens for scripts and automated clients</p>
                </div>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 py-1.5 text-label font-medium hover:bg-surface-2 transition-colors"
                >
                  <KeyRound className="size-3.5" /> New key
                </button>
              </div>
              <div className="pt-4">
                {apiKeys.length === 0 ? (
                  <p className="text-label text-muted">No active keys.</p>
                ) : (
                  <div className="divide-y divide-border">
                    {apiKeys.map((k) => (
                      <div key={k.key_id} className="flex items-center justify-between py-2">
                        <span className="font-medium">{k.name} ({k.prefix}...)</span>
                        <span className="text-micro text-muted">Created {new Date(k.created_at).toLocaleDateString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
