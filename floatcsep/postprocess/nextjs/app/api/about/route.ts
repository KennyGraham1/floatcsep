import { NextResponse, type NextRequest } from 'next/server';
import { loadAbout } from '@/lib/server/about';
import { errorResponse, HttpError, notModified } from '@/lib/server/http';
import { loadManifest } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/** The experiment's about.md, with its images linked to /api/about/assets/<n>. */
export async function GET(request: NextRequest) {
  try {
    const about = await loadAbout(await loadManifest());
    if (!about) throw new HttpError(404, 'This experiment has no about.md');
    const cachedResponse = notModified(request, about.etag);
    if (cachedResponse) return cachedResponse;
    return NextResponse.json(
      { markdown: about.markdown },
      { headers: { ETag: about.etag, 'Cache-Control': 'private, no-cache' } },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
