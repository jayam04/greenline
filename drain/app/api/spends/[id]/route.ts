import { NextResponse } from 'next/server';
import { updateSpend, deleteSpend } from '@/lib/storage';

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const updated = updateSpend(id, body);

    if (!updated) {
      return NextResponse.json({ error: 'Spend not found' }, { status: 404 });
    }

    return NextResponse.json({ item: updated });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed updating spend';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const ok = deleteSpend(id);

    if (!ok) {
      return NextResponse.json({ error: 'Spend not found' }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed deleting spend';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
