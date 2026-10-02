import useSWR, { preload, type SWRConfiguration } from 'swr';
import type { ApiErrorBody, CatalogPayload, EvaluationSummary, ForecastPayload } from './types';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request(url: string): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch (error) {
    throw new ApiError(0, 'Could not reach the dashboard server', String(error));
  }
  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = await response.json();
    } catch {
      // not a JSON error body
    }
    throw new ApiError(response.status, body.error || `Request failed (${response.status})`, body.details);
  }
  return response;
}

export async function fetchJson<T>(url: string): Promise<T> {
  return (await request(url)).json() as Promise<T>;
}

// The cell rates of dense forecasts, per model and file: the same for every time
// window (each window's document gives its factor), so fetched once. Each is tens of
// megabytes, so only the last few models viewed are kept.
const denseRates = new Map<string, Promise<Float32Array>>();
const DENSE_RATES_KEPT = 2;

/** A forecast document; for dense grids, with the rate of every cell attached. */
async function fetchForecast(url: string): Promise<ForecastPayload> {
  const payload = await fetchJson<ForecastPayload>(url);
  if (payload.grid !== 'dense') return payload;
  const model = new URL(url, 'http://dashboard').searchParams.get('model');
  const key = `${model}:${payload.path}`;
  let rates = denseRates.get(key);
  if (rates) {
    denseRates.delete(key); // most recently used last
  } else {
    rates = request(`/api/forecasts/rates?model=${model}`).then(async (r) => new Float32Array(await r.arrayBuffer()));
    rates.catch(() => denseRates.delete(key));
  }
  denseRates.set(key, rates);
  while (denseRates.size > DENSE_RATES_KEPT) denseRates.delete(denseRates.keys().next().value!);

  const rateData = await rates;
  const cells = (payload.nx ?? 0) * (payload.ny ?? 0);
  if (rateData.length !== cells) {
    throw new Error(
      `The forecast has ${rateData.length.toLocaleString('en-US')} cell rates for a grid of ${cells.toLocaleString('en-US')} cells`,
    );
  }
  return { ...payload, rateData };
}

// Catalogs and forecasts only change when the experiment is re-run, and loading
// them can take a while (Python parsing), so never refetch in the background.
const DATA_OPTIONS: SWRConfiguration = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
  shouldRetryOnError: false,
  keepPreviousData: true,
  dedupingInterval: 10 * 60_000,
};

export const CATALOG_URL = '/api/catalog';

export function forecastUrl(model: number, window: number): string {
  return `/api/forecasts?model=${model}&window=${window}`;
}

export function useCatalog(enabled = true) {
  return useSWR<CatalogPayload, ApiError>(enabled ? CATALOG_URL : null, fetchJson, DATA_OPTIONS);
}

export function useForecast(model: number | null, window: number | null) {
  const key = model !== null && window !== null ? forecastUrl(model, window) : null;
  return useSWR<ForecastPayload, ApiError>(key, fetchForecast, DATA_OPTIONS);
}

/** Warm the SWR cache with a forecast (e.g. the next time window). */
export function prefetchForecast(model: number, window: number): void {
  preload(forecastUrl(model, window), fetchForecast).catch(() => {
    // Errors surface when the forecast is actually requested.
  });
}

export function useEvaluations(enabled = true) {
  return useSWR<EvaluationSummary[], ApiError>(enabled ? '/api/evaluations' : null, fetchJson, DATA_OPTIONS);
}

/** The experiment's about.md, with its images linked to /api/about/assets/<n>. */
export function useAbout(enabled = true) {
  return useSWR<{ markdown: string }, ApiError>(enabled ? '/api/about' : null, fetchJson, DATA_OPTIONS);
}

/** Warm the SWR cache (e.g. the next time window) without rendering anything. */
export function prefetch(url: string): void {
  preload(url, fetchJson).catch(() => {
    // Errors surface when the data is actually requested.
  });
}
