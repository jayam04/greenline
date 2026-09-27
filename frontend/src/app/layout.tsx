import type { Metadata } from "next";
import localFont from "next/font/local";
import { Inter, Figtree } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Breadcrumb } from "@/components/Breadcrumb";
import { ThemeProvider } from "@/components/ThemeProvider";
import { FontProvider } from "@/components/FontProvider";
import { cn } from "@/lib/utils";

const figtreeHeading = Figtree({subsets:['latin'],variable:'--font-heading'});

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

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
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
    <html lang="en" className={cn(generalSans.variable, inter.variable, figtreeHeading.variable)} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var savedTheme = localStorage.getItem('greenline_theme') || 'system';
                  var isDark = savedTheme === 'dark' || (savedTheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                  if (isDark) {
                    document.documentElement.classList.add('dark');
                    document.documentElement.classList.remove('light');
                  } else {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.classList.add('light');
                  }

                  var savedFont = localStorage.getItem('greenline_font') || 'general-sans';
                  document.documentElement.setAttribute('data-font', savedFont);
                  if (savedFont === 'inter') {
                    document.documentElement.classList.add('font-inter');
                    document.documentElement.classList.remove('font-general-sans');
                  } else {
                    document.documentElement.classList.add('font-general-sans');
                    document.documentElement.classList.remove('font-inter');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-[#F3F4F6] dark:bg-[#0B0F17] text-[#0F172A] dark:text-[#F8FAFC] min-h-screen font-sans selection:bg-[#9FE837] selection:text-[#0F172A] transition-colors duration-150">
        <ThemeProvider>
          <FontProvider>
            <div className="flex min-h-screen">
              <Sidebar />
              <div className="flex-1 flex flex-col lg:pl-64 w-full">
                <Breadcrumb />
                <main className="flex-1 w-full px-4 md:px-8 pb-8 pt-2">
                  {children}
                </main>
              </div>
            </div>
          </FontProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
