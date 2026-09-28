import fs from 'fs/promises';
import path from 'path';
import { NextResponse, type NextRequest } from 'next/server';
import { errorResponse, HttpError, notModified } from '@/lib/server/http';
import { loadManifest, resolveFromRoot } from '@/lib/server/manifest';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const CONTENT_TYPES: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
};

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

    const file = resolveFromRoot(appRoot, relative);
    let stat;
    try {
      stat = await fs.stat(file);
    } catch {
      throw new HttpError(404, 'Figure not found');
    }

    const etag = `W/"${stat.size.toString(16)}-${Math.floor(stat.mtimeMs).toString(16)}"`;
    const cachedResponse = notModified(request, etag);
    if (cachedResponse) return cachedResponse;

    const extension = path.extname(file).toLowerCase();
    const headers: Record<string, string> = {
      'Content-Type': CONTENT_TYPES[extension] ?? 'application/octet-stream',
      'Cache-Control': 'private, no-cache',
      'Last-Modified': stat.mtime.toUTCString(),
      'X-Content-Type-Options': 'nosniff',
      ETag: etag,
    };
    if (extension === '.svg') {
      headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox";
    }
    if (request.nextUrl.searchParams.has('download')) {
      const name = path.basename(file).replace(/"/g, '');
      headers['Content-Disposition'] =
        `attachment; filename="${name}"; filename*=UTF-8''${encodeURIComponent(path.basename(file))}`;
    }

    return new NextResponse(await fs.readFile(file), { headers });
  } catch (error) {
    return errorResponse(error);
  }
}
