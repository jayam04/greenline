import test from 'node:test';
import assert from 'node:assert/strict';
import { parseNaturalLanguageSpend } from '../lib/classifier';
import { computeMetrics } from '../lib/storage';
import { SpendItem } from '../lib/types';

test('parseNaturalLanguageSpend classifies "bought coffee for $4"', async () => {
  const result = await parseNaturalLanguageSpend('bought coffee for $4', '2026-10-26', 'local');
  assert.equal(result.merchant, 'Coffee Shop');
  assert.equal(result.item, 'Coffee');
  assert.equal(result.formattedDate, 'Oct 26 2026');
  assert.equal(result.type, 'Wants');
  assert.equal(result.category, 'Food/Snacks and Drinks');
  assert.equal(result.amount, 4);
  assert.equal(result.engineUsed, 'local');
  assert.ok(typeof result.latencyMs === 'number');
});

test('computeMetrics correctly aggregates amounts and percentages', () => {
  const sampleItems: SpendItem[] = [
    {
      id: '1',
      merchant: 'Coffee Shop',
      item: 'Coffee',
      date: '2026-10-26',
      formattedDate: 'Oct 26 2026',
      type: 'Wants',
      category: 'Food/Snacks and Drinks',
      amount: 4,
      currency: '$',
      source: 'text',
      createdAt: new Date().toISOString(),
    },
    {
      id: '2',
      merchant: 'Supermarket',
      item: 'Groceries',
      date: '2026-10-26',
      formattedDate: 'Oct 26 2026',
      type: 'Needs',
      category: 'Groceries',
      amount: 16,
      currency: '$',
      source: 'text',
      createdAt: new Date().toISOString(),
    },
  ];

  const metrics = computeMetrics(sampleItems);
  assert.equal(metrics.totalSpent, 20);
  assert.equal(metrics.transactionCount, 2);
  assert.equal(metrics.byBucket['Wants'], 4);
  assert.equal(metrics.byBucket['Needs'], 16);
  assert.equal(metrics.wantsPercentage, 20);
  assert.equal(metrics.needsPercentage, 80);
});
