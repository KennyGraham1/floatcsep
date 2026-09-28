'use client';

import { createContext, useContext, type ReactNode } from 'react';
import useSWR, { type KeyedMutator } from 'swr';
import { ApiError, fetchJson } from '../api';
import type { Manifest } from '../types';

interface ManifestContextType {
  manifest: Manifest | null;
  isLoading: boolean;
  error: ApiError | undefined;
  reload: KeyedMutator<Manifest>;
}

const ManifestContext = createContext<ManifestContextType | undefined>(undefined);

export function ManifestProvider({ children }: { children: ReactNode }) {
  const { data, error, isLoading, mutate } = useSWR<Manifest, ApiError>('/api/manifest', fetchJson, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });

  return (
    <ManifestContext.Provider value={{ manifest: data ?? null, isLoading, error, reload: mutate }}>
      {children}
    </ManifestContext.Provider>
  );
}

export function useManifest() {
  const context = useContext(ManifestContext);
  if (!context) {
    throw new Error('useManifest must be used within ManifestProvider');
  }
  return context;
}

/** For pages rendered by AppShell, which only renders them once the manifest loaded. */
export function useLoadedManifest(): Manifest {
  const { manifest } = useManifest();
  if (!manifest) throw new Error('The experiment manifest is not loaded');
  return manifest;
}
