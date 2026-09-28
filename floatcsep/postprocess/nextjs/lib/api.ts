import useSWR, { preload, type SWRConfiguration } from 'swr';
import type { ApiErrorBody, CatalogPayload, ForecastPayload } from './types';

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

export async function fetchJson<T>(url: string): Promise<T> {
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
  return response.json() as Promise<T>;
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
  return useSWR<ForecastPayload, ApiError>(key, fetchJson, DATA_OPTIONS);
}

/** Warm the SWR cache (e.g. the next time window) without rendering anything. */
export function prefetch(url: string): void {
  preload(url, fetchJson).catch(() => {
    // Errors surface when the data is actually requested.
  });
}
