import { NextResponse } from 'next/server';
import { parseNaturalLanguageSpend } from '@/lib/classifier';
import { addSpend } from '@/lib/storage';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const text = body.text?.trim();

    if (!text) {
      return NextResponse.json({ error: 'Spend description text is required' }, { status: 400 });
    }

    const referenceDate = body.referenceDate || new Date().toISOString().split('T')[0];
    const enginePreference = body.engine || 'auto';
    const classification = await parseNaturalLanguageSpend(text, referenceDate, enginePreference);

    let savedItem = null;
    if (body.autoSave !== false) {
      savedItem = addSpend({
        merchant: classification.merchant,
        item: classification.item,
        date: classification.date,
        formattedDate: classification.formattedDate,
        type: classification.type,
        category: classification.category,
        amount: classification.amount,
        currency: body.currency || '$',
        rawInput: text,
        source: 'text',
        engineUsed: classification.engineUsed,
      });
    }

    return NextResponse.json({
      classification,
      item: savedItem,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed classifying spend';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
