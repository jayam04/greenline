"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { removeAuthToken } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { 
  TrendingUp, Briefcase, Building2, LogOut, User,
  ArrowLeftRight, Settings, Sparkles, Sun, Moon, Laptop,
  ChevronDown, Menu, Search, X
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  
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
    router.push("/login");
  };

  const navItems = [
    {
      name: "Overview",
      href: "/",
      icon: TrendingUp,
      active: pathname === "/",
    },
    {
      name: "Investments",
      href: "/investments",
      icon: Briefcase,
      active: pathname === "/investments",
      subItems: [
        { name: "Holdings", href: "/investments/holdings", active: pathname === "/investments/holdings" },
        { name: "Transactions", href: "/investments/transactions", active: pathname === "/investments/transactions" },
        { name: "Valuations", href: "/investments/valuations", active: pathname === "/investments/valuations" },
        { name: "Discrepancies", href: "/investments/discrepancies", active: pathname === "/investments/discrepancies" },
      ]
    },
    {
      name: "Cashflows",
      href: "/cashflow",
      icon: ArrowLeftRight,
      active: pathname === "/cashflow",
      subItems: [
        { name: "Transactions", href: "/cashflow/transactions", active: pathname === "/cashflow/transactions" },
        { name: "Categories", href: "/categories", active: pathname === "/categories" },
      ]
    },
    {
      name: "Accounts & Master",
      href: "/accounts",
      icon: Building2,
      active: pathname === "/accounts",
    },
    {
      name: "AI Import",
      href: "/import",
      icon: Sparkles,
      active: pathname.startsWith("/import"),
      className: "text-emerald-600 dark:text-emerald-400"
    }
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-white dark:bg-[#0E1522] border-r border-[#E5E7EB] dark:border-[#1E293B]">
      <div className="px-6 py-5 flex items-center">
        <Link href="/" className="flex items-center group">
          <span className="font-black text-lg tracking-tight text-[#0F172A] lowercase bg-[#99EF2E] px-2 py-0.5 rounded-xs inline-block">
            greenline
          </span>
        </Link>
      </div>

      <div className="px-4 pb-4">
        <div className="relative flex items-center w-full">
          <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search..."
            className="w-full bg-[#F3F4F6] dark:bg-[#1A2333] hover:bg-[#EAEBED] dark:hover:bg-[#202B3F] focus:bg-white dark:focus:bg-[#151D2B] text-xs font-semibold text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 pl-9 pr-4 py-2 rounded-lg border border-transparent focus:border-slate-300 dark:focus:border-slate-700 focus:outline-none transition-all"
          />
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 space-y-1">
        {navItems.map((item) => (
          <div key={item.name}>
            <Link
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-bold transition-colors ${
                item.active
                  ? "bg-slate-100 dark:bg-slate-800 text-[#0F172A] dark:text-white"
                  : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
              }`}
            >
              <item.icon className={`w-4 h-4 ${item.className || ""}`} />
              <span className={item.className || ""}>{item.name}</span>
            </Link>
            {item.subItems && (
              <div className="mt-1 space-y-1 mb-2">
                {item.subItems.map((sub) => (
                  <Link
                    key={sub.name}
                    href={sub.href}
                    className={`flex items-center gap-2 px-3 py-1.5 pl-10 rounded-lg text-xs font-semibold transition-colors ${
                      sub.active
                        ? "bg-slate-100 dark:bg-slate-800 text-[#0F172A] dark:text-white"
                        : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
                    }`}
                  >
                    {sub.name}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-[#E5E7EB] dark:border-[#1E293B]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 font-extrabold text-xs rounded-full flex items-center justify-center border border-slate-300 dark:border-slate-600">
              <User className="w-4 h-4" />
            </div>
            <div className="text-xs">
              <div className="font-bold text-[#0F172A] dark:text-white">Admin</div>
              <div className="text-[10px] text-slate-500">admin@greenline.local</div>
            </div>
          </div>
          <Link href="/settings" className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors">
            <Settings className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-3 gap-1 bg-slate-100 dark:bg-[#1A2333] p-1 rounded-xl mb-3">
          <button onClick={() => setTheme("light")} className={`flex justify-center py-1.5 rounded-lg transition-colors ${mounted && theme === "light" ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-900"}`}>
            <Sun className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setTheme("dark")} className={`flex justify-center py-1.5 rounded-lg transition-colors ${mounted && theme === "dark" ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-900"}`}>
            <Moon className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setTheme("system")} className={`flex justify-center py-1.5 rounded-lg transition-colors ${mounted && theme === "system" ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs" : "text-slate-500 hover:text-slate-900"}`}>
            <Laptop className="w-3.5 h-3.5" />
          </button>
        </div>

        <button onClick={handleLogout} className="w-full flex items-center justify-center gap-2 py-2 text-xs font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors">
          <LogOut className="w-4 h-4" />
          <span>Log out</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Top Bar */}
      <div className="lg:hidden sticky top-0 z-50 bg-white dark:bg-[#0E1522] border-b border-[#E5E7EB] dark:border-[#1E293B] flex items-center justify-between px-4 h-14">
        <Link href="/" className="flex items-center group">
          <span className="font-black text-lg tracking-tight text-[#0F172A] lowercase bg-[#99EF2E] px-2 py-0.5 rounded-xs inline-block">
            greenline
          </span>
        </Link>
        <button onClick={() => setIsMobileOpen(true)} className="p-2 -mr-2 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100">
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-[60] lg:hidden flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => setIsMobileOpen(false)} />
          <div className="relative flex flex-col w-72 max-w-[calc(100%-3rem)] h-full">
            <button onClick={() => setIsMobileOpen(false)} className="absolute top-3 -right-12 p-2 text-white/70 hover:text-white">
              <X className="w-6 h-6" />
            </button>
            {sidebarContent}
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 flex-col fixed inset-y-0 z-50">
        {sidebarContent}
      </aside>
    </>
  );
}
