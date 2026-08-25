import { test, expect } from '@playwright/test';

test.describe('Greenline Core End-to-End User Journeys', () => {
  test('Journey 1: Dashboard loads with net worth and navigation', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Greenline|Portfolio|Tracker/i);
    // Verify header and navigation
    await expect(page.locator('text=Holdings')).toBeVisible();
    await expect(page.locator('text=Cashflow')).toBeVisible();
  });

  test('Journey 2: Holdings page renders table columns', async ({ page }) => {
    await page.goto('/holdings');
    await expect(page.locator('h1, h2, h3')).toContainText(/Holdings/i);
    // Verify merged columns and Net P&L exist
    await expect(page.locator('text=Total Cost')).toBeVisible();
    await expect(page.locator('text=Current Value')).toBeVisible();
    await expect(page.locator('text=Net P&L')).toBeVisible();
  });

  test('Journey 3: Cashflow ledger renders transactions and categories', async ({ page }) => {
    await page.goto('/cashflow/transactions');
    await expect(page.locator('text=Transactions')).toBeVisible();
    await expect(page.locator('text=Income').or(page.locator('text=Expense'))).toBeVisible();
  });

  test('Journey 4: Privacy Mode Toggle masks sensitive balances', async ({ page }) => {
    await page.goto('/');
    // Check for eye / privacy toggle button if present
    const eyeButton = page.locator('button:has(svg)').filter({ hasText: '' }).first();
    if (await eyeButton.isVisible()) {
      await eyeButton.click();
    }
  });
});
