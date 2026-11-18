#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url);

/**
 * Normalizes and parses theme argument into an array of canonical themes: 'light' | 'dark' | 'auto'.
 */
export function parseThemes(themeArg) {
  if (!themeArg || typeof themeArg !== 'string') {
    return ['light'];
  }
  const raw = themeArg.trim().toLowerCase();
  if (!raw) return ['light'];
  if (raw === 'all') return ['light', 'dark', 'auto'];

  const parts = raw.split(',').map((t) => t.trim()).filter(Boolean);
  const result = [];
  for (const part of parts) {
    if (part === 'light') result.push('light');
    else if (part === 'dark') result.push('dark');
    else if (part === 'auto' || part === 'system') result.push('auto');
    else if (part === 'all') {
      ['light', 'dark', 'auto'].forEach((t) => {
        if (!result.includes(t)) result.push(t);
      });
    }
  }
  return result.length > 0 ? result : ['light'];
}

/**
 * Turns a URL route path into a clean, filesystem-friendly slug.
 */
export function slugifyRoute(route) {
  if (!route || route === '/') return 'overview';
  const clean = route.replace(/^\/+|\/+$/g, '');
  return clean.replace(/[\/\\]+/g, '-');
}

/**
 * Parses cookies from HTTP header string, raw JSON string, or JSON file path.
 * Returns an array of Playwright cookie objects: { name, value, domain, path }.
 */
export function parseCookies(cookieInput, baseUrl = 'http://localhost:3000') {
  if (!cookieInput || typeof cookieInput !== 'string') return [];

  let defaultDomain = 'localhost';
  try {
    defaultDomain = new URL(baseUrl).hostname;
  } catch (e) {}

  const trimmed = cookieInput.trim();
  if (!trimmed) return [];

  // 1. Check if it's a file path
  if (fs.existsSync(trimmed)) {
    try {
      const fileContent = fs.readFileSync(trimmed, 'utf8').trim();
      const parsed = JSON.parse(fileContent);
      const rawCookies = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.cookies) ? parsed.cookies : []);
      return rawCookies.map((c) => ({
        name: c.name,
        value: c.value,
        domain: c.domain || defaultDomain,
        path: c.path || '/'
      }));
    } catch (e) {
      // Fall back to treating file content as cookie string
      try {
        const fileContent = fs.readFileSync(trimmed, 'utf8').trim();
        return parseCookies(fileContent, baseUrl);
      } catch (e2) {}
    }
  }

  // 2. Check if it's a raw JSON string
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed);
      const rawCookies = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.cookies) ? parsed.cookies : []);
      return rawCookies.map((c) => ({
        name: c.name,
        value: c.value,
        domain: c.domain || defaultDomain,
        path: c.path || '/'
      }));
    } catch (e) {}
  }

  // 3. Parse standard HTTP Cookie string: "name1=val1; name2=val2"
  const cookies = [];
  const pairs = trimmed.split(';');
  for (const pair of pairs) {
    const eqIdx = pair.indexOf('=');
    if (eqIdx === -1) continue;
    const name = pair.slice(0, eqIdx).trim();
    const value = pair.slice(eqIdx + 1).trim();
    if (name) {
      cookies.push({
        name,
        value,
        domain: defaultDomain,
        path: '/'
      });
    }
  }
  return cookies;
}

/**
 * Parses custom HTTP headers from string, raw JSON string, or JSON file path.
 * Supports "Header: Value", "Header Value", or multiple lines / semicolons.
 */
