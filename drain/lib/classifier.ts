import { GoogleGenAI } from '@google/genai';
import { SpendClassification, SpendBucket } from './types';
import { formatDateDisplay, getTodayIso } from './dateUtils';

const DEFAULT_CATEGORIES = [
  'Food/Snacks and Drinks',
  'Groceries',
  'Housing & Utilities',
  'Transportation',
  'Shopping & Entertainment',
  'Health & Wellness',
  'Subscriptions',
  'Personal Care',
  'Travel',
  'Miscellaneous',
];

interface GeminiReceiptItem {
  merchant?: string;
  item?: string;
  date?: string;
  type?: string;
  category?: string;
  amount?: number | string;
}

export async function parseNaturalLanguageSpend(
  input: string,
  referenceDateIso: string = getTodayIso(),
  enginePreference: 'auto' | 'local' | 'gemini' = 'auto'
): Promise<SpendClassification> {
  const startTime = Date.now();
  const apiKey = process.env.GEMINI_API_KEY?.trim();

  // If local engine is explicitly chosen or API key is absent
  if (enginePreference === 'local' || !apiKey) {
    const result = classifyWithRules(input, referenceDateIso);
    result.engineUsed = 'local';
    result.latencyMs = Math.max(1, Date.now() - startTime);
    return result;
  }

  // Attempt Gemini classification
  try {
    const result = await classifyWithGemini(input, referenceDateIso, apiKey);
    result.engineUsed = 'gemini';
    result.latencyMs = Date.now() - startTime;
    return result;
  } catch (err) {
    console.warn('Gemini call failed or timed out, falling back to instant local engine:', err);
    const fallbackResult = classifyWithRules(input, referenceDateIso);
    fallbackResult.engineUsed = 'local';
    fallbackResult.latencyMs = Math.max(1, Date.now() - startTime);
    return fallbackResult;
  }
}

async function classifyWithGemini(
  input: string,
  referenceDateIso: string,
  apiKey: string
): Promise<SpendClassification> {
  const ai = new GoogleGenAI({ apiKey });

  const prompt = `You are an expert personal finance assistant for Greenline Spends.
Classify the user's spend description into structured financial transaction details.

Context:
- Current Reference Date: ${referenceDateIso} (${formatDateDisplay(referenceDateIso)})
- Available Spend Buckets: "Needs" (essential necessities, groceries, rent, utilities), "Wants" (dining out, coffee, entertainment, impulse shopping), "Savings" (investments, emergency fund), "Debt" (loan payment, credit card interest).
- Standard Categories: ${DEFAULT_CATEGORIES.join(', ')}.

Rules:
1. Extract merchant name (e.g. "Coffee Shop", "Subway", "Uber", "Target").
2. Extract the specific item or description (e.g. "Coffee", "Groceries", "Lunch").
3. Determine transaction date (YYYY-MM-DD). If not specified, use reference date: ${referenceDateIso}.
4. Assign type: "Needs", "Wants", "Savings", or "Debt".
5. Assign the best fitting category.
6. Extract numeric amount (e.g. 4.00).

User input: "${input}"

Respond ONLY with valid JSON conforming to:
{
  "merchant": string,
  "item": string,
  "date": "YYYY-MM-DD",
  "type": "Needs" | "Wants" | "Savings" | "Debt",
  "category": string,
  "amount": number,
  "confidence": number,
  "reasoning": string
}`;

  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: prompt,
    config: {
      responseMimeType: 'application/json',
    },
  });

  const text = response.text?.trim() || '{}';
  const parsed = JSON.parse(text);

  const dateIso = parsed.date || referenceDateIso;
  return {
    merchant: parsed.merchant || 'Store',
    item: parsed.item || input,
    date: dateIso,
    formattedDate: formatDateDisplay(dateIso),
    type: validateBucket(parsed.type),
    category: parsed.category || 'Miscellaneous',
    amount: typeof parsed.amount === 'number' ? parsed.amount : parseFloat(parsed.amount) || 0,
    confidence: parsed.confidence || 0.95,
    reasoning: parsed.reasoning || 'Classified with Gemini 2.5 Flash',
  };
}

