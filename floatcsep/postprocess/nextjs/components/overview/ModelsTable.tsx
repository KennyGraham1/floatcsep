'use client';

import { Badge } from '@/components/ui/Badge';
import { DataTable, type Column } from '@/components/ui/DataTable';
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
  const columns: Column<Model>[] = [
    {
      key: 'name',
      header: 'Model',
      sortValue: (m) => m.name.toLowerCase(),
      render: (m) => (
        <span className="flex min-w-0 flex-col">
          <span className="font-medium">{m.name}</span>
          {m.path && <span className="truncate font-mono text-2xs text-ink-3">{m.path}</span>}
        </span>
      ),
    },
    {
      key: 'type',
      header: 'Forecast type',
      sortValue: (m) => (m.is_catalog_forecast ? 1 : 0),
      render: (m) => (
        <Badge tone={m.is_catalog_forecast ? 'info' : 'neutral'}>
          {m.is_catalog_forecast ? 'Catalog-based' : 'Gridded'}
        </Badge>
      ),
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
