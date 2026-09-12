"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatMoney, formatNum, formatQty } from "@/lib/format";
import { 
  Sparkles, ArrowLeft, CheckCircle2, AlertTriangle, 
  HelpCircle, Trash2, Edit, Check, X, Layers,
  ChevronRight, RefreshCw, Plus, ArrowRight, Eye
} from "lucide-react";

interface StagedRecord {
  staged_id: number;
  batch_id: number;
  record_type: string;
  transaction_date: string;
  action_type: string;
  account_id?: number | null;
  account_name?: string | null;
  account_name_raw?: string | null;
  asset_id?: number | null;
  asset_symbol?: string | null;
  asset_symbol_raw?: string | null;
  asset_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  category_name_raw?: string | null;
  quantity?: number | null;
  price_per_unit?: number | null;
  total_amount: number;
  fees: number;
  taxes: number;
  currency: string;
  notes?: string | null;
  source_raw_text?: string | null;
  review_status: string; // approved, pending, skipped, modified
  match_status: string; // new, exact_match, probable_match
  matched_entity_id?: number | null;
  matched_entity_details?: any | null;
}

interface ImportBatch {
  batch_id: number;
  filename: string;
  file_type: string;
  status: string;
  target_account_name?: string | null;
  default_currency: string;
  custom_instructions?: string | null;
  total_records: number;
  new_records: number;
  exact_matches: number;
  probable_matches: number;
  created_at: string;
}

