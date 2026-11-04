import { NextResponse } from 'next/server';

export async function GET() {
  const hasKey = Boolean(process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY.trim().length > 0);
  return NextResponse.json({
    geminiConfigured: hasKey,
    model: 'gemini-3.8-flash',
  });
}
