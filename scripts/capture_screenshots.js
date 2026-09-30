const { chromium } = require('/home/jayampatel/swe/greenline/frontend/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3005';
const DOCS_DIR = path.resolve(__dirname, '../docs/assets/screenshots');
const GITHUB_DIR = path.resolve(__dirname, '../.github/data');

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run() {
  if (!fs.existsSync(DOCS_DIR)) {
    fs.mkdirSync(DOCS_DIR, { recursive: true });
  }
  if (!fs.existsSync(GITHUB_DIR)) {
    fs.mkdirSync(GITHUB_DIR, { recursive: true });
  }

  console.log(`[Screenshots] Launching Chromium (1440x900 @ 2x DPR) with RX100 font...`);
  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: 'light',
  });

  // Inject rx100 font into localStorage across all pages
  await context.addInitScript(() => {
    try {
      window.localStorage.setItem('greenline_font', 'rx100');
    } catch (e) {}
  });

  const page = await context.newPage();

  // 1. Login
  console.log(`[Screenshots] Logging in at ${BASE_URL}/login...`);
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button[type="submit"]');
  
  // Wait for redirect to dashboard
  await page.waitForSelector('.getquin-card, aside', { timeout: 15000 });
  await sleep(2500);

  // Explicitly configure RX100 font on server settings as well
  console.log(`[Screenshots] Setting RX100 font in app settings...`);
  await page.evaluate(async () => {
    localStorage.setItem('greenline_font', 'rx100');
    document.documentElement.setAttribute('data-font', 'rx100');
    document.documentElement.classList.remove('font-general-sans', 'font-inter');
    document.documentElement.classList.add('font-rx100');
    const token = localStorage.getItem('token');
    if (token) {
      await fetch('/api/v1/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ app_font: 'rx100' })
      }).catch(() => {});
    }
  });
  await sleep(1500);

  console.log(`[Screenshots] Logged in with RX100 font! URL: ${page.url()}`);

  async function capture(name, syncToGithub = false) {
    // Ensure font-rx100 class is active
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-font', 'rx100');
      document.documentElement.classList.remove('font-general-sans', 'font-inter');
      document.documentElement.classList.add('font-rx100');
    });
    await sleep(600);

    const docsPath = path.join(DOCS_DIR, name);
    await page.screenshot({ path: docsPath, fullPage: false });
    console.log(`[Screenshots] Saved ${docsPath}`);

    if (syncToGithub) {
      const githubPath = path.join(GITHUB_DIR, name);
      fs.copyFileSync(docsPath, githubPath);
      console.log(`[Screenshots] Synced ${githubPath}`);
    }
  }

  // 1. Net Worth Dashboard (Light Mode with RX100)
  console.log(`[Screenshots] Capturing Net Worth Dashboard (RX100)...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
  await sleep(3000);
  await capture('networth-dashboard.png', true);

  // 2. Privacy Mode (RX100)
  console.log(`[Screenshots] Capturing Privacy Mode (RX100)...`);
  const hideBtn = page.locator('button:has-text("Hide")').first();
  if (await hideBtn.isVisible()) {
    await hideBtn.click();
    await sleep(1000);
    await capture('privacy-mode.png', true);
    // Restore
    const showBtn = page.locator('button:has-text("Show")').first();
    if (await showBtn.isVisible()) {
      await showBtn.click();
      await sleep(600);
    }
  }

  // 3. Investments Portfolio Analytics (RX100)
  console.log(`[Screenshots] Capturing Investments Portfolio (RX100)...`);
  await page.goto(`${BASE_URL}/investments`, { waitUntil: 'domcontentloaded' });
  await sleep(3000);
  await capture('investments-portfolio.png', true);

  // 4. Holdings & FIFO Lot Details (RX100)
  console.log(`[Screenshots] Capturing Holdings & FIFO lots breakdown (RX100)...`);
  await page.goto(`${BASE_URL}/investments/holdings`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  // Expand first holding row to show open FIFO lots breakdown
  const firstRow = page.locator('table tbody tr').first();
  if (await firstRow.isVisible()) {
    await firstRow.click();
    await sleep(1200);
  }
  await capture('holdings.png', true);

  // 5. Cashflow & Sankey Diagram (RX100)
  console.log(`[Screenshots] Capturing Cashflow Sankey (RX100)...`);
  await page.goto(`${BASE_URL}/cashflow`, { waitUntil: 'domcontentloaded' });
  await sleep(3500);
  await capture('cashflow-sankey.png', true);

  // 6. Cashflow Transactions Ledger (RX100)
  console.log(`[Screenshots] Capturing Cashflow Transactions (RX100)...`);
  await page.goto(`${BASE_URL}/cashflow/transactions`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  await capture('cashflow-transactions.png', false);

  // 7. Category Taxonomy & Spends (RX100)
  console.log(`[Screenshots] Capturing Categories Hierarchy (RX100)...`);
  await page.goto(`${BASE_URL}/categories`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  await capture('categories-hierarchy.png', true);

  // 8. Trade & Transaction Ledger (RX100)
  console.log(`[Screenshots] Capturing Unified Transactions Ledger (RX100)...`);
  await page.goto(`${BASE_URL}/investments/transactions`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  await capture('transactions-ledger.png', true);

  // 9. Accounts & Multi-Currency Balances (RX100)
  console.log(`[Screenshots] Capturing Accounts & Valuations (RX100)...`);
  await page.goto(`${BASE_URL}/accounts`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  await capture('accounts-valuations.png', false);

  // 10. Dark Mode Dashboard (RX100)
  console.log(`[Screenshots] Capturing Dark Mode Dashboard (RX100)...`);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
  await sleep(2000);
  // Set theme to dark
  await page.evaluate(() => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('greenline-theme', 'dark');
  });
  await sleep(1500);
  await capture('dark-mode-dashboard.png', false);

  await browser.close();
  console.log(`[Screenshots] All 10 screenshots successfully captured with RX100 font!`);
}

run().catch((err) => {
  console.error('[Screenshots] Error:', err);
  process.exit(1);
});
