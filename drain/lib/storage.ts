import fs from 'node:fs';
import path from 'node:path';
import { SpendItem, SpendMetrics, SpendBucket } from './types';
import { formatDateDisplay } from './dateUtils';

const DATA_DIR = path.join(process.cwd(), 'data');
const DATA_FILE = path.join(DATA_DIR, 'spends.json');

const INITIAL_SPENDS: SpendItem[] = [
  {
    id: 'seed-1',
    userId: 0,
    merchant: 'Coffee Shop',
    item: 'Coffee',
    date: '2026-10-26',
    formattedDate: 'Oct 26 2026',
    type: 'Wants',
    category: 'Food/Snacks and Drinks',
    amount: 4.00,
    currency: '$',
    rawInput: 'bought coffee for $4',
    source: 'text',
    createdAt: '2026-10-26T08:30:00.000Z',
  },
  {
    id: 'seed-2',
    userId: 0,
    merchant: 'Trader Joe\'s',
    item: 'Weekly Groceries',
    date: '2026-10-25',
    formattedDate: 'Oct 25 2026',
    type: 'Needs',
    category: 'Groceries',
    amount: 68.50,
    currency: '$',
    rawInput: 'Trader Joes weekly groceries $68.50',
    source: 'text',
    createdAt: '2026-10-25T14:15:00.000Z',
  },
  {
    id: 'seed-3',
    userId: 0,
    merchant: 'Metro Transit',
    item: 'Subway Pass',
    date: '2026-10-24',
    formattedDate: 'Oct 24 2026',
    type: 'Needs',
    category: 'Transportation',
    amount: 25.00,
    currency: '$',
    rawInput: 'Subway pass $25',
    source: 'text',
    createdAt: '2026-10-24T09:00:00.000Z',
  },
  {
    id: 'seed-4',
    userId: 0,
    merchant: 'Netflix',
    item: 'Monthly Subscription',
    date: '2026-10-23',
    formattedDate: 'Oct 23 2026',
    type: 'Wants',
    category: 'Subscriptions',
    amount: 15.99,
    currency: '$',
    rawInput: 'Netflix monthly subscription $15.99',
    source: 'text',
    createdAt: '2026-10-23T11:00:00.000Z',
  },
];

function ensureStorage(): void {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  if (!fs.existsSync(DATA_FILE)) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(INITIAL_SPENDS, null, 2), 'utf-8');
  }
}

export function getSpends(): SpendItem[] {
  ensureStorage();
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf-8');
    const items = JSON.parse(raw) as SpendItem[];
    // Ensure formattedDate is populated
    return items.map(item => ({
      ...item,
      formattedDate: item.formattedDate || formatDateDisplay(item.date),
    }));
  } catch (err) {
    console.error('Failed reading spends file:', err);
    return INITIAL_SPENDS;
  }
}

export function addSpend(item: Omit<SpendItem, 'id' | 'createdAt'> & { id?: string; createdAt?: string }): SpendItem {
  ensureStorage();
  const spends = getSpends();
  const newItem: SpendItem = {
    ...item,
    userId: item.userId ?? 0,
    id: item.id || `spend-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
    formattedDate: item.formattedDate || formatDateDisplay(item.date),
    createdAt: item.createdAt || new Date().toISOString(),
  };

  spends.unshift(newItem);
  fs.writeFileSync(DATA_FILE, JSON.stringify(spends, null, 2), 'utf-8');
  return newItem;
}

export function updateSpend(id: string, updates: Partial<SpendItem>): SpendItem | null {
  ensureStorage();
  const spends = getSpends();
  const idx = spends.findIndex(s => s.id === id);
  if (idx === -1) return null;

  const updated: SpendItem = {
    ...spends[idx],
    ...updates,
    formattedDate: updates.date ? formatDateDisplay(updates.date) : spends[idx].formattedDate,
  };
  spends[idx] = updated;
  fs.writeFileSync(DATA_FILE, JSON.stringify(spends, null, 2), 'utf-8');
  return updated;
}

export function deleteSpend(id: string): boolean {
  ensureStorage();
  const spends = getSpends();
  const filtered = spends.filter(s => s.id !== id);
  if (filtered.length === spends.length) return false;

  fs.writeFileSync(DATA_FILE, JSON.stringify(filtered, null, 2), 'utf-8');
  return true;
}

export function computeMetrics(items: SpendItem[]): SpendMetrics {
  let totalSpent = 0;
  const byBucket: Record<SpendBucket, number> = {
    Needs: 0,
    Wants: 0,
    Savings: 0,
    Debt: 0,
  };
  const byCategory: Record<string, number> = {};

  for (const item of items) {
    const amt = Number(item.amount) || 0;
    totalSpent += amt;
    const bucket = item.type || 'Wants';
    byBucket[bucket] = (byBucket[bucket] || 0) + amt;
    const cat = item.category || 'Miscellaneous';
    byCategory[cat] = (byCategory[cat] || 0) + amt;
  }

  const needsPercentage = totalSpent > 0 ? Math.round((byBucket['Needs'] / totalSpent) * 100) : 0;
  const wantsPercentage = totalSpent > 0 ? Math.round((byBucket['Wants'] / totalSpent) * 100) : 0;

  return {
    totalSpent: Math.round(totalSpent * 100) / 100,
    transactionCount: items.length,
    byBucket,
    byCategory,
    needsPercentage,
    wantsPercentage,
  };
}