export function classifyWithRules(
  input: string,
  referenceDateIso: string = getTodayIso()
): SpendClassification {
  const lower = input.toLowerCase().trim();

  // Extract amount ($XX.XX or XX dollars or for $XX)
  let amount = 0;
  const amountMatch = input.match(/\$?\s*([0-9]+(?:\.[0-9]{1,2})?)/);
  if (amountMatch) {
    amount = parseFloat(amountMatch[1]);
  }

  let merchant = 'Store';
  let item = input;
  let type: SpendBucket = 'Wants';
  let category = 'Miscellaneous';

  if (lower.includes('coffee')) {
    merchant = 'Coffee Shop';
    item = 'Coffee';
    type = 'Wants';
    category = 'Food/Snacks and Drinks';
  } else if (lower.includes('grocer') || lower.includes('supermarket') || lower.includes('milk') || lower.includes('eggs')) {
    merchant = 'Grocery Store';
    item = 'Groceries';
    type = 'Needs';
    category = 'Groceries';
  } else if (lower.includes('uber') || lower.includes('lyft') || lower.includes('taxi') || lower.includes('gas') || lower.includes('metro')) {
    merchant = lower.includes('uber') ? 'Uber' : lower.includes('lyft') ? 'Lyft' : 'Gas Station';
    item = 'Transportation';
    type = 'Needs';
    category = 'Transportation';
  } else if (lower.includes('lunch') || lower.includes('dinner') || lower.includes('burger') || lower.includes('pizza') || lower.includes('restaurant')) {
    merchant = 'Restaurant';
    item = 'Dining';
    type = 'Wants';
    category = 'Food/Snacks and Drinks';
  } else if (lower.includes('rent') || lower.includes('electric') || lower.includes('water') || lower.includes('utility') || lower.includes('wifi')) {
    merchant = 'Utility Provider';
    item = 'Utilities';
    type = 'Needs';
    category = 'Housing & Utilities';
  } else if (lower.includes('netflix') || lower.includes('spotify') || lower.includes('hulu') || lower.includes('subscription')) {
    merchant = lower.includes('netflix') ? 'Netflix' : lower.includes('spotify') ? 'Spotify' : 'Subscription Service';
    item = 'Subscription';
    type = 'Wants';
    category = 'Subscriptions';
  }

  // Handle at/from merchant detection (e.g. "coffee at starbucks")
  const atMatch = input.match(/(?:at|from)\s+([A-Za-z0-9&'\s]+?)(?:\s+(?:for|\$|yesterday|today|on)|$)/i);
  if (atMatch && atMatch[1].trim()) {
    merchant = atMatch[1].trim();
  }

  return {
    merchant,
    item,
    date: referenceDateIso,
    formattedDate: formatDateDisplay(referenceDateIso),
    type,
    category,
    amount,
    confidence: 0.95,
    reasoning: 'Classified in <5ms via Instant Local NLP Engine',
  };
}

export async function parseReceiptWithGemini(
  base64Data: string,
  mimeType: string,
  referenceDateIso: string = getTodayIso()
): Promise<SpendClassification[]> {
  const apiKey = process.env.GEMINI_API_KEY?.trim();
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is not configured. Please add it to .env.local to enable receipt bill scanning.');
  }

  const ai = new GoogleGenAI({ apiKey });

  const prompt = `Analyze this receipt or bill image and extract transaction items.
Context:
- Reference Date: ${referenceDateIso}
- Categorize each item into: "Needs", "Wants", "Savings", or "Debt".
- Assign standard categories: ${DEFAULT_CATEGORIES.join(', ')}.

Respond ONLY with valid JSON conforming to:
{
  "merchant": string,
  "date": "YYYY-MM-DD",
  "items": [
    {
      "merchant": string,
      "item": string,
      "date": "YYYY-MM-DD",
      "type": "Needs" | "Wants" | "Savings" | "Debt",
      "category": string,
      "amount": number
    }
  ],
  "total": number
}`;

  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: [
      {
        text: prompt,
      },
      {
        inlineData: {
          mimeType,
          data: base64Data,
        },
      },
    ],
    config: {
      responseMimeType: 'application/json',
    },
  });

  const parsed = JSON.parse(response.text?.trim() || '{}');
  const merchant = parsed.merchant || 'Merchant';
  const billDate = parsed.date || referenceDateIso;

  if (Array.isArray(parsed.items) && parsed.items.length > 0) {
    return parsed.items.map((it: GeminiReceiptItem) => ({
      merchant: it.merchant || merchant,
      item: it.item || 'Item',
      date: it.date || billDate,
      formattedDate: formatDateDisplay(it.date || billDate),
      type: validateBucket(it.type),
      category: it.category || 'Miscellaneous',
      amount: typeof it.amount === 'number' ? it.amount : parseFloat(String(it.amount || 0)) || 0,
      confidence: 0.95,
      reasoning: 'Extracted from receipt image via Gemini Vision',
    }));
  }

  return [
    {
      merchant,
      item: 'Receipt Total',
      date: billDate,
      formattedDate: formatDateDisplay(billDate),
      type: 'Needs',
      category: 'Shopping & Entertainment',
      amount: parsed.total || 0,
      confidence: 0.9,
      reasoning: 'Extracted total from receipt image via Gemini Vision',
    },
  ];
}

function validateBucket(b: unknown): SpendBucket {
  if (typeof b === 'string' && ['Needs', 'Wants', 'Savings', 'Debt'].includes(b)) {
    return b as SpendBucket;
  }
  return 'Wants';
}
