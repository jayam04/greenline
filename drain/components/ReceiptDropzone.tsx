'use client';

import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { SpendItem } from '@/lib/types';

interface ReceiptDropzoneProps {
  onReceiptProcessed?: (items: SpendItem[]) => void;
}

export function ReceiptDropzone({ onReceiptProcessed }: ReceiptDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedResult, setUploadedResult] = useState<{
    items: SpendItem[];
    geminiUsed: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadedResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/spends/receipt', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to process receipt');
      }

      const data = await res.json();
      setUploadedResult(data);

      if (onReceiptProcessed && data.items) {
        onReceiptProcessed(data.items);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Error processing receipt';
      setError(message);
    } finally {
      setUploading(false);
    }
  }

  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }

  return (
    <div className="w-full space-y-4">
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer
          transition-all
          ${
            dragActive
              ? 'border-emerald-500 bg-emerald-950/20'
              : 'border-zinc-800 bg-zinc-900/60 hover:border-zinc-700 hover:bg-zinc-900'
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,application/pdf"
          onChange={e => {
            if (e.target.files && e.target.files[0]) {
              handleFile(e.target.files[0]);
            }
          }}
          className="hidden"
        />

        <div className="w-12 h-12 rounded-2xl bg-zinc-800 text-zinc-300 flex items-center justify-center mb-3">
          {uploading ? (
            <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
          ) : (
            <Upload className="w-6 h-6 text-emerald-400" />
          )}
        </div>

        <h3 className="text-base font-semibold text-zinc-100">
          {uploading ? 'Extracting spend with Gemini Vision...' : 'Upload receipt, bill, or invoice'}
        </h3>
        <p className="text-xs text-zinc-400 mt-1 max-w-sm">
          Drag and drop your receipt image (PNG, JPG, WEBP) or click to browse. Gemini will itemize, extract the total, and categorize each expense.
        </p>

        <div className="mt-4 flex items-center gap-2 text-[11px] text-zinc-500">
          <FileText className="w-3.5 h-3.5" />
          <span>Supports PNG, JPG, WEBP, PDF up to 10MB</span>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {uploadedResult && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 to-zinc-900 border border-emerald-500/30 text-zinc-200 text-sm">
          <div className="flex items-center gap-2 font-medium text-emerald-400 mb-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>
              Successfully processed {uploadedResult.items.length} item(s) from receipt!
            </span>
          </div>

          <div className="space-y-1.5 mt-2">
            {uploadedResult.items.map(item => (
              <div
                key={item.id}
                className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded bg-zinc-800/80 border border-zinc-700/50"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-zinc-200">{item.merchant}</span>
                  <span className="text-zinc-400">• {item.item}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300">
                    {item.category}
                  </span>
                </div>
                <span className="font-bold text-emerald-400">
                  ${Number(item.amount).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
