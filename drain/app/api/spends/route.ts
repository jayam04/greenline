import { NextResponse } from 'next/server';
import { getSpends, addSpend, computeMetrics } from '@/lib/storage';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const search = searchParams.get('search')?.toLowerCase().trim();
    const bucket = searchParams.get('bucket')?.trim();
    const category = searchParams.get('category')?.trim();

    let items = getSpends();

    if (search) {
      items = items.filter(
        item =>
          item.merchant.toLowerCase().includes(search) ||
          item.item.toLowerCase().includes(search) ||
          item.category.toLowerCase().includes(search) ||
          (item.rawInput && item.rawInput.toLowerCase().includes(search))
      );
    }

    if (bucket && bucket !== 'all') {
      items = items.filter(item => item.type === bucket);
    }

    if (category && category !== 'all') {
      items = items.filter(item => item.category === category);
    }

    const allItems = getSpends();
    const metrics = computeMetrics(allItems);

    return NextResponse.json({
      items,
      metrics,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed fetching spends';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    if (!body.item || body.amount === undefined) {
      return NextResponse.json({ error: 'Item description and amount are required' }, { status: 400 });
    }

    const created = addSpend({
      merchant: body.merchant || 'Store',
      item: body.item,
      date: body.date || new Date().toISOString().split('T')[0],
      formattedDate: body.formattedDate,
      type: body.type || 'Wants',
      category: body.category || 'Miscellaneous',
      amount: parseFloat(body.amount) || 0,
      currency: body.currency || '$',
      rawInput: body.rawInput,
      source: body.source || 'manual',
      receiptName: body.receiptName,
    });

    return NextResponse.json({ item: created }, { status: 201 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed creating spend';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
