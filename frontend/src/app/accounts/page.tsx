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
import { 
  AccountModal, 
  AssetModal, 
  type Account, 
  type Asset 
} from "@/components/AccountModals";

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
