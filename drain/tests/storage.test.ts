import test from 'node:test';
import assert from 'node:assert/strict';
import { getSpends, addSpend, updateSpend, deleteSpend } from '../lib/storage';

test('storage CRUD operations succeed', () => {
  const testId = `test-${Date.now()}`;

  const created = addSpend({
    id: testId,
    merchant: 'Test Roasters',
    item: 'Latte',
    date: '2026-10-26',
    formattedDate: 'Oct 26 2026',
    type: 'Wants',
    category: 'Food/Snacks and Drinks',
    amount: 5.50,
    currency: '$',
    source: 'manual',
  });

  assert.equal(created.id, testId);
  assert.equal(created.amount, 5.50);

  const updated = updateSpend(testId, { amount: 6.00, item: 'Vanilla Latte' });
  assert.ok(updated);
  assert.equal(updated.amount, 6.00);
  assert.equal(updated.item, 'Vanilla Latte');

  const deleted = deleteSpend(testId);
  assert.equal(deleted, true);

  const finalSpends = getSpends();
  assert.ok(!finalSpends.some(s => s.id === testId));
});
