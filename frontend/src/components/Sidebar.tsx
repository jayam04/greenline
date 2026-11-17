"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth0 } from "@auth0/auth0-react";
import { removeAuthToken } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import {
  Home,
  PieChart,
  Briefcase,
  Receipt,
  Scale,
  AlertCircle,
  ArrowLeftRight,
  List,
  Tags,
  Landmark,
  Settings,
  LogOut,
  Sun,
  Moon,
  Laptop,
  Menu,
  X,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  count?: number;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

const groups: NavGroup[] = [
  {
    items: [{ href: "/", label: "Home", icon: Home }],
  },
  {
    label: "Investing",
    items: [
      { href: "/investments", label: "Portfolio", icon: PieChart },
      { href: "/investments/holdings", label: "Holdings", icon: Briefcase },
      { href: "/investments/transactions", label: "Trades", icon: Receipt },
      { href: "/investments/valuations", label: "Valuations", icon: Scale },
      { href: "/investments/discrepancies", label: "Reconcile", icon: AlertCircle },
    ],
  },
  {
    label: "Cashflow",
    items: [
      { href: "/cashflow", label: "Income & spend", icon: ArrowLeftRight },
      { href: "/cashflow/transactions", label: "Transactions", icon: List },
      { href: "/categories", label: "Categories", icon: Tags },
    ],
  },
  {
    label: "Manage",
    items: [
      { href: "/accounts", label: "Accounts", icon: Landmark },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href;
}

function getInitials(name?: string | null, email?: string | null): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }
  if (email && email.trim()) {
    return email.slice(0, 2).toUpperCase();
  }
  return "GL";
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { user, isAuthenticated, logout } = useAuth0();

  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close mobile sidebar on navigation
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    removeAuthToken();
    if (isAuthenticated) {
      logout({
        logoutParams: {
          returnTo: typeof window !== "undefined" ? window.location.origin : undefined,
        },
      });
    } else {
      router.push("/login");
    }
  };

  const displayName = (isAuthenticated && user?.name) ? user.name : (user?.email || "Admin");
  const displayEmail = (isAuthenticated && user?.email) ? user.email : "admin@greenline.local";
  const initials = getInitials(user?.name, user?.email);

  const sidebarBody = (onNavigate?: () => void) => (
    <div className="flex h-full flex-col bg-white dark:bg-[#0E1522] border-r border-[#E5E7EB] dark:border-[#1E293B]">
      {/* Brand Header */}
      <div className="px-5 pb-3 pt-4 shrink-0">
        <Link
          href="/"
          onClick={onNavigate}
          className="inline-block rounded-xs bg-[#99EF2E] px-2.5 py-1 text-base font-black tracking-tight text-[#0F172A] lowercase transition-transform active:scale-95"
        >
          greenline
        </Link>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-2" aria-label="Main Navigation">
        {groups.map((group, groupIndex) => (
          <div key={groupIndex}>
            {group.label && (
              <div className="px-3 mb-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                {group.label}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-3 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      active
                        ? "bg-slate-100 dark:bg-slate-800 text-[#0F172A] dark:text-white font-semibold"
                        : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-[#0F172A] dark:hover:text-white"
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1">{item.label}</span>
                    {item.count !== undefined && (
                      <span className="rounded-full bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-300">
                        {item.count}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User Profile & Theme Controls */}
      <div className="border-t border-[#E5E7EB] dark:border-[#1E293B] p-3 shrink-0">
        <div className="flex items-center gap-3 px-1">
          {isAuthenticated && user?.picture ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={user.picture}
              alt={displayName}
              className="w-8 h-8 rounded-full object-cover border border-slate-300 dark:border-slate-600 shrink-0"
            />
          ) : (
            <div className="grid w-8 h-8 place-items-center rounded-full bg-[#99EF2E] text-xs font-bold text-[#0F172A] shrink-0">
              {initials}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold text-slate-900 dark:text-white">
              {displayName}
            </div>
            <div className="truncate text-[10px] text-slate-500 dark:text-slate-400">
              {displayEmail}
            </div>
          </div>
          <Link
            href="/settings"
            onClick={onNavigate}
            aria-label="Settings"
            title="Settings"
            className="rounded-lg p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
          >
            <Settings className="w-4 h-4" />
          </Link>
        </div>

        {/* Sleeker theme mode toggle & red logout button in same row */}
        <div className="mt-2.5 flex items-center justify-between gap-2 px-1">
          <div className="inline-flex rounded-full bg-slate-100 dark:bg-slate-800/80 p-0.5" role="group" aria-label="Theme mode">
            <button
              aria-label="Light mode"
              title="Light mode"
              onClick={() => setTheme("light")}
              className={`rounded-full p-1.5 transition-colors ${
                mounted && theme === "light"
                  ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                  : "text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <Sun className="w-3.5 h-3.5" />
            </button>
            <button
              aria-label="Dark mode"
              title="Dark mode"
              onClick={() => setTheme("dark")}
              className={`rounded-full p-1.5 transition-colors ${
                mounted && theme === "dark"
                  ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                  : "text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <Moon className="w-3.5 h-3.5" />
            </button>
            <button
              aria-label="System mode"
              title="System mode"
              onClick={() => setTheme("system")}
              className={`rounded-full p-1.5 transition-colors ${
                mounted && theme === "system"
                  ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                  : "text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <Laptop className="w-3.5 h-3.5" />
            </button>
          </div>

          <button
            onClick={handleLogout}
            aria-label="Log out"
            title="Log out"
            className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors shrink-0"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Top Header */}
      <div className="lg:hidden sticky top-0 z-50 bg-white dark:bg-[#0E1522] border-b border-[#E5E7EB] dark:border-[#1E293B] flex items-center justify-between px-4 h-14">
        <Link href="/" className="inline-block rounded-xs bg-[#99EF2E] px-2.5 py-1 text-base font-black tracking-tight text-[#0F172A] lowercase">
          greenline
        </Link>
        <button
          onClick={() => setIsMobileOpen(true)}
          aria-label="Open navigation menu"
          className="p-2 -mr-2 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Mobile Sidebar Overlay Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-[60] lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/50 transition-opacity"
            onClick={() => setIsMobileOpen(false)}
          />
          <aside className="relative flex flex-col w-72 max-w-[calc(100%-3rem)] h-full z-10 shadow-2xl">
            <button
              onClick={() => setIsMobileOpen(false)}
              aria-label="Close navigation menu"
              className="absolute top-3 -right-12 p-2 text-white/80 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
            {sidebarBody(() => setIsMobileOpen(false))}
          </aside>
        </div>
      )}

      {/* Desktop Sidebar (Fixed Left) */}
      <aside className="hidden lg:flex w-64 flex-col fixed inset-y-0 z-50">
        {sidebarBody()}
      </aside>
    </>
  );
}
