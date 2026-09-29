"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type AppFont = "general-sans" | "inter" | "rx100";

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
        if (saved && (saved === "general-sans" || saved === "inter" || saved === "rx100")) {
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
    root.classList.remove("font-inter", "font-general-sans", "font-rx100");
    if (font === "inter") {
      root.classList.add("font-inter");
    } else if (font === "rx100") {
      root.classList.add("font-rx100");
    } else {
      root.classList.add("font-general-sans");
    }
  }, [font]);

  const setFont = (newFont: AppFont) => {
    const validFont: AppFont = ["inter", "rx100", "general-sans"].includes(newFont) ? newFont : "general-sans";
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
