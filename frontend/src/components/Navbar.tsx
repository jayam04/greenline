"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { removeAuthToken } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { 
  Search, TrendingUp, Briefcase, 
  Building2, LogOut, User, ChevronDown,
  ArrowLeftRight, Settings,
  Sun, Moon, Laptop
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close menus on route change
  useEffect(() => {
    setIsProfileOpen(false);
  }, [pathname]);

  if (pathname === "/login") return null;

  const isNetworthActive = pathname === "/";
  const isInvestmentsActive = pathname.startsWith("/investments");
  const isCashflowActive = pathname.startsWith("/cashflow") || pathname === "/categories";
  const isAccountsActive = pathname === "/accounts";

  const handleLogout = () => {
    setIsProfileOpen(false);
    removeAuthToken();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-50 bg-white dark:bg-[#0E1522] border-b border-[#E5E7EB] dark:border-[#1E293B] font-sans transition-colors">
      {/* Primary Top Bar */}
      <div className="max-w-[1600px] mx-auto px-4 lg:px-6 h-14 flex items-center justify-between gap-4">
        {/* Left: Brand Logo */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center group">
            <span className="font-black text-lg tracking-tight text-[#0F172A] lowercase bg-[#99EF2E] px-2 py-0.5 rounded-xs inline-block">
              greenline
            </span>
          </Link>
        </div>

        {/* Center: Search Bar */}
        <div className="flex-1 max-w-md hidden sm:block">
          <div className="relative flex items-center w-full">
            <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search for stocks, etfs or accounts..."
              className="w-full bg-[#F3F4F6] dark:bg-[#1A2333] hover:bg-[#EAEBED] dark:hover:bg-[#202B3F] focus:bg-white dark:focus:bg-[#151D2B] text-xs font-semibold text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 pl-9 pr-4 py-2 rounded-lg border border-transparent focus:border-slate-300 dark:focus:border-slate-700 focus:outline-none transition-all"
            />
          </div>
        </div>

        {/* Right: Nav Tabs & Profile */}
        <div className="flex items-center gap-1 sm:gap-2">
          <nav className="hidden lg:flex items-center gap-1 mr-2">
            {/* 1. Net worth */}
            <Link
              href="/"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                isNetworthActive
                  ? "text-[#0F172A] dark:text-white bg-slate-100 dark:bg-slate-800 font-extrabold"
                  : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Net worth</span>
            </Link>

            {/* 2. Investments */}
            <Link
              href="/investments"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                isInvestmentsActive
                  ? "text-[#0F172A] dark:text-white bg-slate-100 dark:bg-slate-800 font-extrabold"
                  : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
              }`}
            >
              <Briefcase className="w-3.5 h-3.5" />
              <span>Investments</span>
            </Link>

            {/* 3. Cashflow */}
            <Link
              href="/cashflow"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                isCashflowActive
                  ? "text-[#0F172A] dark:text-white bg-slate-100 dark:bg-slate-800 font-extrabold"
                  : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
              }`}
            >
              <ArrowLeftRight className="w-3.5 h-3.5" />
              <span>Cashflow</span>
            </Link>

            {/* 4. Accounts & Master */}
            <Link
              href="/accounts"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                isAccountsActive
                  ? "text-[#0F172A] dark:text-white bg-slate-100 dark:bg-slate-800 font-extrabold"
                  : "text-slate-500 dark:text-slate-400 hover:text-[#0F172A] dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60"
              }`}
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Accounts & Master</span>
            </Link>
          </nav>

          {/* Interactive Profile Dropdown Menu */}
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setIsProfileOpen(!isProfileOpen)}
              className="flex items-center gap-1.5 p-1 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
              title="User profile & settings"
            >
              <div className="w-7 h-7 bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 font-extrabold text-xs rounded-full flex items-center justify-center border border-slate-300 dark:border-slate-600">
                <User className="w-4 h-4" />
              </div>
              <ChevronDown className="w-3 h-3 text-slate-400 dark:text-slate-500" />
            </button>

            {isProfileOpen && (
              <div className="absolute right-0 top-10 z-50 bg-white dark:bg-[#121824] border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl py-2 w-56 text-xs font-semibold">
                {/* User Info Header */}
                <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">
                  <div className="font-bold text-[#0F172A] dark:text-white text-xs">Admin</div>
                  <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500">admin@greenline.local</div>
                </div>

                {/* Theme Selector Section */}
                <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5 px-1">
                    Theme
                  </div>
                  <div className="grid grid-cols-3 gap-1 bg-slate-100 dark:bg-[#1A2333] p-1 rounded-xl">
                    <button
                      onClick={() => setTheme("light")}
                      className={`flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                        theme === "light"
                          ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                      }`}
                      title="Light theme"
                    >
                      <Sun className="w-3.5 h-3.5" />
                      <span>Light</span>
                    </button>
                    <button
                      onClick={() => setTheme("dark")}
                      className={`flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                        theme === "dark"
                          ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                      }`}
                      title="Dark theme"
                    >
                      <Moon className="w-3.5 h-3.5" />
                      <span>Dark</span>
                    </button>
                    <button
                      onClick={() => setTheme("system")}
                      className={`flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                        theme === "system"
                          ? "bg-white dark:bg-slate-700 text-[#0F172A] dark:text-white shadow-xs"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                      }`}
                      title="System default"
                    >
                      <Laptop className="w-3.5 h-3.5" />
                      <span>Auto</span>
                    </button>
                  </div>
                </div>

                {/* Menu Options */}
                <div className="py-1">
                  <Link
                    href="/settings"
                    onClick={() => setIsProfileOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-[#0F172A] dark:hover:text-white transition-colors"
                  >
                    <Settings className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                    <span>Settings</span>
                  </Link>
                </div>

                <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors text-left cursor-pointer"
                  >
                    <LogOut className="w-4 h-4 text-rose-500 dark:text-rose-400" />
                    <span>Log out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
