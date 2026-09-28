import { NextResponse } from 'next/server';
import { evaluationSummaries } from '@/lib/server/evaluations';
import { errorResponse, notModified } from '@/lib/server/http';
import { loadManifest } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/** Condensed evaluation results of the experiment, for the charts. */
export async function GET(request: Request) {
  try {
    const loaded = await loadManifest();
    const { summaries, etag } = await evaluationSummaries(loaded);
    const cachedResponse = notModified(request, etag);
    if (cachedResponse) return cachedResponse;
    return NextResponse.json(summaries, {
      headers: { 'Cache-Control': 'private, no-cache', ETag: etag },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
