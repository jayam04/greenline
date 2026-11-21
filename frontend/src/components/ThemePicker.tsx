"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export const themes = [
  { id: "lime", name: "Greenline Lime", texture: "Dot grid", blurb: "Brand default. Crisp, fresh, a little playful." },
  { id: "indigo", name: "Midnight Indigo", texture: "Film grain + glow", blurb: "Modern and calm. Mint for gains stands out." },
  { id: "paper", name: "Warm Paper", texture: "Paper grain + ledger rules", blurb: "Private-bank statement feel. Easy on the eyes." },
  { id: "graphite", name: "Graphite", texture: "Blueprint grid", blurb: "Neutral and data-first. Numbers carry the colour." },
  { id: "amber", name: "Amber Ledger", texture: "Tiny checks", blurb: "Trading-desk warmth with a charcoal base." },
] as const;

export type ThemeId = (typeof themes)[number]["id"];

function useIsDark() {
  const [dark, setDark] = React.useState(false);
  React.useEffect(() => {
    const el = document.documentElement;
    const read = () => setDark(el.classList.contains("dark"));
    read();
    const o = new MutationObserver(read);
    o.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => o.disconnect();
  }, []);
  return dark;
}

/** A tiny render of the real UI, wrapped in its own data-theme so it uses that theme's tokens. */
function Preview({ id, dark, texture }: { id: ThemeId; dark: boolean; texture: boolean }) {
  return (
    <div
      data-theme={id}
      className={cn("overflow-hidden rounded-control border border-border text-foreground", dark && "dark")}
      style={{
        backgroundColor: "var(--background)",
        backgroundImage: texture ? "var(--texture)" : "none",
        backgroundSize: "var(--texture-size)",
      }}
      aria-hidden
    >
      <div className="flex h-36">
        <div className="w-9 shrink-0 space-y-1.5 border-r border-border bg-surface p-2">
          <div className="h-3 w-full rounded-sm bg-accent" />
          <div className="h-1.5 w-full rounded-full bg-surface-2" />
          <div className="h-1.5 w-3/4 rounded-full bg-surface-2" />
          <div className="h-1.5 w-full rounded-full bg-surface-2" />
        </div>
        <div className="flex-1 space-y-2 p-2.5">
          <div className="rounded-control border border-border bg-surface p-2 shadow-card">
            <div className="text-[9px] uppercase tracking-wider text-muted">Net worth</div>
            <div className="flex items-center gap-1.5">
              <span className="text-[15px] font-semibold tnum">€155,359</span>
              <span className="rounded-full bg-gain-soft px-1.5 text-[9px] font-medium text-gain">▲ 36.5%</span>
            </div>
            <svg viewBox="0 0 100 24" className="mt-1 h-5 w-full">
              <path d="M0,20 L12,16 L24,18 L36,10 L48,13 L60,6 L72,9 L84,3 L100,5" fill="none" stroke="var(--chart-1)" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="rounded-control bg-primary px-2 py-1 text-[9px] font-medium text-primary-foreground">Add trade</span>
            <span className="rounded-control border border-border-strong bg-surface px-2 py-1 text-[9px] text-muted">Filter</span>
            <span className="ml-auto text-[10px] font-medium tnum text-loss">−€2,858</span>
          </div>
          <div className="flex gap-1">
            {["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5"].map((c) => (
              <span key={c} className="h-1.5 flex-1 rounded-full" style={{ background: `var(${c})` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ThemePicker() {
  const [theme, setTheme] = React.useState<ThemeId>("indigo");
  const [texture, setTexture] = React.useState(true);
  const dark = useIsDark();

  React.useEffect(() => {
    try {
      const t = localStorage.getItem("gl-palette") as ThemeId | null;
      if (t) setTheme(t);
      else {
        setTheme("indigo");
        document.documentElement.dataset.theme = "indigo";
      }
      setTexture(localStorage.getItem("gl-texture") !== "off");
    } catch {}
  }, []);

  const pick = (id: ThemeId) => {
    setTheme(id);
    document.documentElement.dataset.theme = id;
    try {
      localStorage.setItem("gl-palette", id);
    } catch {}
  };

  const toggleTexture = (on: boolean) => {
    setTexture(on);
    document.documentElement.dataset.texture = on ? "on" : "off";
    try {
      localStorage.setItem("gl-texture", on ? "on" : "off");
    } catch {}
  };

  return (
    <div className="space-y-6">
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h3 className="text-title font-semibold">Color theme</h3>
            <p className="mt-0.5 text-label text-muted">Click a theme to apply it everywhere. Previews follow the current mode.</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {themes.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => pick(t.id)}
              aria-pressed={theme === t.id}
              className={cn(
                "group rounded-card border p-2.5 text-left transition-colors",
                theme === t.id ? "border-primary ring-2 ring-primary/20" : "border-border hover:border-border-strong"
              )}
            >
              <Preview id={t.id} dark={dark} texture={texture} />
              <div className="mt-3 flex items-center justify-between gap-2 px-1">
                <span className="font-medium">{t.name}</span>
                {theme === t.id && <Check className="size-4" />}
              </div>
              <div className="px-1 text-micro text-muted">{t.texture}</div>
              <div className="mt-1 px-1 pb-1 text-label text-muted">{t.blurb}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div>
          <h3 className="text-title font-semibold">Background texture</h3>
          <p className="mt-0.5 text-label text-muted">A very faint pattern behind the cards. Cards and tables stay solid so numbers stay crisp.</p>
        </div>
        <div className="mt-4">
          <label className="flex cursor-pointer items-center gap-3 text-body">
            <input
              type="checkbox"
              checked={texture}
              onChange={(e) => toggleTexture(e.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            Show texture
          </label>
        </div>
      </div>
    </div>
  );
}
