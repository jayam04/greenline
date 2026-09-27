"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type AppFont = "general-sans" | "inter";

export const FONT_STORAGE_KEY = "greenline_font";

interface FontContextType {
  font: AppFont;
  setFont: (font: AppFont) => void;
}

const FontContext = createContext<FontContextType | undefined>(undefined);

export function FontProvider({ children }: { children: React.ReactNode }) {
  const [font, setFontState] = useState<AppFont>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(FONT_STORAGE_KEY) as AppFont | null;
        if (saved && (saved === "general-sans" || saved === "inter")) {
          return saved;
        }
      } catch (e) {
        console.error("Failed to read font from localStorage:", e);
      }
    }
    return "general-sans";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-font", font);
    if (font === "inter") {
      root.classList.add("font-inter");
      root.classList.remove("font-general-sans");
    } else {
      root.classList.add("font-general-sans");
      root.classList.remove("font-inter");
    }
  }, [font]);

  const setFont = (newFont: AppFont) => {
    const validFont: AppFont = newFont === "inter" ? "inter" : "general-sans";
    setFontState(validFont);
    try {
      localStorage.setItem(FONT_STORAGE_KEY, validFont);
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
      font: "general-sans" as AppFont,
      setFont: () => {},
    };
  }
  return context;
}
