"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type AppFont = "general-sans" | "inter" | "rx100" | "spline-sans" | "spine-sans";

export const FONT_STORAGE_KEY = "greenline_font";

interface FontContextType {
  font: AppFont;
  setFont: (font: AppFont | string) => void;
}

const FontContext = createContext<FontContextType | undefined>(undefined);

function normalizeFont(f: string | null): AppFont {
  if (!f) return "spline-sans";
  if (f === "inter") return "inter";
  if (f === "rx100" || f === "mono") return "rx100";
  if (f === "general" || f === "general-sans") return "general-sans";
  if (f === "spline" || f === "spline-sans" || f === "spine-sans") return "spline-sans";
  return "spline-sans";
}

export function FontProvider({ children }: { children: React.ReactNode }) {
  const [font, setFontState] = useState<AppFont>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(FONT_STORAGE_KEY) || localStorage.getItem("gl-font");
        if (saved) {
          return normalizeFont(saved);
        }
      } catch (e) {
        console.error("Failed to read font from localStorage:", e);
      }
    }
    return "spline-sans";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-font", font);
    root.classList.remove("font-inter", "font-general-sans", "font-rx100", "font-spline-sans", "font-spine-sans");
    if (font === "inter") {
      root.classList.add("font-inter");
    } else if (font === "rx100") {
      root.classList.add("font-rx100");
    } else if (font === "general-sans") {
      root.classList.add("font-general-sans");
    } else {
      root.classList.add("font-spline-sans");
    }
  }, [font]);

  const setFont = (newFont: AppFont | string) => {
    const validFont = normalizeFont(newFont);
    setFontState(validFont);
    try {
      localStorage.setItem(FONT_STORAGE_KEY, validFont);
      localStorage.setItem("gl-font", validFont === "spline-sans" ? "spline" : validFont);
    } catch (e) {
      console.error("Failed to persist font to localStorage:", e);
    }
  };

  return (
    <FontContext.Provider value={{ font, setFont }}>
      {children}
    </FontContext.Provider>
  );
}

export function useFont() {
  const context = useContext(FontContext);
  if (!context) {
    return {
      font: "spline-sans" as AppFont,
      setFont: () => {},
    };
  }
  return context;
}
