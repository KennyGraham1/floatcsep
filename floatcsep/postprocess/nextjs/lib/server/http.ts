import fs from 'fs/promises';
import path from 'path';
import { NextResponse } from 'next/server';
import type { ApiErrorBody } from '@/lib/types';

const CONTENT_TYPES: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
};

/** An error with the HTTP status the API should answer with. */
export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

export function errorResponse(error: unknown): NextResponse<ApiErrorBody> {
  if (error instanceof HttpError) {
    if (error.status >= 500) console.error(`[dashboard] ${error.message}`, error.details ?? '');
    return NextResponse.json(
      { error: error.message, ...(error.details ? { details: error.details } : {}) },
      { status: error.status, headers: { 'Cache-Control': 'no-store' } },
    );
  }
  console.error('[dashboard] Unexpected error', error);
  return NextResponse.json(
    { error: 'Unexpected server error', details: String(error) },
    { status: 500, headers: { 'Cache-Control': 'no-store' } },
  );
}

/** A 304 answer when the client's cached copy (If-None-Match) is still current. */
export function notModified(request: Request, etag: string): NextResponse | null {
  const header = request.headers.get('if-none-match');
  if (!header) return null;
  const tags = header.split(',').map((tag) => tag.trim());
  if (!tags.includes(etag) && !tags.includes('*')) return null;
  return new NextResponse(null, { status: 304, headers: { ETag: etag } });
}

/** A figure file with caching headers (ETag, 304); SVG files are sandboxed. */
export async function fileResponse(request: Request, file: string, download = false): Promise<NextResponse> {
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
  if (download) {
    const name = path.basename(file).replace(/"/g, '');
    headers['Content-Disposition'] =
      `attachment; filename="${name}"; filename*=UTF-8''${encodeURIComponent(path.basename(file))}`;
  }
  return new NextResponse(await fs.readFile(file), { headers });
}
