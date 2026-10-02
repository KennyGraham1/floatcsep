import fs from 'fs/promises';
import { NextResponse, type NextRequest } from 'next/server';
import { errorResponse, HttpError, notModified } from '@/lib/server/http';
import { loadManifest, resolveFromRoot } from '@/lib/server/manifest';
import { cachedPythonJob, sourceKey } from '@/lib/server/python';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * The rate of every cell of a forecast evaluated outside floatCSEP (?model=<i>, and
 * &window=<j> for a model with a forecast per window), per forecast unit, as
 * little-endian float32: millions of cells are too many for JSON. The forecast
 * document of each time window gives the factor to apply.
 */
export async function GET(request: NextRequest) {
  try {
    const { manifest, manifestPath, appRoot } = await loadManifest();
    const raw = request.nextUrl.searchParams.get('model');
    const modelIndex = raw === null ? NaN : Number(raw);
    if (!Number.isInteger(modelIndex) || modelIndex < 0 || modelIndex >= manifest.models.length) {
      throw new HttpError(400, 'Invalid "model" parameter');
    }
    const model = manifest.models[modelIndex];
    const rawWindow = request.nextUrl.searchParams.get('window');
    const window = rawWindow === null ? model.forecast_available.findIndex(Boolean) : Number(rawWindow);
    if (!Number.isInteger(window) || window < -1 || window >= manifest.time_windows.length) {
      throw new HttpError(400, 'Invalid "window" parameter');
    }
    if (!model.external || window < 0 || !model.forecast_available[window]) {
      throw new HttpError(404, `${model.name} has no cell-rate file`);
    }

    const file = resolveFromRoot(appRoot, model.forecasts[window]!);
    const key = await sourceKey('rates', file, model.external.grid);
    const etag = `"${key}"`;
    const cachedResponse = notModified(request, etag);
    if (cachedResponse) return cachedResponse;

    const out = await cachedPythonJob(
      key,
      ['rates', '--manifest', manifestPath, '--model', String(modelIndex), '--window', String(window)],
      '.f32',
    );
    return new NextResponse(await fs.readFile(out), {
      headers: {
        'Content-Type': 'application/octet-stream',
        'Cache-Control': 'private, no-cache',
        'X-Content-Type-Options': 'nosniff',
        ETag: etag,
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
