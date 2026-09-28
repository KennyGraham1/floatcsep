import fs from 'fs/promises';
import { NextResponse, type NextRequest } from 'next/server';
import { errorResponse, HttpError, notModified } from '@/lib/server/http';
import { loadManifest, resolveFromRoot } from '@/lib/server/manifest';
import { cachedPythonJob, sourceKey } from '@/lib/server/python';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function indexParam(request: NextRequest, name: string, size: number): number {
  const raw = request.nextUrl.searchParams.get(name);
  const value = raw === null ? NaN : Number(raw);
  if (!Number.isInteger(value) || value < 0 || value >= size) {
    throw new HttpError(400, `Invalid "${name}" parameter`);
  }
  return value;
}

/** Cell rates of one model's forecast for one time window: ?model=<i>&window=<j>. */
export async function GET(request: NextRequest) {
  try {
    const { manifest, manifestPath, appRoot } = await loadManifest();
    const modelIndex = indexParam(request, 'model', manifest.models.length);
    const windowIndex = indexParam(request, 'window', manifest.time_windows.length);

    const model = manifest.models[modelIndex];
    const relative = model.forecasts[windowIndex];
    if (!relative) {
      throw new HttpError(404, `${model.name} has no forecast for ${manifest.time_windows[windowIndex]}`);
    }
    if (!model.forecast_available[windowIndex]) {
      throw new HttpError(404, `Forecast file not found: ${relative}`);
    }

    const file = resolveFromRoot(appRoot, relative);
    const region = manifest.region;
    // Catalog forecasts are binned onto the experiment grid, so it is part of the key.
    const key = await sourceKey('forecast', file, {
      catalog: model.is_catalog_forecast,
      nSims: model.func_kwargs?.n_sims ?? null,
      grid: model.is_catalog_forecast ? [region?.dh, region?.origins?.length, region?.bbox, manifest.magnitudes] : null,
    });
    const etag = `"${key}"`;
    const cachedResponse = notModified(request, etag);
    if (cachedResponse) return cachedResponse;

    const out = await cachedPythonJob(key, [
      'forecast',
      '--manifest',
      manifestPath,
      '--model',
      String(modelIndex),
      '--window',
      String(windowIndex),
    ]);
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
