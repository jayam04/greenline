import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Breadcrumb } from "@/components/Breadcrumb";
import { ThemeProvider } from "@/components/ThemeProvider";

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
  title: {
    template: "%s · greenline",
    default: "Overview · greenline",
  },
  description: "Modern minimalist portfolio tracker with precise FIFO lot tracking, XIRR, and Realized P&L.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={generalSans.variable} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('greenline_theme') || 'system';
                  var isDark = saved === 'dark' || (saved === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                  if (isDark) {
                    document.documentElement.classList.add('dark');
                    document.documentElement.classList.remove('light');
                  } else {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.classList.add('light');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className={`${generalSans.className} bg-[#F3F4F6] dark:bg-[#0B0F17] text-[#0F172A] dark:text-[#F8FAFC] min-h-screen flex flex-col font-sans selection:bg-[#9FE837] selection:text-[#0F172A] transition-colors duration-150`}>
        <ThemeProvider>
          <Navbar />
          <Breadcrumb />
          <main className="flex-1 w-full px-4 md:px-8 pb-8 pt-2">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