export function parseHeaders(headerInput) {
  if (!headerInput || typeof headerInput !== 'string') return {};

  const trimmed = headerInput.trim();
  if (!trimmed) return {};

  // 1. Check if it's a file path
  if (fs.existsSync(trimmed)) {
    try {
      const fileContent = fs.readFileSync(trimmed, 'utf8').trim();
      const parsed = JSON.parse(fileContent);
      if (typeof parsed === 'object' && parsed !== null) {
        return parsed;
      }
    } catch (e) {
      try {
        const fileContent = fs.readFileSync(trimmed, 'utf8').trim();
        return parseHeaders(fileContent);
      } catch (e2) {}
    }
  }

  // 2. Check if it's a raw JSON string
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed === 'object' && parsed !== null) {
        return parsed;
      }
    } catch (e) {}
  }

  // 3. Parse header string (e.g. "Authorization: Bearer ...", "Authorization Bearer ...")
  const headers = {};
  const lines = trimmed.split(/[\r\n]+|;\s*(?=[A-Za-z0-9_-]+[:\s])/);

  for (const line of lines) {
    const l = line.trim();
    if (!l) continue;

    const colonIdx = l.indexOf(':');
    if (colonIdx !== -1) {
      const key = l.slice(0, colonIdx).trim();
      const val = l.slice(colonIdx + 1).trim();
      if (key) headers[key] = val;
    } else {
      const spaceIdx = l.indexOf(' ');
      if (spaceIdx !== -1) {
        const key = l.slice(0, spaceIdx).trim();
        const val = l.slice(spaceIdx + 1).trim();
        if (key) headers[key] = val;
      }
    }
  }

  return headers;
}

/**
 * Discovers Next.js routes from an App Router or Pages Router directory tree.
 */
export function discoverRoutes(baseAppDir) {
  if (!fs.existsSync(baseAppDir)) return [];

  const routes = [];
  const pageFileRegex = /^page\.(tsx|jsx|js|mjs|ts)$/;
  const pagesRouterFileRegex = /^(!?_app|_document|_error)\.(tsx|jsx|js|mjs|ts)$/;

  function scan(currentDir, relativeSegments = []) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    // Check if current directory contains page.tsx (App router)
    const hasAppPage = entries.some((e) => e.isFile() && pageFileRegex.test(e.name));
    if (hasAppPage) {
      // Build route from relativeSegments, omitting route groups like (auth) or (marketing)
      const filteredSegments = relativeSegments.filter(
        (seg) => !seg.startsWith('(') || !seg.endsWith(')')
      );
      const routePath = filteredSegments.length === 0 ? '/' : '/' + filteredSegments.join('/');
      if (!routes.includes(routePath)) {
        routes.push(routePath);
      }
    }

    for (const entry of entries) {
      if (entry.isDirectory()) {
        const dirName = entry.name;
        // Ignore internal directories, private folders (_components), and API folders
        if (dirName.startsWith('_') || dirName === 'api' || dirName === 'node_modules' || dirName === '.next') {
          continue;
        }
        scan(path.join(currentDir, dirName), [...relativeSegments, dirName]);
      } else if (entry.isFile() && !hasAppPage) {
        // Fallback for Pages Router if applicable
        if (
          (entry.name.endsWith('.tsx') || entry.name.endsWith('.jsx') || entry.name.endsWith('.js')) &&
          !pagesRouterFileRegex.test(entry.name) &&
          !entry.name.startsWith('_')
        ) {
          const nameWithoutExt = entry.name.replace(/\.(tsx|jsx|js|mjs|ts)$/, '');
          const segs = [...relativeSegments];
          if (nameWithoutExt !== 'index') {
            segs.push(nameWithoutExt);
          }
          const routePath = segs.length === 0 ? '/' : '/' + segs.join('/');
          if (!routes.includes(routePath) && !routePath.startsWith('/api')) {
            routes.push(routePath);
          }
        }
      }
    }
  }

  scan(baseAppDir);
  return routes.sort();
}

/**
 * If target screenshot already exists in current folder, moves it to timestamped archive.
 */
