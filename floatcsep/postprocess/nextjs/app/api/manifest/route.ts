import { NextResponse } from 'next/server';
import { errorResponse } from '@/lib/server/http';
import { loadManifest } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const { manifest } = await loadManifest();
    return NextResponse.json(manifest, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    return errorResponse(error);
  }
}
