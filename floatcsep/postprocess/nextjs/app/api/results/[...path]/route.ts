import path from 'path';
import { type NextRequest } from 'next/server';
import { errorResponse, fileResponse, HttpError } from '@/lib/server/http';
import { loadManifest, resolveFromRoot } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/** A result figure. Only files listed in the manifest are served. */
export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try {
    const { path: segments } = await context.params;
    const { appRoot, figures } = await loadManifest();

    const candidates = [segments.join('/'), segments.map(safeDecode).join('/')].map((p) => path.posix.normalize(p));
    const relative = candidates.find((p) => figures.has(p));
    if (!relative) throw new HttpError(404, 'Figure not found');

    return await fileResponse(
      request,
      resolveFromRoot(appRoot, relative),
      request.nextUrl.searchParams.has('download'),
    );
  } catch (error) {
    return errorResponse(error);
  }
}