export default function ReviewWorkbenchPage({ params }: { params?: any }) {
  const router = useRouter();
  const routeParams = useParams();
  const [batchId, setBatchId] = useState<number>(() => {
    if (params && typeof params === "object" && "batch_id" in params && typeof params.batch_id === "string") {
      return parseInt(params.batch_id, 10);
    }
    if (routeParams?.batch_id && typeof routeParams.batch_id === "string") {
      return parseInt(routeParams.batch_id, 10);
    }
    return 0;
  });

  useEffect(() => {
    if (params && typeof params.then === "function") {
      params.then((p: any) => {
        if (p?.batch_id) setBatchId(parseInt(p.batch_id, 10));
      });
    } else if (params?.batch_id) {
      setBatchId(parseInt(params.batch_id, 10));
    } else if (routeParams?.batch_id) {
      setBatchId(parseInt(routeParams.batch_id as string, 10));
    }
  }, [params, routeParams]);

  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [records, setRecords] = useState<StagedRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all"); // all, new, probable, exact, skipped
  
  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Comparison Drawer / Modal state
  const [comparingRecord, setComparingRecord] = useState<StagedRecord | null>(null);

  // Edit modal state
  const [editingRecord, setEditingRecord] = useState<StagedRecord | null>(null);

  // Manual Add Modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [manualForm, setManualForm] = useState({
    record_type: "investment",
    transaction_date: new Date().toISOString().slice(0, 10),
    action_type: "buy",
    asset_symbol_raw: "",
    total_amount: "",
    quantity: "",
    price_per_unit: "",
    fees: "0",
    notes: ""
  });

  // Final Green Flag modal
  const [isCommitModalOpen, setIsCommitModalOpen] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState<any | null>(null);

  useEffect(() => {
    document.title = `Batch #${batchId} Review Workbench · greenline`;
    loadBatchData();
  }, [batchId]);

  const loadBatchData = async () => {
    try {
      setLoading(true);
      const [bData, rData] = await Promise.all([
        apiFetch<ImportBatch>(`/import/batches/${batchId}`),
        apiFetch<StagedRecord[]>(`/import/batches/${batchId}/records`)
      ]);
      setBatch(bData);
      setRecords(rData || []);

      // Auto-select records marked as 'approved' or 'modified'
      const preSelected = new Set<number>();
      (rData || []).forEach(r => {
        if (r.review_status === "approved" || r.review_status === "modified") {
          preSelected.add(r.staged_id);
        }
      });
      setSelectedIds(preSelected);
    } catch (e) {
      console.error("Failed to load batch workbench:", e);
    } finally {
      setLoading(false);
    }
  };

  // Toggle review_status between approved and skipped
  const handleToggleStatus = async (record: StagedRecord) => {
    const nextStatus = record.review_status === "skipped" ? "approved" : "skipped";
    try {
      const updated = await apiFetch<StagedRecord>(`/import/batches/${batchId}/records/${record.staged_id}`, {
        method: "PATCH",
        body: JSON.stringify({ review_status: nextStatus })
      });
      setRecords(records.map(r => r.staged_id === record.staged_id ? updated : r));
      
      const nextSet = new Set(selectedIds);
      if (nextStatus === "approved") {
        nextSet.add(record.staged_id);
      } else {
        nextSet.delete(record.staged_id);
      }
      setSelectedIds(nextSet);
    } catch (err: any) {
      alert(err.message || "Failed to update status");
    }
  };

  const handleDeleteRecord = async (stagedId: number) => {
    if (!confirm("Are you sure you want to remove this staged record?")) return;
    try {
      await apiFetch(`/import/batches/${batchId}/records/${stagedId}`, { method: "DELETE" });
      setRecords(records.filter(r => r.staged_id !== stagedId));
      const nextSet = new Set(selectedIds);
      nextSet.delete(stagedId);
      setSelectedIds(nextSet);
    } catch (err: any) {
      alert(err.message || "Failed to delete record");
    }
  };

  // Bulk actions
  const handleBulkApproveNew = async () => {
    const newRecords = records.filter(r => r.match_status === "new");
    for (const r of newRecords) {
      if (r.review_status !== "approved") {
        await apiFetch(`/import/batches/${batchId}/records/${r.staged_id}`, {
          method: "PATCH",
          body: JSON.stringify({ review_status: "approved" })
        });
      }
    }
    loadBatchData();
  };

  const handleBulkSkipExact = async () => {
    const exactRecords = records.filter(r => r.match_status === "exact_match");
    for (const r of exactRecords) {
      if (r.review_status !== "skipped") {
        await apiFetch(`/import/batches/${batchId}/records/${r.staged_id}`, {
          method: "PATCH",
          body: JSON.stringify({ review_status: "skipped" })
        });
      }
    }
    loadBatchData();
  };

  // Final Green Flag commit
  const handleFinalGreenFlagCommit = async () => {
    try {
      setCommitting(true);
      const res = await apiFetch<any>(`/import/batches/${batchId}/commit`, {
        method: "POST",
        body: JSON.stringify({
          record_ids: Array.from(selectedIds)
        })
      });
      setCommitResult(res);
      setCommitting(false);
    } catch (err: any) {
      setCommitting(false);
      alert(err.message || "Commit failed");
    }
  };

  // Filtered records
  const filteredRecords = records.filter(r => {
    if (activeTab === "new") return r.match_status === "new";
    if (activeTab === "probable") return r.match_status === "probable_match";
    if (activeTab === "exact") return r.match_status === "exact_match";
    if (activeTab === "skipped") return r.review_status === "skipped";
    return true;
  });

  return (
    <div className="max-w-[1500px] mx-auto px-4 lg:px-8 py-8">
      {/* Top Breadcrumb & Nav */}
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500 mb-4">
        <Link href="/import" className="hover:text-slate-800 dark:hover:text-slate-200 flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Ingestion Dashboard</span>
        </Link>
        <span>/</span>
        <span className="text-slate-900 dark:text-white">Batch #{batchId}</span>
      </div>

      {/* Main Workbench Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-black text-slate-900 dark:text-white tracking-tight">
              {batch?.filename || `Batch #${batchId}`}
            </h1>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold ${
              batch?.status === "merged" 
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                : "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
            }`}>
              {batch?.status?.replaceAll("_", " ")}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Review parsed records, compare duplicates against your existing ledger, and provide the final green flag to merge.
          </p>
        </div>

        {/* Primary Action: The Final Green Flag Button */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-200 rounded-xl text-xs font-bold cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Row</span>
          </button>

          {batch?.status !== "merged" && (
            <button
              onClick={() => setIsCommitModalOpen(true)}
              disabled={selectedIds.size === 0}
              data-testid="final-green-flag-button"
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-extrabold text-xs shadow-md transition-all cursor-pointer ${
                selectedIds.size > 0
                  ? "bg-[#99EF2E] hover:bg-[#88DC20] text-slate-900 ring-2 ring-emerald-400/40"
                  : "bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
              }`}
            >
              <CheckCircle2 className="w-4 h-4 text-slate-900" />
              <span>Final Green Flag: Merge Selected ({selectedIds.size})</span>
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Total Extracted</span>
          <div className="text-2xl font-black text-slate-900 dark:text-white mt-1 tabular-nums">
            {records.length}
          </div>
        </div>

        <div className="bg-white dark:bg-[#0E1522] border border-emerald-200 dark:border-emerald-900/60 rounded-2xl p-4 bg-emerald-50/20">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">New Records</span>
          <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1 tabular-nums">
            {records.filter(r => r.match_status === "new").length}
          </div>
        </div>

        <div className="bg-white dark:bg-[#0E1522] border border-amber-200 dark:border-amber-900/60 rounded-2xl p-4 bg-amber-50/20">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-amber-600 dark:text-amber-400">Probable Matches (±2d)</span>
          <div className="text-2xl font-black text-amber-600 dark:text-amber-400 mt-1 tabular-nums">
            {records.filter(r => r.match_status === "probable_match").length}
          </div>
        </div>

        <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Exact Duplicates</span>
          <div className="text-2xl font-black text-slate-500 mt-1 tabular-nums">
            {records.filter(r => r.match_status === "exact_match").length}
          </div>
        </div>
      </div>

      {/* Tabs & Bulk Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        {/* Filter Tabs */}
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-900/60 p-1 rounded-xl border border-slate-200/60 dark:border-slate-800/60">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
              activeTab === "all" ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            All ({records.length})
          </button>
          <button
            onClick={() => setActiveTab("new")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
              activeTab === "new" ? "bg-white dark:bg-slate-800 text-emerald-600 shadow-xs" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            New ({records.filter(r => r.match_status === "new").length})
          </button>
          <button
            onClick={() => setActiveTab("probable")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
              activeTab === "probable" ? "bg-white dark:bg-slate-800 text-amber-600 shadow-xs" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            Probable ({records.filter(r => r.match_status === "probable_match").length})
          </button>
          <button
            onClick={() => setActiveTab("exact")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
              activeTab === "exact" ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            Exact ({records.filter(r => r.match_status === "exact_match").length})
          </button>
          <button
            onClick={() => setActiveTab("skipped")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
              activeTab === "skipped" ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            Skipped ({records.filter(r => r.review_status === "skipped").length})
          </button>
        </div>

        {/* Quick Bulk Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleBulkApproveNew}
            className="px-2.5 py-1.5 text-xs font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 rounded-lg hover:bg-emerald-100 cursor-pointer"
          >
            Approve All New
          </button>
          <button
            onClick={handleBulkSkipExact}
            className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 cursor-pointer"
          >
            Skip All Duplicates
          </button>
        </div>
      </div>

      {/* Interactive Staging Table */}
      <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                <th className="py-3 px-3 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={filteredRecords.length > 0 && filteredRecords.every(r => selectedIds.has(r.staged_id))}
                    onChange={(e) => {
                      const next = new Set(selectedIds);
                      if (e.target.checked) {
                        filteredRecords.forEach(r => next.add(r.staged_id));
                      } else {
                        filteredRecords.forEach(r => next.delete(r.staged_id));
                      }
                      setSelectedIds(next);
                    }}
                    className="rounded"
                  />
                </th>
                <th className="py-3 px-3">Date</th>
                <th className="py-3 px-3">Action</th>
                <th className="py-3 px-3">Asset / Category</th>
                <th className="py-3 px-3 text-right">Qty</th>
                <th className="py-3 px-3 text-right">Price</th>
                <th className="py-3 px-3 text-right">Total Amount</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Notes</th>
                <th className="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-medium">
              {filteredRecords.map((r) => {
                const isSelected = selectedIds.has(r.staged_id);
                return (
                  <tr 
                    key={r.staged_id} 
                    data-testid="staged-row"
                    className={`hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors ${
                      r.review_status === "skipped" ? "opacity-60 bg-slate-50/30 dark:bg-slate-900/20" : ""
                    }`}
                  >
                    {/* Checkbox */}
                    <td className="py-3 px-3 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          const next = new Set(selectedIds);
                          if (e.target.checked) next.add(r.staged_id);
                          else next.delete(r.staged_id);
                          setSelectedIds(next);
                        }}
                        className="rounded"
                      />
                    </td>

                    {/* Date */}
                    <td className="py-3 px-3 font-semibold text-slate-600 dark:text-slate-300 tabular-nums whitespace-nowrap">
                      {r.transaction_date}
                    </td>

                    {/* Action Type */}
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase ${
                        r.action_type === "buy" || r.action_type === "expense"
                          ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400"
                          : "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400"
                      }`}>
                        {r.action_type}
                      </span>
                    </td>

                    {/* Asset / Category */}
                    <td className="py-3 px-3 font-bold text-slate-900 dark:text-white">
                      {r.record_type === "investment" ? (
                        <div className="flex flex-col">
                          <span className="font-extrabold">{r.asset_symbol || r.asset_symbol_raw || "—"}</span>
                          {r.asset_name && <span className="text-[10px] text-slate-400 font-normal truncate max-w-[140px]">{r.asset_name}</span>}
                        </div>
                      ) : (
                        <span>{r.category_name || r.category_name_raw || "Uncategorized"}</span>
                      )}
                    </td>

                    {/* Quantity */}
                    <td className="py-3 px-3 text-right font-semibold tabular-nums text-slate-600 dark:text-slate-300">
                      {r.quantity ? formatQty(r.quantity) : "—"}
                    </td>

                    {/* Price */}
                    <td className="py-3 px-3 text-right font-semibold tabular-nums text-slate-600 dark:text-slate-300">
                      {r.price_per_unit ? formatMoney(r.price_per_unit, r.currency) : "—"}
                    </td>

                    {/* Total Amount */}
                    <td className="py-3 px-3 text-right font-bold tabular-nums text-slate-900 dark:text-white">
                      {formatMoney(r.total_amount, r.currency)}
                    </td>

                    {/* Match Status Badge */}
                    <td className="py-3 px-3">
                      {r.match_status === "exact_match" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          Exact Match
                        </span>
                      ) : r.match_status === "probable_match" ? (
                        <button
                          onClick={() => setComparingRecord(r)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 hover:underline cursor-pointer"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          <span>Probable Match</span>
                        </button>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                          New
                        </span>
                      )}
                    </td>

                    {/* Notes */}
                    <td className="py-3 px-3 text-slate-500 dark:text-slate-400 truncate max-w-[150px]">
                      {r.notes || "—"}
                    </td>

                    {/* Row Actions */}
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Compare button if match exists */}
                        {r.matched_entity_details && (
                          <button
                            onClick={() => setComparingRecord(r)}
                            title="Compare against existing ledger"
                            className="p-1 text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 rounded cursor-pointer"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Toggle Approve/Skip */}
                        <button
                          onClick={() => handleToggleStatus(r)}
                          title={r.review_status === "skipped" ? "Approve record" : "Skip record"}
                          className={`px-2 py-1 text-[11px] font-bold rounded cursor-pointer ${
                            r.review_status === "skipped" 
                              ? "bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-emerald-100 hover:text-emerald-700" 
                              : "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 hover:bg-rose-100 hover:text-rose-700"
                          }`}
                        >
                          {r.review_status === "skipped" ? "Skip" : "Approved"}
                        </button>

                        {/* Delete Row */}
                        <button
                          onClick={() => handleDeleteRecord(r.staged_id)}
                          title="Delete staged record"
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Side-by-Side Comparison Drawer / Modal */}
      {comparingRecord && comparingRecord.matched_entity_details && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                <h3 className="font-extrabold text-slate-900 dark:text-white text-base">
                  Side-by-Side Duplicate Comparison
                </h3>
              </div>
              <button 
                onClick={() => setComparingRecord(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 my-6 text-xs">
              {/* Left Column: Incoming Staged Record */}
              <div className="p-4 bg-emerald-50/40 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-800/60 rounded-xl">
                <span className="font-bold text-emerald-800 dark:text-emerald-300 uppercase text-[10px] tracking-wider block mb-3">
                  Incoming Document Record
                </span>
                <div className="space-y-2 font-medium text-slate-800 dark:text-slate-200">
                  <div><span className="text-slate-400">Date:</span> <strong className="tabular-nums">{comparingRecord.transaction_date}</strong></div>
                  <div><span className="text-slate-400">Asset:</span> <strong>{comparingRecord.asset_symbol_raw || comparingRecord.asset_symbol}</strong></div>
                  <div><span className="text-slate-400">Type:</span> <strong className="uppercase">{comparingRecord.action_type}</strong></div>
                  <div><span className="text-slate-400">Quantity:</span> <strong className="tabular-nums">{comparingRecord.quantity || "—"}</strong></div>
                  <div><span className="text-slate-400">Total:</span> <strong className="tabular-nums">{formatMoney(comparingRecord.total_amount, comparingRecord.currency)}</strong></div>
                  <div><span className="text-slate-400">Notes:</span> <span>{comparingRecord.notes || "—"}</span></div>
                </div>
              </div>

              {/* Right Column: Existing Live Transaction */}
              <div className="p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl">
                <span className="font-bold text-slate-500 uppercase text-[10px] tracking-wider block mb-3">
                  Existing Ledger Transaction
                </span>
                <div className="space-y-2 font-medium text-slate-800 dark:text-slate-200">
                  <div><span className="text-slate-400">Date:</span> <strong className="tabular-nums">{comparingRecord.matched_entity_details.transaction_date}</strong></div>
                  <div><span className="text-slate-400">Asset:</span> <strong>{comparingRecord.matched_entity_details.asset_symbol}</strong></div>
                  <div><span className="text-slate-400">Type:</span> <strong className="uppercase">{comparingRecord.matched_entity_details.transaction_type}</strong></div>
                  <div><span className="text-slate-400">Quantity:</span> <strong className="tabular-nums">{comparingRecord.matched_entity_details.quantity || "—"}</strong></div>
                  <div><span className="text-slate-400">Total:</span> <strong className="tabular-nums">{formatMoney(comparingRecord.matched_entity_details.total_amount, comparingRecord.currency)}</strong></div>
                  <div><span className="text-slate-400">Account:</span> <span>{comparingRecord.matched_entity_details.account_name}</span></div>
                </div>
              </div>
            </div>

            {comparingRecord.matched_entity_details.match_reason && (
              <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 font-semibold mb-6">
                <strong>Match Reason:</strong> {comparingRecord.matched_entity_details.match_reason}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => {
                  handleToggleStatus({ ...comparingRecord, review_status: "approved" });
                  setComparingRecord(null);
                }}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold cursor-pointer"
              >
                Skip Incoming (Keep Old)
              </button>
              <button
                onClick={() => {
                  handleToggleStatus({ ...comparingRecord, review_status: "skipped" });
                  setComparingRecord(null);
                }}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                Approve Both (Import as Separate)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Final Green Flag Confirmation Modal */}
      {isCommitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl">
            {commitResult ? (
              <div className="text-center py-4">
                <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-3">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="font-extrabold text-base text-slate-900 dark:text-white mb-2">
                  Portfolio Successfully Merged!
                </h3>
                <p className="text-xs text-slate-500 mb-6">
                  {commitResult.message}
                </p>
                <button
                  onClick={() => router.push("/investments/transactions")}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs cursor-pointer"
                >
                  View Transactions
                </button>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-5 h-5 text-emerald-600" />
                  <h3 className="font-extrabold text-base text-slate-900 dark:text-white">
                    Final Green Flag Merge
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mb-4">
                  You are about to merge <strong className="text-slate-900 dark:text-white">{selectedIds.size} approved transactions</strong> into your live portfolio ledger.
                </p>
                <div className="p-3 bg-slate-50 dark:bg-slate-900/40 rounded-xl border border-slate-200/60 dark:border-slate-800/60 text-xs space-y-1.5 mb-6">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Records to insert:</span>
                    <strong className="text-emerald-600">{selectedIds.size}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Skipped duplicates:</span>
                    <strong className="text-slate-400">{records.length - selectedIds.size}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">FIFO Lots & Net Worth:</span>
                    <strong className="text-blue-600">Auto-recalculated</strong>
                  </div>
                </div>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={() => setIsCommitModalOpen(false)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleFinalGreenFlagCommit}
                    disabled={committing}
                    className="px-5 py-2 bg-[#99EF2E] hover:bg-[#88DC20] text-slate-900 font-extrabold rounded-xl text-xs flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    {committing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    <span>Confirm & Merge</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
