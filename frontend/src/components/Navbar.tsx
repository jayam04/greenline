"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { removeAuthToken } from "@/lib/api";
import { 
  Search, TrendingUp, Briefcase, Receipt, 
  Building2, LogOut, User, ChevronDown,
  ArrowLeftRight, FolderTree, Settings, Layers
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();

  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isInvestmentsOpen, setIsInvestmentsOpen] = useState(false);
  const [isCashflowOpen, setIsCashflowOpen] = useState(false);

  const profileRef = useRef<HTMLDivElement>(null);
  const investmentsRef = useRef<HTMLDivElement>(null);
  const cashflowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
      if (investmentsRef.current && !investmentsRef.current.contains(event.target as Node)) {
        setIsInvestmentsOpen(false);
      }
      if (cashflowRef.current && !cashflowRef.current.contains(event.target as Node)) {
        setIsCashflowOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close menus on route change
  useEffect(() => {
    setIsInvestmentsOpen(false);
    setIsCashflowOpen(false);
    setIsProfileOpen(false);
  }, [pathname]);

  if (pathname === "/login") return null;

  const isNetworthActive = pathname === "/";
  const isInvestmentsActive = pathname === "/investments" || pathname === "/holdings" || pathname === "/transactions";
  const isCashflowActive = pathname === "/cashflow" || pathname === "/categories";
  const isAccountsActive = pathname === "/accounts";

  const handleLogout = () => {
    setIsProfileOpen(false);
    removeAuthToken();
    router.push("/login");
  };

  const getBreadcrumb = () => {
    if (pathname === "/") return "Net worth > Overview & Accounts";
    if (pathname === "/investments") return "Investments > Portfolio Dashboard";
    if (pathname === "/holdings") return "Investments > Positions & Holdings";
    if (pathname === "/transactions") return "Investments > Transaction Ledger";
    if (pathname === "/cashflow") return "Cashflow > Income, Spends & Sankey Flow";
    if (pathname === "/categories") return "Cashflow > Category Hierarchy & Labels";
    if (pathname === "/accounts") return "Master > Accounts & Securities Master";
    if (pathname === "/settings") return "Settings > Preferences & Configuration";
    return "Net worth > Overview";
  };

  return (
    <header className="sticky top-0 z-50 bg-[#FFFFFF] border-b border-[#E5E7EB] font-sans">
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
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search for stocks, etfs or accounts..."
              className="w-full bg-[#F3F4F6] hover:bg-[#EAEBED] focus:bg-white text-xs font-semibold text-slate-800 placeholder-slate-400 pl-9 pr-4 py-2 rounded-lg border border-transparent focus:border-slate-300 focus:outline-none transition-all"
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
                  ? "text-[#0F172A] bg-slate-100 font-extrabold"
                  : "text-slate-500 hover:text-[#0F172A] hover:bg-slate-50"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Net worth</span>
            </Link>

            {/* 2. Investments (with Dropdown) */}
            <div className="relative" ref={investmentsRef}>
              <div
                className={`flex items-center rounded-lg transition-colors ${
                  isInvestmentsActive
                    ? "bg-slate-100 font-extrabold text-[#0F172A]"
                    : "text-slate-500 hover:text-[#0F172A] hover:bg-slate-50"
                }`}
              >
                <Link
                  href="/investments"
                  className="flex items-center gap-1.5 pl-3 pr-1 py-1.5 text-xs font-bold"
                >
                  <Briefcase className="w-3.5 h-3.5" />
                  <span>Investments</span>
                </Link>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setIsInvestmentsOpen(!isInvestmentsOpen);
                    setIsCashflowOpen(false);
                  }}
                  className="px-1.5 py-2 hover:text-[#0F172A] cursor-pointer rounded-r-lg transition-colors"
                  title="Investments menu"
                >
                  <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isInvestmentsOpen ? "rotate-180" : ""}`} />
                </button>
              </div>

              {/* Investments Dropdown Menu */}
              {isInvestmentsOpen && (
                <div className="absolute left-0 top-10 z-50 bg-white border border-slate-200 rounded-xl shadow-xl py-1.5 w-48 text-xs font-semibold">
                  <Link
                    href="/holdings"
                    onClick={() => setIsInvestmentsOpen(false)}
                    className={`flex items-center gap-2.5 px-3.5 py-2 hover:bg-slate-50 transition-colors ${
                      pathname === "/holdings" ? "text-blue-600 font-bold bg-blue-50/50" : "text-slate-700 hover:text-[#0F172A]"
                    }`}
                  >
                    <Layers className="w-4 h-4 text-slate-400" />
                    <div>
                      <div className="font-bold">Holdings</div>
                      <div className="text-[10px] text-slate-400 font-normal">Positions & weights</div>
                    </div>
                  </Link>
                  <Link
                    href="/transactions"
                    onClick={() => setIsInvestmentsOpen(false)}
                    className={`flex items-center gap-2.5 px-3.5 py-2 hover:bg-slate-50 transition-colors ${
                      pathname === "/transactions" ? "text-blue-600 font-bold bg-blue-50/50" : "text-slate-700 hover:text-[#0F172A]"
                    }`}
                  >
                    <Receipt className="w-4 h-4 text-slate-400" />
                    <div>
                      <div className="font-bold">Transactions</div>
                      <div className="text-[10px] text-slate-400 font-normal">Trade ledger & history</div>
                    </div>
                  </Link>
                </div>
              )}
            </div>

            {/* 3. Cashflow (Renamed from Income & Spends, with Dropdown) */}
            <div className="relative" ref={cashflowRef}>
              <div
                className={`flex items-center rounded-lg transition-colors ${
                  isCashflowActive
                    ? "bg-slate-100 font-extrabold text-[#0F172A]"
                    : "text-slate-500 hover:text-[#0F172A] hover:bg-slate-50"
                }`}
              >
                <Link
                  href="/cashflow"
                  className="flex items-center gap-1.5 pl-3 pr-1 py-1.5 text-xs font-bold"
                >
                  <ArrowLeftRight className="w-3.5 h-3.5" />
                  <span>Cashflow</span>
                </Link>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setIsCashflowOpen(!isCashflowOpen);
                    setIsInvestmentsOpen(false);
                  }}
                  className="px-1.5 py-2 hover:text-[#0F172A] cursor-pointer rounded-r-lg transition-colors"
                  title="Cashflow menu"
                >
                  <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isCashflowOpen ? "rotate-180" : ""}`} />
                </button>
              </div>

              {/* Cashflow Dropdown Menu */}
              {isCashflowOpen && (
                <div className="absolute left-0 top-10 z-50 bg-white border border-slate-200 rounded-xl shadow-xl py-1.5 w-48 text-xs font-semibold">
                  <Link
                    href="/categories"
                    onClick={() => setIsCashflowOpen(false)}
                    className={`flex items-center gap-2.5 px-3.5 py-2 hover:bg-slate-50 transition-colors ${
                      pathname === "/categories" ? "text-emerald-600 font-bold bg-emerald-50/50" : "text-slate-700 hover:text-[#0F172A]"
                    }`}
                  >
                    <FolderTree className="w-4 h-4 text-slate-400" />
                    <div>
                      <div className="font-bold">Categories</div>
                      <div className="text-[10px] text-slate-400 font-normal">Hierarchy & labels</div>
                    </div>
                  </Link>
                </div>
              )}
            </div>

            {/* 4. Accounts & Master */}
            <Link
              href="/accounts"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                isAccountsActive
                  ? "text-[#0F172A] bg-slate-100 font-extrabold"
                  : "text-slate-500 hover:text-[#0F172A] hover:bg-slate-50"
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
              className="flex items-center gap-1.5 p-1 rounded-full hover:bg-slate-100 transition-colors cursor-pointer border border-transparent hover:border-slate-200"
              title="User profile & settings"
            >
              <div className="w-7 h-7 bg-slate-200 text-slate-800 font-extrabold text-xs rounded-full flex items-center justify-center border border-slate-300">
                <User className="w-4 h-4" />
              </div>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            {isProfileOpen && (
              <div className="absolute right-0 top-10 z-50 bg-white border border-slate-200 rounded-2xl shadow-xl py-2 w-52 text-xs font-semibold">
                {/* User Info Header */}
                <div className="px-4 py-2 border-b border-slate-100">
                  <div className="font-bold text-[#0F172A] text-xs">Admin</div>
                  <div className="text-[11px] font-medium text-slate-400">admin@greenline.local</div>
                </div>

                {/* Menu Options */}
                <div className="py-1">
                  <Link
                    href="/settings"
                    onClick={() => setIsProfileOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-slate-700 hover:bg-slate-50 hover:text-[#0F172A] transition-colors"
                  >
                    <Settings className="w-4 h-4 text-slate-500" />
                    <span>Settings</span>
                  </Link>
                </div>

                <div className="pt-1 border-t border-slate-100">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-rose-600 hover:bg-rose-50 transition-colors text-left cursor-pointer"
                  >
                    <LogOut className="w-4 h-4 text-rose-500" />
                    <span>Log out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sub-header Breadcrumb Bar */}
      <div className="bg-[#F8F9FA] border-t border-[#E5E7EB]/80 px-4 lg:px-6 py-1.5 text-[11px] font-semibold text-slate-500 max-w-[1600px] mx-auto flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span>{getBreadcrumb()}</span>
        </div>
      </div>
    </header>
  );
}
