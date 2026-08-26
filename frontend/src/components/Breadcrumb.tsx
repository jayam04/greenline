"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home, Layers, Receipt, FolderTree, BarChart3, TrendingUp, Settings, Building2 } from "lucide-react";

interface PathSegment {
  label: string;
  href?: string;
}

interface SiblingTab {
  label: string;
  href: string;
  icon?: React.ReactNode;
}

export function Breadcrumb() {
  const pathname = usePathname();

  if (pathname === "/login") return null;

  // 1. Build hierarchical path segments
  const pathSegments: PathSegment[] = [];
  let siblingTabs: SiblingTab[] = [];

  if (pathname === "/") {
    pathSegments.push({ label: "Net worth", href: "/" });
    pathSegments.push({ label: "Overview & Accounts" });
    siblingTabs = [
      { label: "Accounts", href: "/accounts", icon: <Building2 className="w-3 h-3" /> },
      { label: "Settings", href: "/settings", icon: <Settings className="w-3 h-3" /> },
    ];
  } else if (pathname.startsWith("/investments")) {
    pathSegments.push({ label: "Net worth", href: "/" });
    if (pathname === "/investments") {
      pathSegments.push({ label: "Investments" });
    } else {
      pathSegments.push({ label: "Investments", href: "/investments" });
      if (pathname === "/investments/holdings") {
        pathSegments.push({ label: "Holdings" });
      } else if (pathname === "/investments/transactions") {
        pathSegments.push({ label: "Transactions" });
      }
    }
    siblingTabs = [
      { label: "Overview", href: "/investments", icon: <BarChart3 className="w-3 h-3" /> },
      { label: "Holdings", href: "/investments/holdings", icon: <Layers className="w-3 h-3" /> },
      { label: "Transactions", href: "/investments/transactions", icon: <Receipt className="w-3 h-3" /> },
    ];
  } else if (pathname.startsWith("/cashflow") || pathname === "/categories") {
    pathSegments.push({ label: "Net worth", href: "/" });
    if (pathname === "/cashflow") {
      pathSegments.push({ label: "Cashflow" });
    } else {
      pathSegments.push({ label: "Cashflow", href: "/cashflow" });
      if (pathname === "/cashflow/transactions") {
        pathSegments.push({ label: "Transactions" });
      } else if (pathname === "/categories") {
        pathSegments.push({ label: "Categories" });
      }
    }
    siblingTabs = [
      { label: "Overview", href: "/cashflow", icon: <BarChart3 className="w-3 h-3" /> },
      { label: "Transactions", href: "/cashflow/transactions", icon: <Receipt className="w-3 h-3" /> },
      { label: "Categories", href: "/categories", icon: <FolderTree className="w-3 h-3" /> },
    ];
  } else if (pathname === "/accounts") {
    pathSegments.push({ label: "Net worth", href: "/" });
    pathSegments.push({ label: "Accounts & Master" });
  } else if (pathname === "/settings") {
    pathSegments.push({ label: "Net worth", href: "/" });
    pathSegments.push({ label: "Settings" });
  } else {
    pathSegments.push({ label: "Net worth", href: "/" });
    pathSegments.push({ label: pathname.replace("/", "").replace(/-/g, " ") });
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 lg:px-6 pt-3 pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs text-slate-500 dark:text-slate-400 bg-transparent transition-colors">
      {/* Left: Full Clickable Hierarchical Path */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 flex-wrap font-semibold">
        {pathSegments.map((seg, idx) => {
          const isLast = idx === pathSegments.length - 1;
          return (
            <React.Fragment key={idx}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-400 dark:text-slate-600 shrink-0" />}
              {seg.href && !isLast ? (
                <Link
                  href={seg.href}
                  className="text-slate-600 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white transition-colors flex items-center gap-1"
                >
                  {idx === 0 && <TrendingUp className="w-3.5 h-3.5 opacity-70" />}
                  <span>{seg.label}</span>
                </Link>
              ) : (
                <span className="font-bold text-[#0F172A] dark:text-white flex items-center gap-1">
                  {idx === 0 && <TrendingUp className="w-3.5 h-3.5 opacity-70" />}
                  <span>{seg.label}</span>
                </span>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      {/* Right: Sibling Sub-Pages Quick Navigation */}
      {siblingTabs.length > 0 && (
        <div className="flex items-center gap-1 bg-slate-200/60 dark:bg-slate-800/60 p-0.5 rounded-xl text-[11px] font-bold self-start sm:self-auto">
          {siblingTabs.map((tab) => {
            const isActive = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                  isActive
                    ? "bg-[#0F172A] dark:bg-white text-white dark:text-[#0F172A] shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
