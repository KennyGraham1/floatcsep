import fs from 'fs/promises';
import { NextResponse } from 'next/server';
import { errorResponse, HttpError, notModified } from '@/lib/server/http';
import { loadManifest, resolveFromRoot } from '@/lib/server/manifest';
import { cachedPythonJob, sourceKey } from '@/lib/server/python';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/** The experiment's observed catalog (the file listed in the manifest). */
export async function GET(request: Request) {
  try {
    const { manifest, appRoot } = await loadManifest();
    if (!manifest.catalog.path) {
      throw new HttpError(404, 'This experiment has no catalog');
    }
    if (!manifest.catalog.available) {
      throw new HttpError(404, `Catalog file not found: ${manifest.catalog.path}`);
    }

    const file = resolveFromRoot(appRoot, manifest.catalog.path);
    const key = await sourceKey('catalog', file);
    const etag = `"${key}"`;
    const cachedResponse = notModified(request, etag);
    if (cachedResponse) return cachedResponse;

    const out = await cachedPythonJob(key, ['catalog', '--path', file]);
    return new NextResponse(await fs.readFile(out), {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'private, no-cache',
        ETag: etag,
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
