import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {
  discoverRoutes,
  parseThemes,
  slugifyRoute,
  archiveExistingScreenshot,
  parseCookies,
  parseHeaders
} from './capture.mjs';

test('parseThemes parses single and comma-separated themes', () => {
  assert.deepEqual(parseThemes('light'), ['light']);
  assert.deepEqual(parseThemes('dark'), ['dark']);
  assert.deepEqual(parseThemes('auto'), ['auto']);
  assert.deepEqual(parseThemes('system'), ['auto']);
  assert.deepEqual(parseThemes('light,dark'), ['light', 'dark']);
  assert.deepEqual(parseThemes('all'), ['light', 'dark', 'auto']);
  assert.deepEqual(parseThemes(''), ['light']);
  assert.deepEqual(parseThemes(null), ['light']);
});

test('slugifyRoute creates clean filenames from URLs', () => {
  assert.equal(slugifyRoute('/'), 'overview');
  assert.equal(slugifyRoute('/accounts'), 'accounts');
  assert.equal(slugifyRoute('/investments/holdings'), 'investments-holdings');
  assert.equal(slugifyRoute('/cashflow/transactions/print'), 'cashflow-transactions-print');
});

test('discoverRoutes finds all Next.js pages in directory tree', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'next-routes-'));
  try {
    fs.mkdirSync(path.join(tmpDir, 'accounts'), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, 'investments', 'holdings'), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, '(auth)', 'login'), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, 'api', 'health'), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, '_components'), { recursive: true });

    fs.writeFileSync(path.join(tmpDir, 'page.tsx'), 'export default function Page() {}');
    fs.writeFileSync(path.join(tmpDir, 'layout.tsx'), 'export default function Layout() {}');
    fs.writeFileSync(path.join(tmpDir, 'accounts', 'page.tsx'), 'export default function Page() {}');
    fs.writeFileSync(path.join(tmpDir, 'investments', 'holdings', 'page.tsx'), 'export default function Page() {}');
    fs.writeFileSync(path.join(tmpDir, '(auth)', 'login', 'page.tsx'), 'export default function Page() {}');
    fs.writeFileSync(path.join(tmpDir, 'api', 'health', 'route.ts'), 'export async function GET() {}');
    fs.writeFileSync(path.join(tmpDir, '_components', 'sidebar.tsx'), 'export function Sidebar() {}');

    const routes = discoverRoutes(tmpDir);
    assert.ok(routes.includes('/'));
    assert.ok(routes.includes('/accounts'));
    assert.ok(routes.includes('/investments/holdings'));
    assert.ok(routes.includes('/login')); // route group (auth) stripped
    assert.ok(!routes.includes('/api/health')); // API routes excluded
    assert.ok(!routes.some(r => r.includes('_components'))); // private folders excluded
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('archiveExistingScreenshot moves existing photo to timestamped archive', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'archive-test-'));
  try {
    const currentDir = path.join(tmpDir, 'current');
    const archiveDir = path.join(tmpDir, 'archive');
    fs.mkdirSync(currentDir, { recursive: true });
    fs.mkdirSync(archiveDir, { recursive: true });

    const photoPath = path.join(currentDir, 'overview-light.png');
    fs.writeFileSync(photoPath, 'FAKE_IMAGE_DATA_V1');

    const archivedPath = archiveExistingScreenshot(photoPath, archiveDir, '2026-11-18T12-00-00Z');
    assert.ok(archivedPath, 'Archived path should be returned');
    assert.ok(fs.existsSync(archivedPath), 'Archived file must exist in archive dir');
    assert.equal(fs.readFileSync(archivedPath, 'utf8'), 'FAKE_IMAGE_DATA_V1');
    assert.ok(!fs.existsSync(photoPath), 'Original photo should be moved out of current');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('parseCookies handles header string format', () => {
  const cookieHeader = 'session_id=abc123xyz; auth_token=token456==; user_pref=compact';
  const cookies = parseCookies(cookieHeader, 'http://localhost:3000');
  assert.equal(cookies.length, 3);
  assert.deepEqual(cookies[0], {
    name: 'session_id',
    value: 'abc123xyz',
    domain: 'localhost',
    path: '/'
  });
  assert.deepEqual(cookies[1], {
    name: 'auth_token',
    value: 'token456==',
    domain: 'localhost',
    path: '/'
  });
  assert.deepEqual(cookies[2], {
    name: 'user_pref',
    value: 'compact',
    domain: 'localhost',
    path: '/'
  });
});

test('parseCookies handles JSON string and file path', () => {
  const jsonString = JSON.stringify([
    { name: 'app_session', value: 's_987', domain: 'example.com', path: '/app' }
  ]);
  const parsedFromString = parseCookies(jsonString, 'http://localhost:3000');
  assert.equal(parsedFromString.length, 1);
  assert.equal(parsedFromString[0].name, 'app_session');
  assert.equal(parsedFromString[0].value, 's_987');

  const tmpFile = path.join(os.tmpdir(), `cookie-test-${Date.now()}.json`);
  try {
    fs.writeFileSync(
      tmpFile,
      JSON.stringify({
        cookies: [{ name: 'storage_cookie', value: 'sc_123', domain: 'localhost', path: '/' }]
      })
    );
    const parsedFromFile = parseCookies(tmpFile, 'http://localhost:3000');
    assert.equal(parsedFromFile.length, 1);
    assert.equal(parsedFromFile[0].name, 'storage_cookie');
  } finally {
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
  }
});

test('parseHeaders parses standard headers, authorization bearer, and json', () => {
  const h1 = parseHeaders('Authorization: Bearer token123');
  assert.deepEqual(h1, { Authorization: 'Bearer token123' });

  // Handle header without colon e.g. "Authorization Bearer token123"
  const h2 = parseHeaders('Authorization Bearer token123');
  assert.deepEqual(h2, { Authorization: 'Bearer token123' });

  // Handle JSON
  const h3 = parseHeaders(JSON.stringify({ 'X-Custom-Header': 'val1', Authorization: 'Bearer 456' }));
  assert.equal(h3['X-Custom-Header'], 'val1');
  assert.equal(h3['Authorization'], 'Bearer 456');

  // Handle multiple newline or semicolon separated headers
  const h4 = parseHeaders('X-Key-1: val1\nX-Key-2: val2');
  assert.equal(h4['X-Key-1'], 'val1');
  assert.equal(h4['X-Key-2'], 'val2');
});


