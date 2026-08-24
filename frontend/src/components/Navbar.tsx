"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { removeAuthToken } from "@/lib/api";
import { 
  Search, TrendingUp, LayoutDashboard, Briefcase, Receipt, 
  DollarSign, Building2, LogOut, Bell, Star, User, ChevronDown,
  ArrowLeftRight, FolderTree, Settings, ShieldCheck, Layers
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
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

  if (pathname === "/login") return null;

  const navItems = [
    { name: "Net worth", href: "/", icon: TrendingUp },
    { name: "Investments", href: "/investments", icon: Briefcase },
    { name: "Holdings", href: "/holdings", icon: Layers },
    { name: "Transactions", href: "/transactions", icon: Receipt },
    { name: "Income & Spends", href: "/cashflow", icon: ArrowLeftRight },
    { name: "Categories", href: "/categories", icon: FolderTree },
    { name: "Realized P&L", href: "/realized", icon: DollarSign },
    { name: "Accounts & Master", href: "/accounts", icon: Building2 },
  ];

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
    if (pathname === "/realized") return "Investments > Realized Gains & Tax Lots";
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
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                    isActive
                      ? "text-[#0F172A] bg-slate-100 font-extrabold"
                      : "text-slate-500 hover:text-[#0F172A] hover:bg-slate-50"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
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
