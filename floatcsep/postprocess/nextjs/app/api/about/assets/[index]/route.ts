import { type NextRequest } from 'next/server';
import { loadAbout } from '@/lib/server/about';
import { errorResponse, fileResponse, HttpError } from '@/lib/server/http';
import { loadManifest } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/** An image referenced by about.md, by its position among the document's images. */
export async function GET(request: NextRequest, context: { params: Promise<{ index: string }> }) {
  try {
    const { index } = await context.params;
    const about = await loadAbout(await loadManifest());
    const file = /^\d+$/.test(index) ? about?.assets[Number(index)] : undefined;
    if (!file) throw new HttpError(404, 'Figure not found');
    return await fileResponse(request, file, request.nextUrl.searchParams.has('download'));
  } catch (error) {
    return errorResponse(error);
  }
}
