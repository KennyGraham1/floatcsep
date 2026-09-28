import { NextResponse } from 'next/server';
import type { ApiErrorBody } from '@/lib/types';

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
