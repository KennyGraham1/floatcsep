'use client';

import { useManifest } from '@/lib/contexts/ManifestContext';

// Safe render helper
function safe(value: any): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    if (Array.isArray(value)) return value.join(', ');
    return JSON.stringify(value);
  }
  return String(value);
}

export default function ExperimentPage() {
  const { manifest, isLoading, error } = useManifest();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-400">Loading experiment data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center text-red-400">
          <p className="text-xl font-semibold mb-2">Error loading experiment</p>
          <p className="text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-gray-400">No experiment data available</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">{safe(manifest.name)}</h1>
        <p className="text-gray-400">{safe(manifest.date_range)}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Metadata */}
        <div className="bg-surface p-6 rounded-lg border border-border">
          <h2 className="text-xl font-semibold mb-4">Metadata</h2>
          <div className="space-y-2 text-sm">
            {manifest.authors && (
              <p><span className="text-gray-400">Authors:</span> {safe(manifest.authors)}</p>
            )}
            {manifest.exp_class && (
              <p><span className="text-gray-400">Class:</span> {safe(manifest.exp_class)}</p>
            )}
            <p><span className="text-gray-400">Start:</span> {safe(manifest.start_date)}</p>
            <p><span className="text-gray-400">End:</span> {safe(manifest.end_date)}</p>
          </div>
        </div>

        {/* Region */}
        <div className="bg-surface p-6 rounded-lg border border-border">
          <h2 className="text-xl font-semibold mb-4">Region</h2>
          <div className="space-y-2 text-sm">
            {manifest.region?.name && (
              <p><span className="text-gray-400">Name:</span> {safe(manifest.region.name)}</p>
            )}
            <p><span className="text-gray-400">Magnitude:</span> [{safe(manifest.mag_min)}, {safe(manifest.mag_max)}]</p>
            {manifest.depth_min !== null && (
              <p><span className="text-gray-400">Depth:</span> [{safe(manifest.depth_min)}, {safe(manifest.depth_max)}] km</p>
            )}
          </div>
        </div>

        {/* Models */}
        <div className="bg-surface p-6 rounded-lg border border-border">
          <h2 className="text-xl font-semibold mb-4">Models ({manifest.models?.length || 0})</h2>
          <div className="space-y-3">
            {manifest.models?.filter((m: any) => m && typeof m === 'object' && m.name).map((model: any, idx: number) => (
              <div key={idx} className="border-l-2 border-primary pl-3">
                <h3 className="font-semibold text-sm">{safe(model.name)}</h3>
                {model.doi && (
                  <p className="text-xs text-gray-400">DOI: {safe(model.doi)}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Tests */}
        <div className="bg-surface p-6 rounded-lg border border-border">
          <h2 className="text-xl font-semibold mb-4">Tests ({manifest.tests?.length || 0})</h2>
          <div className="space-y-3">
            {manifest.tests?.filter((t: any) => t && typeof t === 'object' && t.name).map((test: any, idx: number) => (
              <div key={idx} className="border-l-2 border-secondary pl-3">
                <h3 className="font-semibold text-sm">{safe(test.name)}</h3>
                {test.func && (
                  <p className="text-xs text-gray-400 font-mono">{safe(test.func)}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Time Windows */}
      <div className="bg-surface p-6 rounded-lg border border-border">
        <h2 className="text-xl font-semibold mb-4">Time Windows ({manifest.time_windows?.length || 0})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
          {manifest.time_windows?.filter((tw: any) => tw && typeof tw === 'string').map((tw: string, idx: number) => (
            <div key={idx} className="bg-background p-2 rounded">
              <span className="text-primary font-semibold">T{idx + 1}:</span> {safe(tw)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
