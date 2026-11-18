"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { money } from "@/lib/utils";
import { convertCurrency, getMasterCurrency } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { 
  Plus, Trash2, Pencil, X, RefreshCw, Search, Landmark, 
  Briefcase, Coins, PiggyBank, AlertCircle
} from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  broker_name?: string;
  account_type: string;
  currency: string;
  current_balance?: number;
  cash_balance?: number;
  securities_value?: number;
  default_dividend_account_id?: number | null;
  default_dividend_account_name?: string | null;
  created_at?: string;
}

interface Asset {
  asset_id: number;
  symbol: string;
  isin?: string | null;
  name: string;
  asset_type: string;
  exchange: string;
  sector?: string | null;
  industry?: string | null;
  currency?: string;
}

interface AssetLookupResult {
  symbol: string;
  isin?: string | null;
  name: string;
  exchange: string;
  sector?: string | null;
  industry?: string | null;
  asset_type: string;
  currency: string;
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [masterCurrency, setMasterCurrency] = useState("EUR");
  const [loading, setLoading] = useState(true);

  // Filter accounts by type: "all" | "bank" | "demat"
  const [accountFilter, setAccountFilter] = useState<"all" | "bank" | "demat">("all");

  // Modals state
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);

  const [isAssetModalOpen, setIsAssetModalOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);

  // Search filter for Security Master
  const [assetSearchQuery, setAssetSearchQuery] = useState("");

  const [accountOrder, setAccountOrder] = useState<number[]>([]);

  useEffect(() => {
    document.title = "Accounts · greenline";
    try {
      const rawLayout = typeof window !== "undefined" ? localStorage.getItem("greenline_account_layout") : null;
      if (rawLayout) {
        const parsed = JSON.parse(rawLayout);
        if (Array.isArray(parsed.order) && parsed.order.length > 0) {
          setAccountOrder(parsed.order);
        }
      }
    } catch (e) {
      console.error("Failed to load account order in accounts page:", e);
    }
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [accs, asts, settings] = await Promise.all([
        apiFetch<Account[]>("/accounts"),
        apiFetch<Asset[]>("/assets"),
        apiFetch<{ master_currency?: string }>("/settings").catch(() => null),
      ]);
      setAccounts(accs || []);
      setAssets(asts || []);
      if (settings?.master_currency) {
        setMasterCurrency(settings.master_currency.toUpperCase());
      } else {
        setMasterCurrency(getMasterCurrency());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const orderedAccounts = useMemo(() => {
    const list = [...accounts];
    if (accountOrder.length > 0) {
      const orderMap = new Map<number, number>();
      accountOrder.forEach((id: number, idx: number) => orderMap.set(id, idx));
      list.sort((a, b) => {
        const orderA = orderMap.has(a.account_id) ? orderMap.get(a.account_id)! : 9999;
        const orderB = orderMap.has(b.account_id) ? orderMap.get(b.account_id)! : 9999;
        return orderA - orderB;
      });
    }
    return list;
  }, [accounts, accountOrder]);

  const bankAccounts = useMemo(() => {
    return orderedAccounts.filter((a) => a.account_type === "bank");
  }, [orderedAccounts]);

  const brokerageAccounts = useMemo(() => {
    return orderedAccounts.filter((a) => a.account_type !== "bank");
  }, [orderedAccounts]);

  const filteredAccounts = useMemo(() => {
    if (accountFilter === "bank") return bankAccounts;
    if (accountFilter === "demat") return brokerageAccounts;
    return orderedAccounts;
  }, [accountFilter, orderedAccounts, bankAccounts, brokerageAccounts]);

  // Aggregate metrics in master currency
  const summaryMetrics = useMemo(() => {
    let totalNetMaster = 0;
    let totalCashMaster = 0;
    let totalSecuritiesMaster = 0;

    for (const acc of accounts) {
      const ccy = acc.currency || "EUR";
      const currentBal = acc.current_balance ?? 0;
      totalNetMaster += convertCurrency(currentBal, ccy, masterCurrency);

      if (acc.account_type === "bank") {
        totalCashMaster += convertCurrency(acc.cash_balance ?? currentBal, ccy, masterCurrency);
      } else {
        totalSecuritiesMaster += convertCurrency(acc.securities_value ?? 0, ccy, masterCurrency);
        totalCashMaster += convertCurrency(acc.cash_balance ?? 0, ccy, masterCurrency);
      }
    }

    return {
      totalNetMaster,
      totalCashMaster,
      totalSecuritiesMaster,
    };
  }, [accounts, masterCurrency]);

  const handleDeleteAccount = async (id: number) => {
    if (!confirm("Are you sure you want to delete this account? Any associated transactions and balances will be removed!")) return;
    try {
      await apiFetch(`/accounts/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete account");
    }
  };

  const handleDeleteAsset = async (id: number) => {
    if (!confirm("Are you sure you want to delete this security? All associated transactions and tax lots will be removed!")) return;
    try {
      await apiFetch(`/assets/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete security");
    }
  };

  // Filtered Assets based on Search Query
  const filteredAssets = useMemo(() => {
    if (!assetSearchQuery.trim()) return assets;
    const q = assetSearchQuery.toLowerCase().trim();
    return assets.filter(
      (a) =>
        a.symbol.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        (a.isin && a.isin.toLowerCase().includes(q)) ||
        (a.sector && a.sector.toLowerCase().includes(q)) ||
        (a.industry && a.industry.toLowerCase().includes(q)) ||
        (a.exchange && a.exchange.toLowerCase().includes(q)) ||
        a.asset_type.toLowerCase().includes(q)
    );
  }, [assets, assetSearchQuery]);

  const getAccountIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "bank":
        return <Landmark className="size-4 text-gain" />;
      case "crypto_exchange":
        return <Coins className="size-4 text-warn" />;
      case "pf":
      case "nps":
        return <PiggyBank className="size-4 text-accent" />;
      default:
        return <Briefcase className="size-4 text-primary" />;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Where your money lives, and the securities you can trade."
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => {
                setEditingAccount(null);
                setIsAccountModalOpen(true);
              }}
            >
              <Plus className="size-4" />
              <span>Add account</span>
            </Button>
          </div>
        }
      />

      {/* Summary KPI Cards Strip */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-card border border-border bg-surface p-4">
          <div className="text-label text-muted">Total Net Balance</div>
          <div className="mt-1 text-display font-semibold tracking-tight text-foreground">
            {money(summaryMetrics.totalNetMaster, masterCurrency)}
          </div>
          <div className="mt-1 text-micro text-subtle">
            Across {accounts.length} connected {accounts.length === 1 ? "account" : "accounts"}
          </div>
        </div>

        <div className="rounded-card border border-border bg-surface p-4">
          <div className="text-label text-muted">Total Bank Cash</div>
          <div className="mt-1 text-heading font-semibold tracking-tight text-foreground">
            {money(summaryMetrics.totalCashMaster, masterCurrency)}
          </div>
          <div className="mt-1 text-micro text-subtle">
            {bankAccounts.length} liquid cash {bankAccounts.length === 1 ? "account" : "accounts"}
          </div>
        </div>

        <div className="rounded-card border border-border bg-surface p-4">
          <div className="text-label text-muted">Securities Valuation</div>
          <div className="mt-1 text-heading font-semibold tracking-tight text-foreground">
            {money(summaryMetrics.totalSecuritiesMaster, masterCurrency)}
          </div>
          <div className="mt-1 text-micro text-subtle">
            {brokerageAccounts.length} investment {brokerageAccounts.length === 1 ? "portfolio" : "portfolios"}
          </div>
        </div>
      </div>

      {/* SECTION 1: Connected Accounts */}
      <div className="rounded-card border border-border bg-surface p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
          <div>
            <h2 className="text-title font-semibold text-foreground">Connected Accounts</h2>
            <p className="text-label text-muted mt-0.5">
              {accounts.length} connected
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Filter Buttons */}
            <div className="inline-flex rounded-full bg-surface-2 p-1">
              <button
                type="button"
                onClick={() => setAccountFilter("all")}
                className={`rounded-full px-3.5 py-1 text-label font-medium transition-colors ${
                  accountFilter === "all"
                    ? "bg-surface text-foreground shadow-card font-semibold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                All ({accounts.length})
              </button>
              <button
                type="button"
                onClick={() => setAccountFilter("bank")}
                className={`rounded-full px-3.5 py-1 text-label font-medium transition-colors ${
                  accountFilter === "bank"
                    ? "bg-surface text-foreground shadow-card font-semibold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                Banks ({bankAccounts.length})
              </button>
              <button
                type="button"
                onClick={() => setAccountFilter("demat")}
                className={`rounded-full px-3.5 py-1 text-label font-medium transition-colors ${
                  accountFilter === "demat"
                    ? "bg-surface text-foreground shadow-card font-semibold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                Brokerage ({brokerageAccounts.length})
              </button>
            </div>

            <Button
              size="sm"
              onClick={() => {
                setEditingAccount(null);
                setIsAccountModalOpen(true);
              }}
            >
              <Plus className="size-4" />
              <span>Add account</span>
            </Button>
          </div>
        </div>

        {/* Accounts Cards Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-card border border-border bg-surface-2/40 p-4 animate-pulse h-32"
              />
            ))}
          </div>
        ) : filteredAccounts.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
            {filteredAccounts.map((acc) => {
              const isDemat = acc.account_type === "demat";
              const ccy = acc.currency || "EUR";
              const currentBal = acc.current_balance ?? 0;
              const convertedBal = convertCurrency(currentBal, ccy, masterCurrency);

              return (
                <div
                  key={acc.account_id}
                  className="group relative flex flex-col justify-between rounded-card border border-border bg-surface p-4 transition-all hover:border-border-strong"
                >
                  <div>
                    {/* Card Top: Icon, Names, Type, and Actions */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="grid size-9 shrink-0 place-items-center rounded-control bg-surface-2 text-muted">
                          {getAccountIcon(acc.account_type)}
                        </span>
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold text-foreground text-body leading-tight">
                            {acc.account_name}
                          </h3>
                          <p className="truncate text-label text-muted mt-0.5">
                            {acc.broker_name ? `${acc.broker_name} · ` : ""}
                            {isDemat ? "Brokerage" : acc.account_type.replace(/_/g, " ")} · {ccy}
                          </p>
                        </div>
                      </div>

                      {/* Edit / Delete Ghost Action Buttons */}
                      <div className="flex items-center opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingAccount(acc);
                            setIsAccountModalOpen(true);
                          }}
                          className="p-1.5 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors cursor-pointer"
                          title="Edit account"
                          aria-label="Edit account"
                        >
                          <Pencil className="size-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteAccount(acc.account_id)}
                          className="p-1.5 text-loss/70 hover:text-loss hover:bg-loss-soft rounded-control transition-colors cursor-pointer"
                          title="Delete account"
                          aria-label="Delete account"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Balance Information */}
                    <div className="mt-4 pt-3 border-t border-border">
                      <div className="text-micro uppercase tracking-wider text-subtle font-medium">Balance</div>
                      <div className="mt-0.5 flex items-baseline gap-2 flex-wrap">
                        <span className="text-heading font-semibold text-foreground tracking-tight">
                          {money(currentBal, ccy)}
                        </span>
                        {ccy !== masterCurrency && (
                          <span className="text-label text-muted font-medium">
                            ≈ {money(convertedBal, masterCurrency)}
                          </span>
                        )}
                      </div>

                      {/* Breakdown for Demat / Brokerage accounts */}
                      {isDemat && (
                        <div className="mt-2 text-micro text-muted flex items-center gap-1.5 flex-wrap">
                          <span className="font-medium">
                            Securities: {money(acc.securities_value ?? 0, ccy)}
                          </span>
                          <span>·</span>
                          <span className="font-medium">
                            Cash: {money(acc.cash_balance ?? 0, ccy)}
                          </span>
                        </div>
                      )}

                      {/* Dividend Bank Link badge */}
                      {acc.default_dividend_account_name && (
                        <div className="mt-2.5">
                          <span className="inline-flex items-center text-micro font-medium text-gain bg-gain-soft px-2 py-0.5 rounded-full border border-gain/20">
                            Divs → {acc.default_dividend_account_name}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-10 border border-dashed border-border rounded-card bg-surface-2/20">
            <p className="text-body font-semibold text-foreground">No accounts found</p>
            <p className="text-label text-muted mt-1 max-w-sm mx-auto">
              Add your investment brokerage accounts or bank accounts to track your net worth and balances.
            </p>
          </div>
        )}
      </div>

      {/* SECTION 2: Securities Master Registry */}
      <div className="rounded-card border border-border bg-surface p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-border gap-3">
          <div>
            <h2 className="text-title font-semibold text-foreground">Securities</h2>
            <p className="text-label text-muted mt-0.5">
              {assets.length} in your registry
            </p>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Real-time Search Box */}
            <div className="relative min-w-[240px]">
              <Search className="size-3.5 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Filter by name, ticker, or ISIN..."
                value={assetSearchQuery}
                onChange={(e) => setAssetSearchQuery(e.target.value)}
                className="w-full bg-surface-2 text-foreground placeholder:text-muted text-label rounded-control pl-8.5 pr-8 py-1.5 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
              {assetSearchQuery && (
                <button
                  type="button"
                  onClick={() => setAssetSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>

            <Button
              size="sm"
              onClick={() => {
                setEditingAsset(null);
                setIsAssetModalOpen(true);
              }}
            >
              <Plus className="size-4" />
              <span>Add security</span>
            </Button>
          </div>
        </div>

        {/* Security Master Table */}
        <div className="rounded-control border border-border overflow-x-auto">
          <table className="w-full text-left text-body">
            <thead className="border-b border-border text-micro uppercase tracking-wider text-muted font-semibold bg-surface-2/40">
              <tr>
                <th className="py-2.5 px-3.5">Symbol / ISIN</th>
                <th className="py-2.5 px-3.5">Asset Name</th>
                <th className="py-2.5 px-3.5">Exchange</th>
                <th className="py-2.5 px-3.5">Sector / Industry</th>
                <th className="py-2.5 px-3.5 text-right">Currency</th>
                <th className="py-2.5 px-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredAssets.map((ast) => (
                <tr key={ast.asset_id} className="hover:bg-surface-2/30 transition-colors group">
                  <td className="py-2.5 px-3.5 font-semibold text-foreground">
                    <div>{ast.symbol}</div>
                    {ast.isin && (
                      <div className="text-micro font-normal text-muted">{ast.isin}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-3.5 font-medium text-foreground">
                    {ast.name}
                  </td>
                  <td className="py-2.5 px-3.5 text-muted">
                    {ast.exchange || "US"}
                  </td>
                  <td className="py-2.5 px-3.5 text-muted">
                    {ast.sector ? (
                      <div>
                        <span className="font-medium text-foreground">{ast.sector}</span>
                        {ast.industry && <span className="text-micro block text-muted">{ast.industry}</span>}
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2.5 px-3.5 text-right font-semibold text-muted uppercase">
                    {ast.currency || "USD"}
                  </td>
                  <td className="py-2.5 px-3.5 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingAsset(ast);
                          setIsAssetModalOpen(true);
                        }}
                        className="p-1.5 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors cursor-pointer"
                        title="Edit security"
                        aria-label="Edit security"
                      >
                        <Pencil className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteAsset(ast.asset_id)}
                        className="p-1.5 text-loss/70 hover:text-loss hover:bg-loss-soft rounded-control transition-colors cursor-pointer"
                        title="Delete security"
                        aria-label="Delete security"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredAssets.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted font-medium">
                    No matching securities found in master directory.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* POPUP MODAL: Account Modal */}
      {isAccountModalOpen && (
        <AccountModal
          isOpen={isAccountModalOpen}
          initialData={editingAccount}
          allAccounts={accounts}
          onClose={() => {
            setIsAccountModalOpen(false);
            setEditingAccount(null);
          }}
          onSuccess={() => {
            setIsAccountModalOpen(false);
            setEditingAccount(null);
            loadData();
          }}
        />
      )}

      {/* POPUP MODAL: Asset Modal */}
      {isAssetModalOpen && (
        <AssetModal
          isOpen={isAssetModalOpen}
          initialData={editingAsset}
          onClose={() => {
            setIsAssetModalOpen(false);
            setEditingAsset(null);
          }}
          onSuccess={() => {
            setIsAssetModalOpen(false);
            setEditingAsset(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

// ----------------------------------------------------
// ACCOUNT MODAL POPUP COMPONENT
// ----------------------------------------------------
interface AccountModalProps {
  isOpen: boolean;
  initialData: Account | null;
  allAccounts?: Account[];
  onClose: () => void;
  onSuccess: () => void;
}

export function AccountModal({ isOpen, initialData, allAccounts = [], onClose, onSuccess }: AccountModalProps) {
  const [name, setName] = useState(initialData?.account_name || "");
  const [broker, setBroker] = useState(initialData?.broker_name || "");
  const [type, setType] = useState(initialData?.account_type || "demat");
  const [currency, setCurrency] = useState(initialData?.currency || "USD");
  const [defaultDividendAccountId, setDefaultDividendAccountId] = useState<number | "">(
    initialData?.default_dividend_account_id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please provide an account name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const payload: any = {
        account_name: name.trim(),
        broker_name: broker.trim() || null,
        account_type: type,
        currency: currency.toUpperCase(),
        default_dividend_account_id: type === "demat" && defaultDividendAccountId ? Number(defaultDividendAccountId) : null,
      };

      if (initialData) {
        await apiFetch(`/accounts/${initialData.account_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/accounts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to save account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface rounded-card border border-border w-full max-w-md shadow-pop p-6 relative">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-foreground p-1.5 rounded-control hover:bg-surface-2 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>

        <div className="mb-5">
          <h2 className="text-title font-semibold text-foreground">
            {initialData ? "Edit Account" : "Add New Account"}
          </h2>
          <p className="text-label text-muted mt-0.5">
            Configure brokerage, bank, or crypto investment accounts
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-loss-soft border border-loss/20 rounded-control text-loss text-label font-medium flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-body">
          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Account Name <span className="text-loss">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Zerodha Primary, Charles Schwab, Main Bank"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Broker / Platform
              </label>
              <input
                type="text"
                placeholder="e.g. Zerodha, Schwab"
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Account Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              >
                <option value="demat">Demat / Stocks</option>
                <option value="mutual_fund">Mutual Funds</option>
                <option value="crypto_exchange">Crypto Wallet</option>
                <option value="bank">Bank / Cash</option>
                <option value="pf">Provident Fund (PF)</option>
                <option value="nps">NPS / Pension</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Base Currency
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
            >
              <option value="USD">USD ($ - US Dollar)</option>
              <option value="EUR">EUR (€ - Euro)</option>
              <option value="INR">INR (₹ - Indian Rupee)</option>
              <option value="GBP">GBP (£ - British Pound)</option>
              <option value="CAD">CAD (CA$ - Canadian Dollar)</option>
              <option value="AUD">AUD (A$ - Australian Dollar)</option>
              <option value="JPY">JPY (¥ - Japanese Yen)</option>
              <option value="CHF">CHF (CHF - Swiss Franc)</option>
              <option value="SGD">SGD (S$ - Singapore Dollar)</option>
            </select>
          </div>

          {type === "demat" && (
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5 flex items-center justify-between">
                <span>Default Dividend Bank Account</span>
                <span className="text-micro text-subtle font-normal">Optional</span>
              </label>
              <select
                value={defaultDividendAccountId}
                onChange={(e) => setDefaultDividendAccountId(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              >
                <option value="">-- None (Manual Linking) --</option>
                {allAccounts
                  .filter((a) => a.account_type === "bank" && a.account_id !== initialData?.account_id)
                  .map((b) => (
                    <option key={b.account_id} value={b.account_id}>
                      {b.account_name} ({b.currency})
                    </option>
                  ))}
              </select>
              <p className="text-micro text-muted mt-1">
                Dividends for stocks in this Demat account will be auto-suggested to deposit into this bank account.
              </p>
            </div>
          )}

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="rounded-control px-4 py-2 text-label font-medium text-muted hover:text-foreground hover:bg-surface-2 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={loading}
              size="sm"
            >
              {loading ? "Saving..." : initialData ? "Update Account" : "Create Account"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ----------------------------------------------------
// ASSET / SECURITY MODAL POPUP COMPONENT
// ----------------------------------------------------
interface AssetModalProps {
  isOpen: boolean;
  initialData: Asset | null;
  onClose: () => void;
  onSuccess: () => void;
}

export function AssetModal({ isOpen, initialData, onClose, onSuccess }: AssetModalProps) {
  const [symbol, setSymbol] = useState(initialData?.symbol || "");
  const [name, setName] = useState(initialData?.name || "");
  const [assetType, setAssetType] = useState(initialData?.asset_type || "stock");
  const [exchange, setExchange] = useState(initialData?.exchange || "NASDAQ");
  const [currency, setCurrency] = useState(initialData?.currency || "USD");
  const [isin, setIsin] = useState(initialData?.isin || "");
  const [sector, setSector] = useState(initialData?.sector || "");
  const [industry, setIndustry] = useState(initialData?.industry || "");

  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleLookup = async () => {
    const cleanSym = symbol.trim().toUpperCase();
    if (!cleanSym) {
      setLookupError("Please enter a ticker symbol first.");
      return;
    }

    try {
      setLookingUp(true);
      setLookupError("");
      const data = await apiFetch<AssetLookupResult>(`/assets/lookup?symbol=${encodeURIComponent(cleanSym)}`);
      
      if (data.name) setName(data.name);
      if (data.exchange) setExchange(data.exchange);
      if (data.sector) setSector(data.sector);
      if (data.industry) setIndustry(data.industry);
      if (data.isin) setIsin(data.isin);
      if (data.asset_type) setAssetType(data.asset_type);
      if (data.currency) setCurrency(data.currency);
    } catch (err: any) {
      setLookupError(err.message || "Could not auto-fetch metadata from Yahoo Finance");
    } finally {
      setLookingUp(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim() || !name.trim()) {
      setError("Please fill in both Symbol and Security Name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const payload = {
        symbol: symbol.trim().toUpperCase(),
        name: name.trim(),
        asset_type: assetType,
        exchange: exchange.trim().toUpperCase(),
        currency: currency.toUpperCase(),
        isin: isin.trim() || null,
        sector: sector.trim() || null,
        industry: industry.trim() || null,
      };

      if (initialData) {
        await apiFetch(`/assets/${initialData.asset_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/assets", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to save security");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface rounded-card border border-border w-full max-w-lg shadow-pop p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-foreground p-1.5 rounded-control hover:bg-surface-2 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>

        <div className="mb-5">
          <h2 className="text-title font-semibold text-foreground">
            {initialData ? "Edit Security" : "Add Security to Master"}
          </h2>
          <p className="text-label text-muted mt-0.5">
            Register stock, ETF, or asset details in the security master
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-loss-soft border border-loss/20 rounded-control text-loss text-label font-medium flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-body">
          {/* Symbol & Auto Fetch */}
          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Ticker / Symbol <span className="text-loss">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="e.g. AAPL, MSFT, RELIANCE.NS, BTC-USD"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="flex-1 bg-surface-2 text-foreground font-bold uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
                required
              />
              <button
                type="button"
                onClick={handleLookup}
                disabled={lookingUp}
                className="rounded-control px-3 py-2 text-label font-medium text-foreground bg-surface-2 hover:bg-border border border-border shrink-0 cursor-pointer flex items-center gap-1.5 transition-colors"
                title="Fetch metadata automatically from Yahoo Finance"
              >
                <RefreshCw className={`size-3.5 ${lookingUp ? "animate-spin text-primary" : ""}`} />
                <span>{lookingUp ? "Fetching..." : "Fetch Info"}</span>
              </button>
            </div>
            {lookupError && (
              <p className="text-micro font-medium text-loss mt-1">{lookupError}</p>
            )}
          </div>

          <div>
            <label className="block text-foreground font-semibold text-label mb-1.5">
              Security Full Name <span className="text-loss">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Apple Inc., Microsoft Corporation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Asset Type
              </label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all uppercase"
              >
                <option value="stock">Stock</option>
                <option value="etf">ETF</option>
                <option value="mutual_fund">Mutual Fund</option>
                <option value="crypto">Crypto</option>
                <option value="index">Index</option>
                <option value="bond">Bond</option>
              </select>
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Exchange
              </label>
              <input
                type="text"
                placeholder="NASDAQ, NYSE, NSE, BSE"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Trading Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="INR">INR (₹)</option>
                <option value="GBP">GBP (£)</option>
                <option value="CAD">CAD (CA$)</option>
                <option value="AUD">AUD (A$)</option>
                <option value="JPY">JPY (¥)</option>
                <option value="CHF">CHF (CHF)</option>
                <option value="SGD">SGD (S$)</option>
              </select>
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                ISIN (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. US0378331005"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium uppercase rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Sector (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Technology, Healthcare"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-foreground font-semibold text-label mb-1.5">
                Industry (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Consumer Electronics"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-surface-2 text-foreground font-medium rounded-control px-3.5 py-2 border border-border focus:border-border-strong focus:outline-none transition-all"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="rounded-control px-4 py-2 text-label font-medium text-muted hover:text-foreground hover:bg-surface-2 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={loading}
              size="sm"
            >
              {loading ? "Saving..." : initialData ? "Update Security" : "Add Security"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
