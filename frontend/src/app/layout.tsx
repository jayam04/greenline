import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const generalSans = localFont({
  src: [
    {
      path: "./fonts/GeneralSans-Variable.woff2",
      style: "normal",
    },
    {
      path: "./fonts/GeneralSans-VariableItalic.woff2",
      style: "italic",
    },
  ],
  variable: "--font-general-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Greenline | Neo-Fintech Investment Tracker",
  description: "Modern minimalist portfolio tracker with precise FIFO lot tracking, XIRR, and Realized P&L.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={generalSans.variable}>
      <body className={`${generalSans.className} bg-[#F3F4F6] text-[#0F172A] min-h-screen flex flex-col font-sans selection:bg-[#9FE837] selection:text-[#0F172A]`}>
        <Navbar />
        <main className="flex-1 w-full px-4 md:px-8 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