export function archiveExistingScreenshot(filePath, archiveDir, timestamp = null) {
  if (!fs.existsSync(filePath)) return null;

  const ts = timestamp || new Date().toISOString().replace(/[:.]/g, '-');
  const targetArchiveFolder = path.join(archiveDir, ts);
  if (!fs.existsSync(targetArchiveFolder)) {
    fs.mkdirSync(targetArchiveFolder, { recursive: true });
  }

  const fileName = path.basename(filePath);
  const destination = path.join(targetArchiveFolder, fileName);
  fs.copyFileSync(filePath, destination);
  fs.unlinkSync(filePath);
  return destination;
}

/**
 * Resolves Playwright module from workspace dependencies.
 */
function getPlaywright() {
  const possiblePaths = [
    path.resolve(__dirname, '../../../../frontend/node_modules/@playwright/test'),
    path.resolve(__dirname, '../../../../frontend/node_modules/playwright'),
    '@playwright/test',
    'playwright'
  ];

  for (const candidate of possiblePaths) {
    try {
      const mod = require(candidate);
      if (mod && mod.chromium) return mod;
    } catch (e) {
      // continue search
    }
  }
  throw new Error('Playwright not found in frontend/node_modules or global scope.');
}

/**
 * Launches Chromium using installed Playwright browsers or system Chrome fallback.
 */
export async function launchBrowser(options = {}) {
  const { chromium } = getPlaywright();
  const headless = options.headless !== false;

  // 1. Try default launch
  try {
    return await chromium.launch({ headless });
  } catch (err1) {
    // 2. Try system Google Chrome
    try {
      return await chromium.launch({ headless, channel: 'chrome' });
    } catch (err2) {
      // 3. Try cached chromium executable in ms-playwright
      const homeDir = process.env.HOME || '/home/jayampatel';
      const cachedPaths = [
        path.join(homeDir, '.cache/ms-playwright/chromium-1248/chrome-linux64/chrome'),
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser'
      ];
      for (const p of cachedPaths) {
        if (fs.existsSync(p)) {
          return await chromium.launch({ headless, executablePath: p });
        }
      }
      throw err1;
    }
  }
}

/**
 * Finds the default Next.js app directory in the repository.
 */
