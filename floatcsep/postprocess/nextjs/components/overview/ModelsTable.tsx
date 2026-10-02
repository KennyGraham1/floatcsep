'use client';

import { Badge } from '@/components/ui/Badge';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { splitModelName } from '@/lib/modelGrid';
import type { Manifest, Model } from '@/lib/types';
import { doiUrl, gitWebUrl, zenodoUrl } from '@/lib/utils';

/** Where a model comes from, as plain text (for the CSV export). */
function sourceText(model: Model): string {
  if (model.giturl) return model.git_hash ? `${model.giturl} @ ${model.git_hash}` : model.giturl;
  if (model.zenodo_id) return `Zenodo ${String(model.zenodo_id)}`;
  return 'Local files';
}

function Source({ model }: { model: Model }) {
  if (model.giturl) {
    const web = gitWebUrl(model.giturl);
    const label = (web ?? model.giturl).replace(/^https?:\/\/(www\.)?/, '');
    return (
      <span className="flex min-w-0 flex-col">
        {web ? (
          <a href={web} target="_blank" rel="noopener noreferrer" className="link truncate" title={model.giturl}>
            {label}
          </a>
        ) : (
          <code className="truncate text-xs text-ink-2">{model.giturl}</code>
        )}
        {model.git_hash && <span className="font-mono text-2xs text-ink-3">@ {model.git_hash}</span>}
      </span>
    );
  }
  if (model.zenodo_id) {
    return (
      <a href={zenodoUrl(model.zenodo_id)} target="_blank" rel="noopener noreferrer" className="link">
        Zenodo {String(model.zenodo_id)}
      </a>
    );
  }
  return <span className="text-ink-3">Local files</span>;
}

export function ModelsTable({ manifest }: { manifest: Manifest }) {
  // A model on several grids is described once, e.g. in the configuration of one of them
  const described = new Map<string, string>();
  for (const m of manifest.models) {
    const base = splitModelName(m.name).model;
    if (m.description && !described.has(base)) described.set(base, m.description);
  }
  const description = (m: Model) => m.description ?? described.get(splitModelName(m.name).model) ?? null;
  // A time-dependent floatCSEP model, or any model with a different forecast in some window
  const variesInTime = (m: Model) => m.time_dependent || new Set(m.forecasts.filter(Boolean)).size > 1;

  const columns: Column<Model>[] = [
    {
      key: 'name',
      header: 'Model',
      sortValue: (m) => m.name.toLowerCase(),
      csv: (m) => m.name,
      render: (m) => (
        <span className="flex min-w-0 flex-col">
          <span className="font-medium">{m.name}</span>
          {m.path && <span className="truncate font-mono text-2xs text-ink-3">{m.path}</span>}
        </span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      sortValue: (m) => description(m) ?? '',
      render: (m) => {
        const text = description(m);
        return text ? (
          <span className="block min-w-[16rem] max-w-[28rem] whitespace-normal text-xs leading-5 text-ink-2">
            {text}
          </span>
        ) : (
          <span className="text-ink-3">—</span>
        );
      },
      csv: (m) => description(m),
    },
    {
      key: 'type',
      header: 'Forecast type',
      sortValue: (m) => (m.is_catalog_forecast ? 2 : 0) + (variesInTime(m) ? 1 : 0),
      render: (m) => (
        <span className="flex flex-wrap gap-1">
          <Badge tone={m.is_catalog_forecast ? 'info' : 'neutral'}>
            {m.is_catalog_forecast ? 'Catalog-based' : 'Gridded'}
          </Badge>
          {variesInTime(m) && <Badge tone="accent">Time-dependent</Badge>}
        </span>
      ),
      csv: (m) => `${m.is_catalog_forecast ? 'Catalog-based' : 'Gridded'}${variesInTime(m) ? ', time-dependent' : ''}`,
    },
    {
      key: 'source',
      header: 'Source',
      render: (m) => <Source model={m} />,
      csv: sourceText,
      className: 'max-w-[18rem]',
    },
    {
      key: 'forecasts',
      header: 'Forecasts',
      align: 'right',
      numeric: true,
      sortValue: (m) => m.forecast_available.filter(Boolean).length,
      render: (m) => {
        const available = m.forecast_available.filter(Boolean).length;
        const total = m.forecasts.filter(Boolean).length;
        return (
          <span className={available < total ? 'text-warning' : undefined}>
            {available} / {total}
          </span>
        );
      },
    },
    {
      key: 'doi',
      header: 'DOI',
      render: (m) =>
        m.doi ? (
          <a href={doiUrl(m.doi)} target="_blank" rel="noopener noreferrer" className="link">
            {m.doi}
          </a>
        ) : (
          <span className="text-ink-3">—</span>
        ),
    },
  ];

  return (
    <DataTable
      caption="Models of the experiment"
      columns={columns}
      rows={manifest.models}
      rowKey={(m) => m.name}
      empty="This experiment has no models."
    />
  );
}
