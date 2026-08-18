"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { 
  Plus, Edit, Trash2, ChevronRight, ChevronDown, Folder, 
  FolderOpen, Tag, Sparkles, X, Layers, CheckCircle2 
} from "lucide-react";

interface CategoryTreeItem {
  category_id: number;
  parent_id?: number | null;
  name: string;
  category_type: string;
  default_label?: string | null;
  effective_label?: string | null;
  full_path?: string | null;
  level: number;
  icon?: string | null;
  color?: string | null;
  subcategories: CategoryTreeItem[];
}

interface FlatCategory {
  category_id: number;
  parent_id?: number | null;
  name: string;
  category_type: string;
  default_label?: string | null;
  effective_label?: string | null;
  full_path?: string | null;
  level: number;
}

const CLASSIFICATION_LABELS = [
  { key: "ESSENTIAL", label: "Essential (Need)" },
  { key: "DISCRETIONARY", label: "Discretionary (Want)" },
  { key: "LUXURY", label: "Luxury" },
  { key: "INVESTMENT", label: "Investment / Savings" },
];

export default function CategoriesPage() {
  const [tree, setTree] = useState<CategoryTreeItem[]>([]);
  const [flatCategories, setFlatCategories] = useState<FlatCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<{ [id: number]: boolean }>({});

  // Form State
  const [editingCategory, setEditingCategory] = useState<FlatCategory | null>(null);
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<number | "">("");
  const [categoryType, setCategoryType] = useState("EXPENSE");
  const [defaultLabel, setDefaultLabel] = useState<string>("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [treeData, flatData] = await Promise.all([
        apiFetch<CategoryTreeItem[]>("/categories/tree"),
        apiFetch<FlatCategory[]>("/categories"),
      ]);
      setTree(treeData || []);
      setFlatCategories(flatData || []);

      // Auto-expand level 1 and level 2 nodes
      const initialExpanded: { [id: number]: boolean } = {};
      (flatData || []).forEach((c) => {
        if (c.level <= 2) initialExpanded[c.category_id] = true;
      });
      setExpandedNodes(initialExpanded);
    } catch (e) {
      console.error("Failed to load categories:", e);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleEdit = (cat: FlatCategory) => {
    setEditingCategory(cat);
    setName(cat.name);
    setParentId(cat.parent_id ?? "");
    setCategoryType(cat.category_type);
    setDefaultLabel(cat.default_label || "");
  };

  const handleCancelEdit = () => {
    setEditingCategory(null);
    setName("");
    setParentId("");
    setCategoryType("EXPENSE");
    setDefaultLabel("");
    setError("");
  };

  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const payload = {
        name: name.trim(),
        parent_id: parentId ? Number(parentId) : null,
        category_type: categoryType.toUpperCase(),
        default_label: defaultLabel || null,
      };

      if (editingCategory) {
        await apiFetch(`/categories/${editingCategory.category_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/categories", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      handleCancelEdit();
      loadData();
    } catch (err: any) {
      setError(err.message || "Failed to save category");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCategory = async (id: number) => {
    if (!confirm("Are you sure you want to delete this category? Subcategories must be deleted first.")) return;
    try {
      await apiFetch(`/categories/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete category");
    }
  };

  const renderTreeNode = (node: CategoryTreeItem) => {
    const hasChildren = node.subcategories && node.subcategories.length > 0;
    const isExpanded = !!expandedNodes[node.category_id];
    const isExplicit = !!node.default_label;
    const effLabel = node.effective_label || node.default_label || "DISCRETIONARY";

    const badgeColor =
      effLabel === "ESSENTIAL"
        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
        : effLabel === "LUXURY"
        ? "bg-pink-50 text-pink-700 border-pink-200"
        : effLabel === "INVESTMENT"
        ? "bg-blue-50 text-blue-700 border-blue-200"
        : "bg-amber-50 text-amber-700 border-amber-200";

    return (
      <div key={node.category_id} className="space-y-1">
        <div 
          className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 border border-transparent hover:border-slate-100 transition-all text-xs"
          style={{ paddingLeft: `${(node.level - 1) * 20 + 8}px` }}
        >
          <div className="flex items-center gap-2">
            {hasChildren ? (
              <button
                type="button"
                onClick={() => toggleExpand(node.category_id)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded cursor-pointer"
              >
                {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            ) : (
              <div className="w-5" />
            )}

            <div className="flex items-center gap-1.5 font-bold text-[#0F172A]">
              {hasChildren ? (
                isExpanded ? <FolderOpen className="w-3.5 h-3.5 text-amber-500" /> : <Folder className="w-3.5 h-3.5 text-amber-500" />
              ) : (
                <Tag className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>{node.name}</span>
            </div>

            <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-slate-100 text-slate-500 rounded">
              L{node.level}
            </span>

            <span className={`px-1.5 py-0.2 text-[9px] font-extrabold uppercase rounded border ${badgeColor}`}>
              {effLabel} {!isExplicit && <span className="opacity-60 text-[8px]">(Inherited)</span>}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => handleEdit(node)}
              className="p-1 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 cursor-pointer"
              title="Edit Category"
            >
              <Edit className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleDeleteCategory(node.category_id)}
              className="p-1 text-rose-400 hover:text-rose-600 rounded hover:bg-rose-50 cursor-pointer"
              title="Delete Category"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {hasChildren && isExpanded && (
          <div className="space-y-1">
            {node.subcategories.map((sub) => renderTreeNode(sub))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Category Hierarchy & Classification
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Organize up to 5 levels of income & spend categories with automatic label inheritance
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left 2 Cols: Interactive Category Tree */}
        <div className="lg:col-span-2 getquin-card p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-600" />
              <span>Hierarchical Category Tree ({flatCategories.length})</span>
            </h2>
            <div className="flex items-center gap-2 text-[11px] font-bold text-slate-400">
              <span>Depths 1 to 5</span>
            </div>
          </div>

          <div className="space-y-1 max-h-[700px] overflow-y-auto pr-1">
            {tree.map((rootNode) => renderTreeNode(rootNode))}
          </div>
        </div>

        {/* Right 1 Col: Add / Edit Form */}
        <div className="getquin-card p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-sm font-bold text-[#0F172A]">
              {editingCategory ? "Edit Category" : "Add New Category"}
            </h2>
            {editingCategory && (
              <button
                onClick={handleCancelEdit}
                className="text-xs font-bold text-rose-600 flex items-center gap-1 hover:underline cursor-pointer"
              >
                <X className="w-3.5 h-3.5" /> Cancel
              </button>
            )}
          </div>

          {error && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold rounded-lg">
              {error}
            </div>
          )}

          <form onSubmit={handleSaveCategory} className="space-y-3 text-xs">
            <div>
              <label className="block text-slate-600 font-semibold mb-1">Category Name</label>
              <input
                type="text"
                placeholder="e.g. Electric Vehicle Charging, Spotify"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-slate-600 font-semibold mb-1">Parent Category (Optional)</label>
              <select
                value={parentId}
                onChange={(e) => setParentId(Number(e.target.value) || "")}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none cursor-pointer"
              >
                <option value="">None (Top-Level Root)</option>
                {flatCategories
                  .filter((c) => !editingCategory || c.category_id !== editingCategory.category_id)
                  .map((c) => (
                    <option key={c.category_id} value={c.category_id}>
                      {c.full_path || c.name} (L{c.level})
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-600 font-semibold mb-1">Category Type</label>
              <select
                value={categoryType}
                onChange={(e) => setCategoryType(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none uppercase"
              >
                <option value="EXPENSE">Expense</option>
                <option value="INCOME">Income</option>
                <option value="INVESTMENT">Investment</option>
                <option value="TRANSFER">Transfer</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-600 font-semibold mb-1">
                Default Classification Label
              </label>
              <select
                value={defaultLabel}
                onChange={(e) => setDefaultLabel(e.target.value)}
                className="w-full bg-[#F3F4F6] text-slate-900 font-semibold rounded-lg px-3 py-2 border border-transparent focus:outline-none"
              >
                <option value="">Inherit from Parent Category</option>
                {CLASSIFICATION_LABELS.map((lbl) => (
                  <option key={lbl.key} value={lbl.key}>
                    {lbl.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full btn-pill-black justify-center py-2 text-xs cursor-pointer disabled:opacity-50 mt-2"
            >
              {saving ? "Saving..." : (editingCategory ? "Update Category" : "Create Category")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