export function findDefaultAppDir() {
  const candidates = [
    path.resolve(__dirname, '../../../../frontend/src/app'),
    path.resolve(__dirname, '../../../../frontend/app'),
    path.resolve(process.cwd(), 'frontend/src/app'),
    path.resolve(process.cwd(), 'src/app')
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return candidates[0];
}

/**
 * Main execution runner.
 */
export async function run(argv = process.argv.slice(2)) {
  const args = {
    page: null,
    all: false,
    theme: 'light',
    list: false,
    auth: false,
    cookie: process.env.SCREENSHOT_COOKIE || process.env.COOKIE || null,
    header: process.env.SCREENSHOT_HEADER || process.env.HEADER || null,
    storageState: process.env.STORAGE_STATE || null,
    baseUrl: process.env.BASE_URL || 'http://localhost:3000',
    appDir: null,
    outputDir: path.resolve(__dirname, '../screenshots'),
    viewport: '1440x900'
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--page') args.page = argv[++i];
    else if (arg === '--all') args.all = true;
    else if (arg === '--theme') args.theme = argv[++i];
    else if (arg === '--list') args.list = true;
    else if (arg === '--auth') args.auth = true;
    else if (arg === '--cookie' || arg === '--cookies') args.cookie = argv[++i];
    else if (arg === '--header' || arg === '--headers') args.header = argv[++i];
    else if (arg === '--storage-state') args.storageState = argv[++i];
    else if (arg === '--base-url') args.baseUrl = argv[++i];
    else if (arg === '--app-dir') args.appDir = argv[++i];
    else if (arg === '--output-dir') args.outputDir = argv[++i];
    else if (arg === '--viewport') args.viewport = argv[++i];
    else if (arg === '--help' || arg === '-h') {
      console.log(`
Usage: node capture.mjs [options]

Options:
  --page <route>          Capture a specific page (e.g. "/" or "/accounts")
  --all                   Capture all pages discovered in the Next.js app directory
  --theme <mode>          Theme: "light", "dark", "auto", or comma-separated list "light,dark" (default: "light")
  --cookie <string|file>  Pass cookie header ("a=1; b=2"), JSON array, or cookie file path
  --header <string|file>  Pass HTTP headers ("Authorization: Bearer ...") or JSON
  --storage-state <path>  Playwright storage state JSON file path (cookies + localStorage)
  --list                  List all discovered Next.js pages and exit
  --auth                  Perform automated login before capturing protected dashboards
  --base-url <url>        Base URL (default: "http://localhost:3000")
  --app-dir <path>        Path to Next.js app directory (default: auto-detected)
  --output-dir <path>     Screenshots output directory (default: .agents/skills/page-screenshots/screenshots)
  --viewport <WxH>        Viewport dimensions (default: "1440x900")
  --help, -h              Show this help message
`);
      return;
    }
  }

  const appDir = args.appDir ? path.resolve(args.appDir) : findDefaultAppDir();
  const routes = discoverRoutes(appDir);

  if (args.list) {
    console.log(`Discovered ${routes.length} Next.js routes in ${appDir}:`);
    for (const r of routes) {
      console.log(`  - ${r}`);
    }
    return;
  }

  const targetRoutes = [];
  if (args.page) {
    const formatted = args.page.startsWith('/') ? args.page : `/${args.page}`;
    targetRoutes.push(formatted);
  } else if (args.all) {
    targetRoutes.push(...routes);
  } else {
    // Default to root overview page
    targetRoutes.push('/');
  }

  const themes = parseThemes(args.theme);
  const [vpWidth, vpHeight] = args.viewport.split('x').map(Number);
  const currentDir = path.join(args.outputDir, 'current');
  const archiveDir = path.join(args.outputDir, 'archive');

  if (!fs.existsSync(currentDir)) fs.mkdirSync(currentDir, { recursive: true });
  if (!fs.existsSync(archiveDir)) fs.mkdirSync(archiveDir, { recursive: true });

  const runTimestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const parsedCookies = parseCookies(args.cookie, args.baseUrl);
  const parsedHeaders = parseHeaders(args.header);
  const authHeader = parsedHeaders['Authorization'] || parsedHeaders['authorization'];
  let bearerToken = null;
  if (authHeader) {
    bearerToken = authHeader.replace(/^Bearer\s+/i, '').trim();
  }

  console.log(`[page-screenshots] Target routes: ${targetRoutes.join(', ')}`);
  console.log(`[page-screenshots] Themes: ${themes.join(', ')}`);
  console.log(`[page-screenshots] Viewport: ${vpWidth}x${vpHeight} @ 2x DPR`);
  console.log(`[page-screenshots] Base URL: ${args.baseUrl}`);
  console.log(`[page-screenshots] Output directory: ${currentDir}`);
  if (parsedCookies.length > 0) {
    console.log(`[page-screenshots] Custom cookies loaded: ${parsedCookies.length} cookie(s)`);
  }
  if (Object.keys(parsedHeaders).length > 0) {
    console.log(`[page-screenshots] Custom headers loaded: ${Object.keys(parsedHeaders).join(', ')}`);
  }
  if (bearerToken) {
    console.log(`[page-screenshots] Bearer authentication token active`);
  }
  if (args.storageState) {
    console.log(`[page-screenshots] Storage state: ${args.storageState}`);
  }

  const browser = await launchBrowser();
  let archivedCount = 0;
  let capturedCount = 0;
  const capturedFiles = [];

  try {
    for (const theme of themes) {
      const colorScheme = theme === 'dark' ? 'dark' : theme === 'light' ? 'light' : 'no-preference';
      const contextOptions = {
        viewport: { width: vpWidth || 1440, height: vpHeight || 900 },
        deviceScaleFactor: 2,
        colorScheme,
        ...(Object.keys(parsedHeaders).length > 0 ? { extraHTTPHeaders: parsedHeaders } : {})
      };
      if (args.storageState && fs.existsSync(args.storageState)) {
        contextOptions.storageState = args.storageState;
      }

      const context = await browser.newContext(contextOptions);

      if (parsedCookies.length > 0) {
        await context.addCookies(parsedCookies);
      }

      // Inject theme and auth token into localStorage
      await context.addInitScript(({ th, token }) => {
        try {
          const storageVal = th === 'dark' ? 'dark' : th === 'light' ? 'light' : 'system';
          window.localStorage.setItem('greenline_theme', storageVal);
          window.localStorage.setItem('gl-theme', storageVal);
          if (token) {
            window.localStorage.setItem('token', token);
            window.localStorage.setItem('access_token', token);
          }
        } catch (e) {}
      }, { th: theme, token: bearerToken });

      const page = await context.newPage();

      // Optional Auth
      if (args.auth) {
        try {
          const loginUrl = `${args.baseUrl}/login`;
          console.log(`[page-screenshots] Logging in at ${loginUrl}...`);
          await page.goto(loginUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
          const userField = page.locator('input[type="text"]');
          const passField = page.locator('input[type="password"]');
          const submitBtn = page.locator('button[type="submit"]');

          if (await userField.count() > 0) {
            await userField.fill(process.env.SCREENSHOT_USER || 'admin');
            await passField.fill(process.env.SCREENSHOT_PASS || 'admin123');
            await submitBtn.click();
            await page.waitForTimeout(2000);
          }
        } catch (authErr) {
          console.warn(`[page-screenshots] Auth attempt warning: ${authErr.message}`);
        }
      }

      for (const route of targetRoutes) {
        const targetUrl = `${args.baseUrl}${route}`;
        const slug = slugifyRoute(route);
        const fileName = `${slug}-${theme}.png`;
        const currentPath = path.join(currentDir, fileName);

        // 1. Save old photo if exists
        const archived = archiveExistingScreenshot(currentPath, archiveDir, runTimestamp);
        if (archived) {
          archivedCount++;
          console.log(`[page-screenshots] Archived old photo -> ${archived}`);
        }

        // 2. Navigate and capture
        console.log(`[page-screenshots] Capturing ${targetUrl} (${theme})...`);
        try {
          await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
          // Ensure theme classes and token on page
          await page.evaluate(({ th, token }) => {
            const root = document.documentElement;
            if (th === 'dark') {
              root.classList.add('dark');
              root.classList.remove('light');
            } else if (th === 'light') {
              root.classList.remove('dark');
              root.classList.add('light');
            }
            if (token) {
              window.localStorage.setItem('token', token);
              window.localStorage.setItem('access_token', token);
            }
          }, { th: theme, token: bearerToken });

          // Allow charts and animations to settle
          await page.waitForTimeout(1000);

          const currentUrl = page.url();
          const pageTitle = await page.title();
          console.log(`[page-screenshots] Rendered: "${pageTitle}" (${currentUrl})`);

          await page.screenshot({ path: currentPath, fullPage: false });
          capturedCount++;
          capturedFiles.push(currentPath);
          console.log(`[page-screenshots] Saved: ${currentPath}`);
        } catch (navErr) {
          console.error(`[page-screenshots] Failed capturing ${targetUrl}: ${navErr.message}`);
        }
      }

      await context.close();
    }
  } finally {
    await browser.close();
  }

  console.log(`\n[page-screenshots] Completed: ${capturedCount} captured, ${archivedCount} archived.`);
  return { capturedFiles, capturedCount, archivedCount };
}

// Direct execution CLI entrypoint
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(__filename)) {
  run().catch((err) => {
    console.error(`[page-screenshots] Error:`, err);
    process.exit(1);
  });
}
