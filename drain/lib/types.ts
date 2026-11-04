export type SpendBucket = 'Needs' | 'Wants' | 'Savings' | 'Debt';

export interface SpendItem {
  id: string;
  userId?: number;
  merchant: string;
  item: string;
  date: string;            // YYYY-MM-DD
  formattedDate: string;   // e.g. "Oct 26 2026"
  type: SpendBucket;       // "Needs" | "Wants" | "Savings" | "Debt"
  category: string;        // e.g. "Food/Snacks and Drinks"
  amount: number;          // 4.00
  currency: string;        // "$"
  rawInput?: string;       // "bought coffee for $4"
  source: 'text' | 'receipt' | 'manual';
  engineUsed?: 'local' | 'gemini';
  receiptName?: string;
  createdAt: string;
}

export interface SpendClassification {
  merchant: string;
  item: string;
  date: string;
  formattedDate: string;
  type: SpendBucket;
  category: string;
  amount: number;
  confidence?: number;
  reasoning?: string;
  engineUsed?: 'local' | 'gemini';
  latencyMs?: number;
}

export interface SpendMetrics {
  totalSpent: number;
  transactionCount: number;
  byBucket: Record<SpendBucket, number>;
  byCategory: Record<string, number>;
  needsPercentage: number;
  wantsPercentage: number;
}
