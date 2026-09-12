"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, getAuthToken } from "@/lib/api";
import { 
  Sparkles, UploadCloud, FileText, ArrowRight, CheckCircle2, 
  AlertCircle, Lock, ChevronDown, ChevronUp, Clock, RefreshCw, Plus
} from "lucide-react";

interface Account {
  account_id: number;
  account_name: string;
  currency: string;
}

interface ImportBatch {
  batch_id: number;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  target_account_name?: string | null;
  default_currency: string;
  total_records: number;
  new_records: number;
  exact_matches: number;
  probable_matches: number;
  created_at: string;
  error_message?: string | null;
}

export default function ImportDashboardPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // File Upload Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [targetAccountId, setTargetAccountId] = useState<string>("");
  const [defaultCurrency, setDefaultCurrency] = useState("USD");
  const [customInstructions, setCustomInstructions] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    document.title = "AI Document Ingestion · greenline";
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const [batchData, accountData] = await Promise.all([
        apiFetch<ImportBatch[]>("/import/batches"),
        apiFetch<Account[]>("/accounts")
      ]);
      setBatches(batchData || []);
      setAccounts(accountData || []);
    } catch (err: any) {
      console.error("Failed to load import batches:", err);
      setErrorMsg(err.message || "Failed to load import batches");
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg("Please select a document or statement to upload.");
      return;
    }

    try {
      setUploading(true);
      setErrorMsg(null);

      const formData = new FormData();
      formData.append("file", selectedFile);
      if (password.trim()) formData.append("password", password.trim());
      if (targetAccountId) formData.append("target_account_id", targetAccountId);
      formData.append("default_currency", defaultCurrency);
      if (customInstructions.trim()) formData.append("custom_instructions", customInstructions.trim());

      const token = getAuthToken();
      const res = await fetch("http://localhost:8000/api/v1/import/upload", {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with HTTP ${res.status}`);
      }

      const createdBatch: ImportBatch = await res.json();
      router.push(`/import/${createdBatch.batch_id}`);
    } catch (err: any) {
      console.error("Upload error:", err);
      setErrorMsg(err.message || "Failed to process and stage document");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto px-4 lg:px-8 py-8">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-950/60 rounded-xl text-emerald-600 dark:text-emerald-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              AI Document Ingestion & Staging
            </h1>
          </div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
            Upload broker statements, trade books, bank statements, or receipts. AI parses them into an interactive staging area for your final green flag review.
          </p>
        </div>

        <button
          onClick={loadData}
          className="self-start md:self-auto flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {errorMsg && (
        <div className="mb-6 p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-xs font-bold text-rose-700 dark:text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Upload Wizard Card */}
      <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 mb-10 shadow-xs">
        <form onSubmit={handleUpload}>
          <div className="flex items-center gap-2 text-sm font-extrabold text-slate-900 dark:text-white mb-4">
            <UploadCloud className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>Upload New Document</span>
          </div>

          {/* File Dropzone Area */}
          <div 
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              selectedFile 
                ? "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20" 
                : "border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600 bg-slate-50/50 dark:bg-slate-900/30"
            }`}
          >
            <input 
              ref={fileInputRef} 
              type="file" 
              accept=".pdf,.csv,.xlsx,.xls,.tsv" 
              className="hidden" 
              onChange={handleFileChange} 
            />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-1.5">
                <FileText className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
                <span className="text-sm font-bold text-slate-900 dark:text-white">{selectedFile.name}</span>
                <span className="text-xs text-slate-500">{Math.round(selectedFile.size / 1024)} KB</span>
                <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 mt-1">Click to change file</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="p-3 bg-slate-100 dark:bg-slate-800 rounded-full text-slate-600 dark:text-slate-400">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <span className="text-sm font-bold text-slate-800 dark:text-slate-200">
                  Drag & drop statement or click to browse
                </span>
                <span className="text-xs text-slate-400">
                  Supports PDF (broker & bank statements, CAS), CSV, Excel (XLSX, XLS), TSV
                </span>
              </div>
            )}
          </div>

          {/* Additional File Information Accordion */}
          <div className="mt-6 border-t border-slate-100 dark:border-slate-800/80 pt-4">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer"
            >
              <span>Additional Document Information & Prompt Instructions</span>
              {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 p-4 bg-slate-50 dark:bg-slate-900/40 rounded-xl border border-slate-200/60 dark:border-slate-800/60 text-xs">
                {/* PDF Password */}
                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1">
                    <Lock className="w-3 h-3 text-slate-400" />
                    <span>PDF Password (if encrypted)</span>
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="e.g. PAN + DOB for CAS"
                    className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-[10px] text-slate-400 mt-0.5 block">Used in-memory only to decrypt statement.</span>
                </div>

                {/* Target Account Override */}
                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Target Account (Optional Default)
                  </label>
                  <select
                    value={targetAccountId}
                    onChange={(e) => setTargetAccountId(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Auto-detect from statement</option>
                    {accounts.map((a) => (
                      <option key={a.account_id} value={a.account_id}>
                        {a.account_name} ({a.currency})
                      </option>
                    ))}
                  </select>
                  <span className="text-[10px] text-slate-400 mt-0.5 block">Assigns transactions to this account if unspecified.</span>
                </div>

                {/* Currency Override */}
                <div>
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Default Currency
                  </label>
                  <select
                    value={defaultCurrency}
                    onChange={(e) => setDefaultCurrency(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CAD">CAD ($)</option>
                  </select>
                </div>

                {/* Custom AI Instructions */}
                <div className="md:col-span-3">
                  <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Custom AI Parsing Instructions & Categorization Hints
                  </label>
                  <textarea
                    rows={2}
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    placeholder="e.g. 'Categorize Swiggy as Food & Dining', 'Transactions before 2024 are already reconciled so ignore them', 'Treat bonus shares with 0 cost'."
                    className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Submit Action */}
          <div className="mt-6 flex justify-end">
            <button
              type="submit"
              disabled={!selectedFile || uploading}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs cursor-pointer transition-all ${
                uploading || !selectedFile
                  ? "bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm hover:shadow"
              }`}
            >
              {uploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Parsing & Staging Document...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Parse & Stage with AI</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Recent Import Batches Table */}
      <div className="bg-white dark:bg-[#0E1522] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-sm font-extrabold text-slate-900 dark:text-white">
            <Clock className="w-4 h-4 text-slate-400" />
            <span>Previous Ingestion Batches</span>
          </div>
          <span className="text-xs font-bold text-slate-400">{batches.length} batches</span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-slate-400">Loading import history...</div>
        ) : batches.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            No documents ingested yet. Upload a statement above to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-3">Batch ID</th>
                  <th className="py-3 px-3">Filename</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3 text-right">Extracted</th>
                  <th className="py-3 px-3 text-right">New</th>
                  <th className="py-3 px-3 text-right">Matches</th>
                  <th className="py-3 px-3">Date</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-medium">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-3 font-bold text-slate-500">#{b.batch_id}</td>
                    <td className="py-3 px-3 font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-slate-400" />
                      <span className="truncate max-w-[200px]">{b.filename}</span>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                        b.status === "merged" 
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                          : b.status === "ready_for_review"
                          ? "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                          : b.status === "failed"
                          ? "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
                          : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
                      }`}>
                        {b.status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-bold tabular-nums">{b.total_records}</td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                      {b.new_records}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-amber-600 dark:text-amber-400 tabular-nums">
                      {b.exact_matches + b.probable_matches}
                    </td>
                    <td className="py-3 px-3 text-slate-500 tabular-nums">{b.created_at.slice(0, 10)}</td>
                    <td className="py-3 px-3 text-right">
                      <Link
                        href={`/import/${b.batch_id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 dark:hover:bg-emerald-950/80 rounded-lg transition-colors"
                      >
                        <span>{b.status === "merged" ? "View Batch" : "Review & Merge"}</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
