"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { 
  Plus, Edit, Trash2, ChevronRight, ChevronDown, Folder, 
  FolderOpen, Tag, Sparkles, X, Layers, CheckCircle2,
  FolderPlus, Search, Calendar, ChevronUp, Columns
} from "lucide-react";
import { formatCurrency } from "@/lib/format";
import { TimelineKey, TIMELINE_OPTIONS, getTimelineDateRange } from "@/lib/dateUtils";
import { CategoryModal, FlatCategory } from "@/components/CategoryModal";

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

export default function CategoriesPage() {
  const [tree, setTree] = useState<CategoryTreeItem[]>([]);
  const [flatCategories, setFlatCategories] = useState<FlatCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<{ [id: number]: boolean }>({});
  const [searchQuery, setSearchQuery] = useState("");

  const [masterCurrency, setMasterCurrency] = useState<string>("EUR");

  // Dynamic Timeline Columns
  const [activeColumns, setActiveColumns] = useState<TimelineKey[]>(["THIS_MONTH", "LAST_MONTH"]);
  const [isManageColumnsModalOpen, setIsManageColumnsModalOpen] = useState(false);
  const [tempActiveColumns, setTempActiveColumns] = useState<TimelineKey[]>([]);
  const [columnTotals, setColumnTotals] = useState<{ [timelineKey: string]: { [categoryId: string]: number } }>({});

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<FlatCategory | null>(null);
  const [parentPresetId, setParentPresetId] = useState<number | null>(null);

  useEffect(() => {
    document.title = "Categories · greenline";
    const savedCols = typeof window !== "undefined" ? localStorage.getItem("greenline_active_columns") : null;
    if (savedCols) {
      try {
        const parsed = JSON.parse(savedCols);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setActiveColumns(parsed);
        }
      } catch (e) {
        console.error("Failed to parse saved active columns", e);
      }
    }
    loadCategoryData();
  }, []);

  useEffect(() => {
    loadAllColumnTotals();
  }, [activeColumns, masterCurrency]);

  const loadCategoryData = async () => {
    try {
      setLoading(true);
      const [treeData, flatData, settingsRes] = await Promise.all([
        apiFetch<CategoryTreeItem[]>("/categories/tree"),
        apiFetch<FlatCategory[]>("/categories"),
        apiFetch<{ master_currency: string }>("/settings").catch(() => null),
      ]);
      setTree(treeData || []);
      setFlatCategories(flatData || []);
      if (settingsRes?.master_currency) {
        setMasterCurrency(settingsRes.master_currency.trim().toUpperCase());
      } else {
        const localCurr = (typeof window !== "undefined" && localStorage.getItem("greenline_master_currency")) || "EUR";
        setMasterCurrency(localCurr);
      }

      // Load expanded state from localStorage or auto-expand level 1 & 2
      const savedState = typeof window !== "undefined" ? localStorage.getItem("greenline_categories_expanded") : null;
      if (savedState) {
        try {
          setExpandedNodes(JSON.parse(savedState));
        } catch(e) {
          console.error("Failed to parse saved expanded state", e);
        }
      } else {
        const initialExpanded: { [id: number]: boolean } = {};
        (flatData || []).forEach((c) => {
          if (c.level <= 2) initialExpanded[c.category_id] = true;
        });
        setExpandedNodes(initialExpanded);
      }
    } catch (e) {
      console.error("Failed to load categories:", e);
    } finally {
      setLoading(false);
    }
  };

  const loadAllColumnTotals = async () => {
    for (const key of activeColumns) {
      loadTotalsForTimeline(key);
    }
  };

  const loadTotalsForTimeline = async (key: TimelineKey) => {
    try {
      const { startDate, endDate } = getTimelineDateRange(key);
      const queryParams = new URLSearchParams();
      if (startDate) queryParams.append("start_date", startDate);
      if (endDate) queryParams.append("end_date", endDate);
      queryParams.append("master_currency", masterCurrency);
      const qs = queryParams.toString() ? `?${queryParams.toString()}` : "";

      const totals = await apiFetch<{ [categoryId: string]: number }>(`/categories/totals${qs}`);
      setColumnTotals((prev) => ({ ...prev, [key]: totals || {} }));
    } catch (e) {
      console.error(`Failed to load totals for ${key}:`, e);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedNodes((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem("greenline_categories_expanded", JSON.stringify(next));
      return next;
    });
  };

  const handleExpandAll = () => {
    const all: { [id: number]: boolean } = {};
    flatCategories.forEach((c) => {
      all[c.category_id] = true;
    });
    setExpandedNodes(all);
    localStorage.setItem("greenline_categories_expanded", JSON.stringify(all));
  };

  const handleCollapseAll = () => {
    setExpandedNodes({});
    localStorage.setItem("greenline_categories_expanded", JSON.stringify({}));
  };

  const handleOpenAdd = (parentId?: number) => {
    setEditingCategory(null);
    setParentPresetId(parentId ?? null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (cat: FlatCategory) => {
    setEditingCategory(cat);
    setParentPresetId(null);
    setIsModalOpen(true);
  };

  const handleDeleteCategory = async (id: number) => {
    if (!confirm("Are you sure you want to delete this category? (Subcategories and used categories cannot be deleted)")) return;
    try {
      await apiFetch(`/categories/${id}`, { method: "DELETE" });
      loadCategoryData();
      // Reload totals
      setColumnTotals({});
      loadAllColumnTotals();
    } catch (err: any) {
      alert(err.message || "Failed to delete category");
    }
  };

  // Filter tree by search query
  const matchesSearch = (node: CategoryTreeItem): boolean => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    if (node.name.toLowerCase().includes(q)) return true;
    return (node.subcategories || []).some((sub) => matchesSearch(sub));
  };

  const renderTreeRows = (node: CategoryTreeItem): React.ReactNode => {
    if (!matchesSearch(node)) return null;

    const hasChildren = node.subcategories && node.subcategories.length > 0;
    const isExpanded = !!expandedNodes[node.category_id];
    const effLabel = node.effective_label || node.default_label || "DISCRETIONARY";
    const dotColor =
      effLabel === "ESSENTIAL" ? "bg-emerald-500"
        : effLabel === "LUXURY" ? "bg-pink-500"
        : effLabel === "INVESTMENT" ? "bg-blue-500"
        : "bg-amber-500";

    return (
      <React.Fragment key={node.category_id}>
        <tr className="hover:bg-slate-50/80 transition-colors border-b border-slate-100 group">
          {/* Column 1: Category Name with Tree Indentation */}
          <td className="py-2.5 pl-1 pr-3">
            <div 
              className="flex items-center gap-1.5"
              style={{ paddingLeft: `${(node.level - 1) * 22}px` }}
            >
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => toggleExpand(node.category_id)}
                  className="p-1 text-slate-400 hover:text-slate-700 rounded cursor-pointer"
                >
                  {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
              ) : (
                <span className="w-5.5" />
              )}

              {hasChildren ? (
                isExpanded ? <FolderOpen className="w-3.5 h-3.5 text-blue-500 shrink-0" /> : <Folder className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              ) : (
                <Tag className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              )}

              <div className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} title={`Classification: ${effLabel}`} />

              <span className={`text-xs font-bold text-[#0F172A] ${node.level === 1 ? "text-[13px]" : ""}`}>
                {node.name}
              </span>

              {hasChildren && (
                <span className="text-[10px] text-slate-400 font-semibold ml-1">
                  ({node.subcategories.length})
                </span>
              )}
            </div>
          </td>

          {/* Dynamic Timeline Totals Columns */}
          {activeColumns.map((colKey) => {
            const aggAmount = columnTotals[colKey]?.[String(node.category_id)] || 0;
            let displayAmount = aggAmount;

            if (isExpanded && hasChildren) {
              const childrenSum = node.subcategories.reduce(
                (sum, child) => sum + (columnTotals[colKey]?.[String(child.category_id)] || 0),
                0
              );
              displayAmount = aggAmount - childrenSum;
            }

            const amountColor = node.category_type === "INCOME"
              ? "text-emerald-600 font-bold"
              : (node.category_type === "EXPENSE" || displayAmount < -0.001)
              ? "text-rose-600 font-bold"
              : "text-[#0F172A]";

            return (
              <td key={colKey} className="py-2.5 px-3 text-right tabular-nums font-semibold text-xs">
                {Math.abs(displayAmount) > 0.001 ? (
                  <span className={amountColor}>
                    {formatCurrency(displayAmount, masterCurrency)}
                  </span>
                ) : (
                  <span className="text-slate-300">-</span>
                )}
              </td>
            );
          })}

          {/* Spacer to absorb extra width */}
          <td className="w-full"></td>

          {/* Column Actions */}
          <td className="py-2.5 pl-8 pr-3 text-right whitespace-nowrap">
            <div className="flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => handleOpenAdd(node.category_id)}
                className="p-1 text-slate-400 hover:text-blue-600 rounded hover:bg-blue-50 cursor-pointer"
                title="Add Subcategory"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleOpenEdit(node)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 cursor-pointer"
                title="Edit Category"
              >
                <Edit className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleDeleteCategory(node.category_id)}
                className="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 cursor-pointer"
                title="Delete Category"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </td>
        </tr>

        {/* Recursive Child Rows */}
        {hasChildren && isExpanded && node.subcategories.map((sub) => renderTreeRows(sub))}
      </React.Fragment>
    );
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-6 py-5 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F5F9]">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">
            Category Hierarchy & Comparative Spends
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">
            Organize up to 5 levels of taxonomy with dynamic timeline comparative analysis
          </p>
        </div>

        {/* Header Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Search Input */}
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search category name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[#F3F4F6] text-xs font-semibold text-slate-800 placeholder-slate-400 pl-8 pr-3 py-1.5 rounded-lg border border-transparent focus:border-slate-300 focus:bg-white focus:outline-none w-52"
            />
          </div>

          {/* Expand / Collapse Controls */}
          <div className="flex items-center bg-[#F1F5F9] p-1 rounded-xl text-xs font-bold">
            <button
              onClick={handleExpandAll}
              className="px-2.5 py-1 text-slate-600 hover:text-black rounded-lg transition-all cursor-pointer"
            >
              Expand All
            </button>
            <button
              onClick={handleCollapseAll}
              className="px-2.5 py-1 text-slate-600 hover:text-black rounded-lg transition-all cursor-pointer"
            >
              Collapse All
            </button>
          </div>

          {/* Add New Category Button */}
          <button
            onClick={() => handleOpenAdd()}
            className="btn-pill-black text-xs cursor-pointer shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Category</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* FULL-WIDTH TABULAR CATEGORY TREE                         */}
      {/* ======================================================== */}
      <div className="getquin-card p-5 space-y-4 w-full">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-600" />
              <span>Category Taxonomy & Spend Aggregates ({flatCategories.length} Categories)</span>
            </h2>
            <p className="text-[11px] font-medium text-slate-400">
              Totals include direct transactions plus all child subcategories
            </p>
          </div>

          {/* Manage Columns Button in Toolbar */}
          <div className="relative">
            <button
              onClick={() => {
                setTempActiveColumns([...activeColumns]);
                setIsManageColumnsModalOpen(true);
              }}
              className="btn-pill-gray text-xs cursor-pointer flex items-center gap-1.5"
              title="Manage timeline comparison columns"
            >
              <Columns className="w-3.5 h-3.5 text-blue-600" />
              <span>Manage Columns</span>
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 text-[11px] font-bold uppercase tracking-wider">
                <th className="pb-2.5 pl-1 pr-3 font-bold min-w-[280px]">Category Hierarchy</th>

                {/* Dynamic Timeline Headers */}
                {activeColumns.map((colKey, idx) => {
                  const opt = TIMELINE_OPTIONS.find((o) => o.key === colKey);
                  return (
                    <th key={colKey} className="pb-2.5 px-3 font-bold text-right min-w-[120px]">
                      {opt?.label || colKey}
                    </th>
                  );
                })}

                {/* Spacer to absorb extra width so data columns stay compact to the left */}
                <th className="w-full"></th>

                <th className="pb-2.5 pl-8 pr-3 font-bold text-right w-24">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {tree.map((rootNode) => renderTreeRows(rootNode))}

              {tree.length === 0 && !loading && (
                <tr>
                  <td colSpan={3 + activeColumns.length} className="py-8 text-center text-slate-400 font-medium text-xs">
                    No categories found. Click &quot;Add Category&quot; to create one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manage Columns Modal */}
      {isManageColumnsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white w-full max-w-sm rounded-2xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-[#0F172A]">Manage Timeline Columns</h3>
              <button
                onClick={() => setIsManageColumnsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-3 max-h-[60vh] overflow-y-auto">
              {TIMELINE_OPTIONS.map((opt) => {
                const isSelected = tempActiveColumns.includes(opt.key);
                return (
                  <label key={opt.key} className="flex items-center gap-3 p-3 border border-slate-100 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors group">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setTempActiveColumns([...tempActiveColumns, opt.key]);
                        } else {
                          if (tempActiveColumns.length <= 1) return; // Prevent removing all
                          setTempActiveColumns(tempActiveColumns.filter((k) => k !== opt.key));
                        }
                      }}
                      className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer"
                    />
                    <span className="text-sm font-semibold text-slate-700 group-hover:text-[#0F172A] transition-colors">{opt.label}</span>
                  </label>
                );
              })}
              <p className="text-[11px] text-slate-500 font-medium pt-2">
                Select the timeline periods you want to compare side-by-side. At least one column must be active.
              </p>
            </div>
            <div className="px-5 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-2">
              <button
                onClick={() => setIsManageColumnsModalOpen(false)}
                className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const newlyAdded = tempActiveColumns.filter((key) => !activeColumns.includes(key));
                  setActiveColumns(tempActiveColumns);
                  localStorage.setItem("greenline_active_columns", JSON.stringify(tempActiveColumns));
                  newlyAdded.forEach((key) => loadTotalsForTimeline(key));
                  setIsManageColumnsModalOpen(false);
                }}
                className="px-4 py-2 text-xs font-bold bg-[#0F172A] text-white rounded-lg hover:bg-slate-800 transition-all shadow-sm cursor-pointer"
              >
                Apply Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Category Add & Edit Modal */}
      <CategoryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          loadCategoryData();
          setColumnTotals({});
          loadAllColumnTotals();
        }}
        categories={flatCategories}
        initialData={editingCategory}
        parentPresetId={parentPresetId}
      />
    </div>
  );
}
