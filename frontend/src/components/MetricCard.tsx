import React from "react";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
}: MetricCardProps) {
  const getTrendBadge = () => {
    if (!trendValue) return null;
    if (trend === "up") {
      return (
        <span className="px-2 py-0.5 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
          +{trendValue}
        </span>
      );
    }
    if (trend === "down") {
      return (
        <span className="px-2 py-0.5 text-xs font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-full">
          {trendValue}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-xs font-medium text-slate-400 bg-slate-800 rounded-full">
        {trendValue}
      </span>
    );
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700/80 transition-all">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">{title}</span>
        <div className="p-2 bg-slate-800 text-slate-300 rounded-lg">
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between gap-2">
        <span className="text-2xl font-bold tracking-tight text-white">{value}</span>
        {getTrendBadge()}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
    </div>
  );
}
