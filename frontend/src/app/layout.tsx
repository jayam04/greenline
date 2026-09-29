import type { Metadata } from "next";
import Script from "next/script";
import localFont from "next/font/local";
import { Inter, Figtree } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Breadcrumb } from "@/components/Breadcrumb";
import { ThemeProvider } from "@/components/ThemeProvider";
import { FontProvider } from "@/components/FontProvider";
import { ClientLayout } from "@/components/ClientLayout";
import { cn } from "@/lib/utils";

const rx100 = localFont({
  src: "./../../public/fonts/RX100_Complete/Fonts/WEB/fonts/RX100-Regular.woff2",
  variable: "--font-rx100",
  display: "swap",
});

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
    <html lang="en" className={cn(generalSans.variable, inter.variable, figtreeHeading.variable, rx100.variable)} suppressHydrationWarning>
      <head>
        <Script
          id="theme-script"
          strategy="beforeInteractive"
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
                  document.documentElement.classList.remove('font-inter', 'font-general-sans', 'font-rx100');
                  if (savedFont === 'inter') {
                    document.documentElement.classList.add('font-inter');
                  } else if (savedFont === 'rx100') {
                    document.documentElement.classList.add('font-rx100');
                  } else {
                    document.documentElement.classList.add('font-general-sans');
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
            <ClientLayout>
              {children}
            </ClientLayout>
          </FontProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
