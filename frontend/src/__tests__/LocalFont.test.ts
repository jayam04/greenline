import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Spline Sans Local Font Configuration', () => {
  it('uses localFont for Spline Sans instead of Google API in layout.tsx', () => {
    const layoutPath = path.resolve(__dirname, '../app/layout.tsx');
    const layoutContent = fs.readFileSync(layoutPath, 'utf-8');

    // Should NOT import Spline_Sans from next/font/google
    expect(layoutContent).not.toMatch(/import\s*\{[^}]*Spline_Sans[^}]*\}\s*from\s*["']next\/font\/google["']/);
    expect(layoutContent).not.toMatch(/Spline_Sans\s*\(\s*\{/);

    // Should use localFont for Spline Sans pointing to public/fonts/Spline_Sans
    expect(layoutContent).toMatch(/SplineSans-VariableFont_wght\.ttf|Spline_Sans/);
    expect(layoutContent).toMatch(/--font-spline-sans/);
  });
});
