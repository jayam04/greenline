"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatQty } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { 
  RefreshCw, X, Check, Zap, HelpCircle, CheckCircle2 
} from "lucide-react";

interface CandidateMatch {
  match_id: number;
  match_type: string;
  account_id: number;
  account_name: string;
  date: string;
  amount: number;
  title: string;
}

interface DiscrepancyItem {
  expected_dividend_id?: number | null;
  transaction_id?: number | null;
  account_id: number;
  account_name: string;
  asset_id: number;
  asset_symbol: string;
  asset_name: string;
  currency: string;
  transaction_date: string;
  quantity: number;
  price_per_unit: number;
  total_amount: number;
  expected_amount?: number | null;
  linked_transaction_amount?: number | null;
  taxes: number;
  net_amount: number;
  source: string;
  status: string;
  suggested_funding_account_id?: number | null;
  suggested_funding_account_name?: string | null;
  candidate_matches?: CandidateMatch[];
  notes?: string | null;
}

interface DiscrepancySummary {
  total_count: number;
  total_unlinked_amount: number;
  auto_linkable_count: number;
  unlinked_items: DiscrepancyItem[];
}

interface AccountOption {
  account_id: number;
  account_name: string;
  account_type: string;
  currency: string;
}

export default function DiscrepanciesPage() {
  const [data, setData] = useState<DiscrepancySummary | null>(null);
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [selectedBankPerTx, setSelectedBankPerTx] = useState<Record<string, number>>({});
  const [selectedDatePerTx, setSelectedDatePerTx] = useState<Record<string, string>>({});
  const [batchBankId, setBatchBankId] = useState<number | "">("");
  const [setDefaultDemat, setSetDefaultDemat] = useState<Record<string, boolean>>({});

  useEffect(() => {
    document.title = "Reconcile · greenline";
    loadData();
  }, []);

  const getRowKey = (item: DiscrepancyItem): string => {
    if (item.expected_dividend_id) return `exp-${item.expected_dividend_id}`;
    if (item.transaction_id) return `tx-${item.transaction_id}`;
    return `item-${item.account_id}-${item.asset_id}-${item.transaction_date}`;
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const [discRes, accRes] = await Promise.all([
        apiFetch<DiscrepancySummary>("/discrepancies"),
        apiFetch<AccountOption[]>("/accounts"),
      ]);
      setData(discRes);
      setAccounts(accRes || []);

      const bankAccs = (accRes || []).filter((a) => a.account_type === "bank");

      if (discRes && discRes.unlinked_items) {
        const initialBanks: Record<string, number> = {};
        const initialDates: Record<string, string> = {};

        discRes.unlinked_items.forEach((item) => {
          const key = getRowKey(item);
          initialDates[key] = item.transaction_date;

          if (item.candidate_matches && item.candidate_matches.length > 0) {
            initialBanks[key] = item.candidate_matches[0].account_id;
            initialDates[key] = item.candidate_matches[0].date;
          } else if (item.suggested_funding_account_id) {
            initialBanks[key] = item.suggested_funding_account_id;
          } else {
            const sameCurr = bankAccs.find((b) => b.currency === item.currency);
            if (sameCurr) {
              initialBanks[key] = sameCurr.account_id;
            } else if (bankAccs.length > 0) {
              initialBanks[key] = bankAccs[0].account_id;
            }
          }
        });

        setSelectedBankPerTx(initialBanks);
        setSelectedDatePerTx(initialDates);
      }
    } catch (err) {
      console.error("Failed to load dividend discrepancies:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAutoLinkDefaults = async () => {
    if (!data || data.auto_linkable_count === 0) return;
    try {
      setResolving(true);
      const resolutions = data.unlinked_items
        .filter((item) => item.suggested_funding_account_id)
        .map((item) => {
          const key = getRowKey(item);
          return {
            expected_dividend_id: item.expected_dividend_id || undefined,
            transaction_id: item.transaction_id || undefined,
            funding_account_id: item.suggested_funding_account_id!,
            transaction_date: selectedDatePerTx[key] || item.transaction_date || undefined,
            total_amount: item.total_amount,
            taxes: item.taxes || 0.0,
          };
        });

      if (resolutions.length > 0) {
        await apiFetch("/discrepancies/resolve", {
          method: "POST",
          body: JSON.stringify({ resolutions }),
        });
        await loadData();
      }
    } catch (err: any) {
      alert(err.message || "Failed to auto-link default accounts");
    } finally {
      setResolving(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await apiFetch("/discrepancies/sync", { method: "POST" });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to sync expected dividends");
    } finally {
      setSyncing(false);
    }
  };

  const handleResolveSingle = async (item: DiscrepancyItem, dematId: number) => {
    const key = getRowKey(item);
    const bankId = selectedBankPerTx[key];
    if (!bankId) {
      alert("Please select a destination bank account.");
      return;
    }

    try {
      setResolving(true);
      const shouldSetDefault = setDefaultDemat[key];
      const creditDate = selectedDatePerTx[key];

      await apiFetch("/discrepancies/resolve", {
        method: "POST",
        body: JSON.stringify({
          resolutions: [
            {
              expected_dividend_id: item.expected_dividend_id || undefined,
              transaction_id: item.transaction_id || undefined,
              funding_account_id: bankId,
              transaction_date: creditDate || undefined,
              total_amount: item.total_amount,
              taxes: item.taxes || 0.0,
            }
          ],
          set_default_for_demat: shouldSetDefault
            ? { demat_account_id: dematId, default_dividend_account_id: bankId }
            : null,
        }),
      });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to resolve dividend");
    } finally {
      setResolving(false);
    }
  };

  const handleDismiss = async (expId: number) => {
    try {
      setResolving(true);
      await apiFetch("/discrepancies/dismiss", {
        method: "POST",
        body: JSON.stringify({ expected_dividend_ids: [expId] }),
      });
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to dismiss expected dividend");
    } finally {
      setResolving(false);
    }
  };

  const toggleSelectAll = () => {
    if (!data) return;
    if (selectedKeys.size === data.unlinked_items.length) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(data.unlinked_items.map(getRowKey)));
    }
  };

  const toggleSelectItem = (key: string) => {
    const next = new Set(selectedKeys);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setSelectedKeys(next);
  };

  const bankAccounts = accounts.filter((a) => a.account_type === "bank");

  return (
    <>
      <PageHeader
        title="Reconcile"
        description="Match expected dividends with deposits that landed in your bank."
        actions={
          <div className="flex items-center gap-2">
            {(data?.auto_linkable_count || 0) > 0 && (
              <Button variant="outline" size="sm" onClick={handleAutoLinkDefaults} disabled={resolving}>
                <Check className="size-4" />
                <span>Auto-Link Defaults ({data?.auto_linkable_count})</span>
              </Button>
            )}
            <Button size="sm" onClick={handleSync} disabled={syncing}>
              <RefreshCw className={`size-4 ${syncing ? "animate-spin" : ""}`} />
              <span>{syncing ? "Syncing..." : "Sync dividends"}</span>
            </Button>
          </div>
        }
      />

      {/* KPI Summary Cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <Card className="rounded-card border border-border bg-surface p-5 shadow-card">
          <div className="text-micro uppercase tracking-wider text-subtle font-medium">Unlinked Distributions</div>
          <div className="mt-1 text-heading font-semibold text-warn tabular-nums">
            {data?.total_count || 0}
          </div>
          <p className="mt-1 text-label text-muted">Awaiting deposit routing</p>
        </Card>

        <Card className="rounded-card border border-border bg-surface p-5 shadow-card">
          <div className="text-micro uppercase tracking-wider text-subtle font-medium">Total Unlinked Value</div>
          <div className="mt-1 text-heading font-semibold text-foreground tabular-nums">
            {formatCurrency(data?.total_unlinked_amount || 0, "EUR")}
          </div>
          <p className="mt-1 text-label text-muted">Net payout after withheld taxes</p>
        </Card>
      </div>

      {/* Reconciliation Table Card */}
      <Card className="rounded-card border border-border bg-surface shadow-card">
        <CardHeader>
          <CardTitle>Dividend reconciliation hub</CardTitle>
          <CardDescription>Expected distributions vs actual bank receipts</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.unlinked_items && data.unlinked_items.length > 0 ? (
            <div className="overflow-x-auto rounded-control border border-border">
              <table className="w-full text-left text-body">
                <thead className="border-b border-border text-micro uppercase tracking-wider text-muted font-semibold bg-surface-2/40">
                  <tr>
                    <th className="py-2.5 px-3.5 w-10">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={selectedKeys.size === data.unlinked_items.length && data.unlinked_items.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded border-border text-primary focus:ring-primary size-4"
                      />
                    </th>
                    <th className="py-2.5 px-3.5">Ex-date</th>
                    <th className="py-2.5 px-3.5">Security</th>
                    <th className="py-2.5 px-3.5">Shares & rate</th>
                    <th className="py-2.5 px-3.5 text-right">Net payout</th>
                    <th className="py-2.5 px-3.5">Deposit to</th>
                    <th className="py-2.5 px-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.unlinked_items.map((d) => {
                    const key = getRowKey(d);
                    const isSelected = selectedKeys.has(key);

                    return (
                      <tr key={key} className="hover:bg-surface-2/30 transition-colors">
                        <td className="py-2.5 px-3.5">
                          <input
                            type="checkbox"
                            aria-label={`Select ${d.asset_symbol}`}
                            checked={isSelected}
                            onChange={() => toggleSelectItem(key)}
                            className="rounded border-border text-primary focus:ring-primary size-4"
                          />
                        </td>
                        <td className="py-2.5 px-3.5 text-label font-medium text-muted tabular-nums">
                          {d.transaction_date}
                        </td>
                        <td className="py-2.5 px-3.5 font-semibold text-foreground leading-tight">
                          <div>{d.asset_symbol}</div>
                          <div className="text-micro font-normal text-muted">{d.asset_name}</div>
                        </td>
                        <td className="py-2.5 px-3.5 text-label text-muted tabular-nums">
                          {formatQty(d.quantity)} shares @ {formatCurrency(d.price_per_unit, d.currency)}
                        </td>
                        <td className="py-2.5 px-3.5 text-right font-semibold text-gain tabular-nums">
                          +{formatCurrency(d.net_amount, d.currency)}
                        </td>
                        <td className="py-2.5 px-3.5">
                          <div className="flex flex-col gap-1.5">
                            <div className="flex items-center gap-2">
                              <input
                                type="date"
                                value={selectedDatePerTx[key] || d.transaction_date}
                                onChange={(e) =>
                                  setSelectedDatePerTx((prev) => ({ ...prev, [key]: e.target.value }))
                                }
                                className="bg-surface-2 text-foreground font-medium rounded-control px-2.5 py-1 text-label border border-border focus:outline-none w-36"
                              />
                              <select
                                value={selectedBankPerTx[key] || ""}
                                onChange={(e) =>
                                  setSelectedBankPerTx((prev) => ({ ...prev, [key]: Number(e.target.value) }))
                                }
                                className="bg-surface-2 text-foreground font-medium rounded-control px-2.5 py-1 text-label border border-border focus:outline-none w-48"
                              >
                                {bankAccounts.map((b) => (
                                  <option key={b.account_id} value={b.account_id}>
                                    {b.account_name} ({b.currency})
                                  </option>
                                ))}
                              </select>
                            </div>
                            {d.candidate_matches && d.candidate_matches.length > 0 && (
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {d.candidate_matches.map((m, mIdx) => (
                                  <button
                                    key={mIdx}
                                    type="button"
                                    onClick={() => {
                                      setSelectedBankPerTx((prev) => ({ ...prev, [key]: m.account_id }));
                                      setSelectedDatePerTx((prev) => ({ ...prev, [key]: m.date }));
                                    }}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-micro font-medium bg-gain-soft text-gain border border-gain/20 hover:bg-gain/20 transition-colors cursor-pointer text-left"
                                    title={`Use matched bank ${m.account_name} on ${m.date}`}
                                  >
                                    <span>Match: {m.account_name}</span>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-3.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              size="sm"
                              onClick={() => handleResolveSingle(d, d.account_id)}
                              disabled={resolving}
                            >
                              Link Deposit
                            </Button>
                            {d.expected_dividend_id && (
                              <button
                                type="button"
                                onClick={() => handleDismiss(d.expected_dividend_id!)}
                                className="p-1.5 text-muted hover:text-foreground hover:bg-surface-2 rounded-control transition-colors"
                                title="Dismiss"
                                aria-label="Dismiss"
                              >
                                <X className="size-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-16 text-center text-label text-muted">
              {loading ? "Checking reconciliation records..." : "No Discrepancies Found · All dividends are fully reconciled with your bank deposits!"}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
