"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { X, FolderPlus, Edit, AlertCircle, CheckCircle2 } from "lucide-react";

export interface FlatCategory {
  category_id: number;
  parent_id?: number | null;
  name: string;
  category_type: string;
  default_label?: string | null;
  effective_label?: string | null;
  full_path?: string | null;
  level: number;
}

interface CategoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  categories: FlatCategory[];
  initialData?: FlatCategory | null;
  parentPresetId?: number | null;
}

const CLASSIFICATION_LABELS = [
  { key: "ESSENTIAL", label: "Essential (Need)" },
  { key: "DISCRETIONARY", label: "Discretionary (Want)" },
  { key: "LUXURY", label: "Luxury" },
  { key: "INVESTMENT", label: "Investment / Savings" },
];

export function CategoryModal({
  isOpen,
  onClose,
  onSuccess,
  categories,
  initialData,
  parentPresetId,
}: CategoryModalProps) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<number | "">("");
  const [categoryType, setCategoryType] = useState("EXPENSE");
  const [defaultLabel, setDefaultLabel] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen) {
      setError("");
      if (initialData) {
        setName(initialData.name);
        setParentId(initialData.parent_id ?? "");
        setCategoryType(initialData.category_type);
        setDefaultLabel(initialData.default_label || "");
      } else {
        setName("");
        setParentId(parentPresetId ?? "");
        if (parentPresetId) {
          const parent = categories.find((c) => c.category_id === parentPresetId);
          if (parent) {
            setCategoryType(parent.category_type);
            setDefaultLabel(parent.default_label || "");
          }
        } else {
          setCategoryType("EXPENSE");
          setDefaultLabel("DISCRETIONARY");
        }
      }
    }
  }, [isOpen, initialData, parentPresetId, categories]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter a category name.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const payload = {
        name: name.trim(),
        parent_id: parentId ? Number(parentId) : null,
        category_type: categoryType,
        default_label: defaultLabel || null,
      };

      if (initialData) {
        await apiFetch(`/categories/${initialData.category_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/categories", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save category");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2.5 mb-4">
          <div className="p-2 bg-[#0F172A] text-white rounded-xl">
            {initialData ? <Edit className="w-4 h-4" /> : <FolderPlus className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">
              {initialData ? "Edit Category" : "Add New Category"}
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              {initialData ? "Modify category configuration and parent relation" : "Create a root or sub-level category in your hierarchy"}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-3.5 p-2.5 bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Category Name */}
          <div>
            <label className="block font-semibold text-slate-600 mb-1">
              Category Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Groceries, Streaming Services, Base Salary"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
              required
            />
          </div>

          {/* Parent Category */}
          <div>
            <label className="block font-semibold text-slate-600 mb-1">
              Parent Category (Optional for Root Level)
            </label>
            <select
              value={parentId}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : "";
                setParentId(val);
                if (val) {
                  const parent = categories.find((c) => c.category_id === val);
                  if (parent) {
                    setCategoryType(parent.category_type);
                    if (parent.effective_label) setDefaultLabel(parent.effective_label);
                  }
                }
              }}
              className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none cursor-pointer"
            >
              <option value="">None (Top-Level Root Category)</option>
              {categories
                .filter((c) => !initialData || c.category_id !== initialData.category_id)
                .map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.full_path || c.name} ({c.category_type})
                  </option>
                ))}
            </select>
          </div>

          {/* Category Type */}
          <div>
            <label className="block font-semibold text-slate-600 mb-1">Category Type</label>
            <div className="grid grid-cols-4 gap-1.5 p-1 bg-[#F1F5F9] rounded-xl text-xs font-bold">
              {["EXPENSE", "INCOME", "INVESTMENT", "TRANSFER"].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setCategoryType(t)}
                  className={`py-1.5 rounded-lg text-center transition-all cursor-pointer text-[11px] ${
                    categoryType === t
                      ? "bg-white text-[#0F172A] shadow-xs"
                      : "text-slate-500 hover:text-black"
                  }`}
                >
                  {t.charAt(0) + t.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Default Label */}
          <div>
            <label className="block font-semibold text-slate-600 mb-1">
              Default Classification Label (Inherited by subcategories)
            </label>
            <select
              value={defaultLabel}
              onChange={(e) => setDefaultLabel(e.target.value)}
              className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none cursor-pointer"
            >
              <option value="">Inherit from Parent / None</option>
              {CLASSIFICATION_LABELS.map((lbl) => (
                <option key={lbl.key} value={lbl.key}>
                  {lbl.label}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="mt-5 flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill-gray text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-pill-black text-xs disabled:opacity-50 cursor-pointer"
            >
              {loading ? "Saving..." : (initialData ? "Update Category" : "Save Category")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
