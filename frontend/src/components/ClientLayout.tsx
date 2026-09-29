"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { Breadcrumb } from "@/components/Breadcrumb";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPrint = pathname === "/cashflow/transactions/print";
  const isLogin = pathname === "/login";

  if (isPrint) {
    return <main className="print-layout">{children}</main>;
  }

  return (
    <div className="flex min-h-screen">
      {!isLogin && <Sidebar />}
      <div className={`flex-1 flex flex-col w-full ${!isLogin ? "lg:pl-64" : ""}`}>
        {!isLogin && <Breadcrumb />}
        <main className="flex-1 w-full px-4 md:px-8 pb-8 pt-2">
          {children}
        </main>
      </div>
    </div>
  );
}
