import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Olive Theme Configuration", () => {
  const globalsCssPath = path.resolve(__dirname, "../app/globals.css");
  const layoutPath = path.resolve(__dirname, "../app/layout.tsx");
  const componentsJsonPath = path.resolve(__dirname, "../../components.json");

  it("should have baseColor set to olive in components.json", () => {
    const raw = fs.readFileSync(componentsJsonPath, "utf-8");
    const json = JSON.parse(raw);
    expect(json.tailwind.baseColor).toBe("olive");
  });

  it("should define olive background and card colors in globals.css instead of pure white oklch(1 0 0)", () => {
    const css = fs.readFileSync(globalsCssPath, "utf-8");
    // Ensure :root does NOT define --background or --card as pure white oklch(1 0 0)
    // Under Olive theme, it should have a visible olive hue (hue ~ 118)
    expect(css).toMatch(/--background:\s*oklch\([^)]*118\)/);
    expect(css).toMatch(/--card:\s*oklch\([^)]*118\)/);
    expect(css).toMatch(/--popover:\s*oklch\([^)]*118\)/);
  });

  it("should not duplicate :root and .dark blocks in globals.css", () => {
    const css = fs.readFileSync(globalsCssPath, "utf-8");
    const rootMatches = css.match(/:root\s*\{/g);
    expect(rootMatches ? rootMatches.length : 0).toBe(1);
    const darkMatches = css.match(/\.dark\s*\{/g);
    expect(darkMatches ? darkMatches.length : 0).toBe(1);
  });

  it("should not hardcode slate/navy body background in layout.tsx", () => {
    const layout = fs.readFileSync(layoutPath, "utf-8");
    expect(layout).not.toContain("bg-[#F3F4F6]");
    expect(layout).not.toContain("dark:bg-[#0B0F17]");
    expect(layout).toContain("bg-background");
    expect(layout).toContain("text-foreground");
  });
});
