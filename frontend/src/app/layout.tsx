import type { Metadata } from "next";
import Script from "next/script";
import localFont from "next/font/local";
import { Inter, Figtree } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { FontProvider } from "@/components/FontProvider";
import { ClientLayout } from "@/components/ClientLayout";
import { AuthProvider } from "@/components/AuthProvider";
import { cn } from "@/lib/utils";

const rx100 = localFont({
  src: "./../../public/fonts/RX100_Complete/Fonts/WEB/fonts/RX100-Regular.woff2",
  variable: "--font-rx100",
  display: "swap",
});

const figtreeHeading = Figtree({ subsets: ["latin"], variable: "--font-heading" });

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

const splineSans = localFont({
  src: "./../../public/fonts/Spline_Sans/SplineSans-VariableFont_wght.ttf",
  variable: "--font-spline-sans",
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
    <html
      lang="en"
      data-font="spline"
      data-theme="indigo"
      className={cn(generalSans.variable, inter.variable, figtreeHeading.variable, rx100.variable, splineSans.variable)}
      suppressHydrationWarning
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link href="https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Spline+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
        <Script
          id="theme-script"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var savedTheme = localStorage.getItem('greenline_theme') || localStorage.getItem('gl-theme') || 'system';
                  var isDark = savedTheme === 'dark' || (savedTheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                  if (isDark) {
                    document.documentElement.classList.add('dark');
                    document.documentElement.classList.remove('light');
                  } else {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.classList.add('light');
                  }

                  var savedPalette = localStorage.getItem('gl-palette') || 'indigo';
                  document.documentElement.setAttribute('data-theme', savedPalette);

                  var savedTexture = localStorage.getItem('gl-texture');
                  if (savedTexture === 'off') {
                    document.documentElement.setAttribute('data-texture', 'off');
                  }

                  var savedFont = localStorage.getItem('greenline_font') || localStorage.getItem('gl-font') || 'spline';
                  document.documentElement.setAttribute('data-font', savedFont);
                  document.documentElement.classList.remove('font-inter', 'font-general-sans', 'font-rx100', 'font-spline-sans', 'font-spine-sans');
                  if (savedFont === 'inter') {
                    document.documentElement.classList.add('font-inter');
                  } else if (savedFont === 'rx100' || savedFont === 'mono') {
                    document.documentElement.classList.add('font-rx100');
                  } else if (savedFont === 'general-sans' || savedFont === 'general') {
                    document.documentElement.classList.add('font-general-sans');
                  } else {
                    document.documentElement.classList.add('font-spline-sans');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-background text-foreground min-h-screen font-sans selection:bg-[#9FE837] selection:text-[#0F172A] transition-colors duration-150">
        <AuthProvider>
          <ThemeProvider>
            <FontProvider>
              <ClientLayout>
                {children}
              </ClientLayout>
            </FontProvider>
          </ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
