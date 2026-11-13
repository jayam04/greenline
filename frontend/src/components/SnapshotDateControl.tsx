"use client";

import React, { useState, useEffect, useRef } from "react";
import { Calendar, ChevronDown, Check, Sparkles, Clock } from "lucide-react";

export type SnapshotStartMode = "auto" | "manual";

export interface SnapshotDateControlProps {
  onChange?: (startDate: string | null, mode: SnapshotStartMode) => void;
  className?: string;
  variant?: "popover" | "inline";
}

export function getPresetDate(preset: "sep1" | "ytd" | "fy" | "1y"): string {
  const now = new Date();
  const currentYear = now.getFullYear();

  switch (preset) {
    case "sep1": {
      const sep1ThisYear = new Date(currentYear, 8, 1);
      const year = now >= sep1ThisYear ? currentYear : currentYear - 1;
      return `${year}-09-01`;
    }
    case "ytd": {
      return `${currentYear}-01-01`;
    }
    case "fy": {
      const apr1ThisYear = new Date(currentYear, 3, 1);
      const year = now >= apr1ThisYear ? currentYear : currentYear - 1;
      return `${year}-04-01`;
    }
    case "1y": {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 1);
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }
  }
}

export function SnapshotDateControl({
  onChange,
  className = "",
  variant = "popover",
}: SnapshotDateControlProps) {
  const [mode, setMode] = useState<SnapshotStartMode>("auto");
  const [startDate, setStartDate] = useState<string>(() => getPresetDate("sep1"));
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const savedMode = localStorage.getItem("greenline_snapshot_start_mode") as SnapshotStartMode | null;
      const savedDate = localStorage.getItem("greenline_snapshot_start_date");

      if (savedMode === "manual") {
        setMode("manual");
        const dateVal = savedDate || getPresetDate("sep1");
        setStartDate(dateVal);
      } else {
        setMode("auto");
      }
    } catch {
      // Ignore localStorage unavailable in some environments
    }
  }, []);

  // Close popover when clicking outside
  useEffect(() => {
    if (variant !== "popover" || !isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, variant]);

  const handleSelectMode = (newMode: SnapshotStartMode) => {
    setMode(newMode);
    try {
      localStorage.setItem("greenline_snapshot_start_mode", newMode);
    } catch {
      // Ignore
    }

    if (newMode === "auto") {
      onChange?.(null, "auto");
    } else {
      const activeDate = startDate || getPresetDate("sep1");
      setStartDate(activeDate);
      try {
        localStorage.setItem("greenline_snapshot_start_date", activeDate);
      } catch {
        // Ignore
      }
      onChange?.(activeDate, "manual");
    }
  };

  const handlePresetClick = (presetKey: "sep1" | "ytd" | "fy" | "1y") => {
    const newDate = getPresetDate(presetKey);
    setMode("manual");
    setStartDate(newDate);
    try {
      localStorage.setItem("greenline_snapshot_start_mode", "manual");
      localStorage.setItem("greenline_snapshot_start_date", newDate);
    } catch {
      // Ignore
    }
    onChange?.(newDate, "manual");
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    setStartDate(newDate);
    try {
      localStorage.setItem("greenline_snapshot_start_date", newDate);
    } catch {
      // Ignore
    }
    if (mode === "manual") {
      onChange?.(newDate, "manual");
    }
  };

  const getTriggerLabel = () => {
    if (mode === "auto") {
      return "Start: Auto";
    }
    // Format friendly label if matching a preset
    const currentYear = new Date().getFullYear();
    if (startDate === `${currentYear}-09-01` || startDate === `${currentYear - 1}-09-01`) {
      return `Start: Sep 1 (${startDate})`;
    }
    return `Start: ${startDate}`;
  };

  const controlContent = (
    <div className="space-y-3 p-1">
      {/* Auto vs Manual Mode Switcher */}
      <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 dark:bg-slate-800/60 rounded-xl text-xs font-semibold">
        <button
          type="button"
          onClick={() => handleSelectMode("auto")}
          className={`flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg transition-all cursor-pointer ${
            mode === "auto"
              ? "bg-white dark:bg-[#1E293B] text-[#0F172A] dark:text-white shadow-xs font-bold"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
          <span>Auto</span>
          {mode === "auto" && <Check className="w-3 h-3 text-emerald-500" />}
        </button>

        <button
          type="button"
          onClick={() => handleSelectMode("manual")}
          className={`flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg transition-all cursor-pointer ${
            mode === "manual"
              ? "bg-white dark:bg-[#1E293B] text-[#0F172A] dark:text-white shadow-xs font-bold"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <Clock className="w-3.5 h-3.5 text-purple-500" />
          <span>Manual</span>
          {mode === "manual" && <Check className="w-3 h-3 text-purple-500" />}
        </button>
      </div>

      <p className="text-[11px] text-slate-500 dark:text-slate-400">
        {mode === "auto"
          ? "Calculates weekly snapshots starting from your earliest recorded balance."
          : "Filters weekly net worth snapshots from a custom baseline date."}
      </p>

      {/* Manual Date Selection & Quick Presets */}
      <div className={`space-y-2.5 pt-1 border-t border-slate-100 dark:border-slate-800 ${mode === "auto" ? "opacity-60 pointer-events-none" : ""}`}>
        <div className="flex flex-col gap-1">
          <label htmlFor="snapshot-start-date-input" className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
            Start Date
          </label>
          <input
            id="snapshot-start-date-input"
            aria-label="Start date"
            type="date"
            value={startDate}
            onChange={handleDateChange}
            className="w-full px-2.5 py-1.5 text-xs font-medium bg-white dark:bg-[#151D2B] border border-slate-200 dark:border-slate-700 rounded-lg text-[#0F172A] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#99EF2E]"
          />
        </div>

        {/* Quick Presets */}
        <div>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 block mb-1.5">
            Quick Presets
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => handlePresetClick("sep1")}
              className={`px-2 py-1.5 text-[11px] font-semibold rounded-lg border text-left transition-all cursor-pointer ${
                startDate === getPresetDate("sep1")
                  ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10 text-[#0F172A] dark:text-white"
                  : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-[#151D2B] text-slate-700 dark:text-slate-300"
              }`}
            >
              Sep 1
            </button>
            <button
              type="button"
              onClick={() => handlePresetClick("ytd")}
              className={`px-2 py-1.5 text-[11px] font-semibold rounded-lg border text-left transition-all cursor-pointer ${
                startDate === getPresetDate("ytd")
                  ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10 text-[#0F172A] dark:text-white"
                  : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-[#151D2B] text-slate-700 dark:text-slate-300"
              }`}
            >
              Jan 1 (YTD)
            </button>
            <button
              type="button"
              onClick={() => handlePresetClick("fy")}
              className={`px-2 py-1.5 text-[11px] font-semibold rounded-lg border text-left transition-all cursor-pointer ${
                startDate === getPresetDate("fy")
                  ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10 text-[#0F172A] dark:text-white"
                  : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-[#151D2B] text-slate-700 dark:text-slate-300"
              }`}
            >
              Apr 1 (Fiscal)
            </button>
            <button
              type="button"
              onClick={() => handlePresetClick("1y")}
              className={`px-2 py-1.5 text-[11px] font-semibold rounded-lg border text-left transition-all cursor-pointer ${
                startDate === getPresetDate("1y")
                  ? "border-[#0F172A] dark:border-white bg-[#0F172A]/5 dark:bg-white/10 text-[#0F172A] dark:text-white"
                  : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-[#151D2B] text-slate-700 dark:text-slate-300"
              }`}
            >
              1 Year Ago
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  if (variant === "inline") {
    return (
      <div className={`p-4 bg-white dark:bg-[#151D2B] border border-slate-200 dark:border-slate-800 rounded-xl ${className}`}>
        {controlContent}
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      <button
        type="button"
        aria-label="Snapshot starting date"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-[#151D2B] hover:bg-slate-50 dark:hover:bg-[#1E293B] text-slate-700 dark:text-slate-200 shadow-xs transition-all cursor-pointer"
      >
        <Calendar className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
        <span>{getTriggerLabel()}</span>
        <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-72 p-3 bg-white dark:bg-[#151D2B] border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg z-50">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-slate-800">
            <span className="text-xs font-bold text-[#0F172A] dark:text-white">
              Snapshot Starting Date
            </span>
          </div>
          {controlContent}
        </div>
      )}
    </div>
  );
}

export default SnapshotDateControl;
