'use client';

import { BookOpen } from 'lucide-react';
import { Children, isValidElement, useMemo, useState, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PageHeader } from '@/components/layout/PageHeader';
import { FigureImage } from '@/components/results/FigureImage';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DefinitionList } from '@/components/ui/DefinitionList';
import { Lightbox, type LightboxItem } from '@/components/ui/Lightbox';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { useAbout } from '@/lib/api';
import { useLoadedManifest } from '@/lib/contexts/ManifestContext';
import type { Manifest } from '@/lib/types';
import { doiUrl } from '@/lib/utils';

/** The plain text of rendered Markdown (for heading anchors). */
function textOf(children: ReactNode): string {
  return Children.toArray(children)
    .map((child) =>
      typeof child === 'string' || typeof child === 'number'
        ? String(child)
        : isValidElement<{ children?: ReactNode }>(child)
          ? textOf(child.props.children)
          : '',
    )
    .join('');
}

function slug(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-');
}

const IMAGE = /!\[([^\]]*)\]\((\S+?)(?:\s+"([^"]*)")?\)/g;

/** Section headings (##) and figures of the document, outside code blocks. */
function outline(markdown: string) {
  const sections: { id: string; title: string }[] = [];
  const figures: LightboxItem[] = [];
  let fenced = false;
  for (const line of markdown.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    if (fenced) continue;
    const heading = /^##\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      const title = heading[1].replace(/[*_`]/g, '');
      sections.push({ id: slug(title), title });
    }
    for (const [, alt, src, title] of line.matchAll(IMAGE)) {
      if (!figures.some((f) => f.src === src)) {
        figures.push({ src, title: title || alt || 'Figure', downloadHref: `${src}?download=1` });
      }
    }
  }
  return { sections, figures };
}

function Metadata({ manifest }: { manifest: Manifest }) {
  const link = (doi: string | null) =>
    doi ? (
      <a href={doiUrl(doi)} target="_blank" rel="noopener noreferrer" className="link break-all">
        {doi}
      </a>
    ) : null;
  return (
    <DefinitionList
      layout="stacked"
      items={[
        { label: 'Testing period', value: `${manifest.start_date} → ${manifest.end_date}` },
        { label: 'Authors', value: manifest.authors },
        { label: 'Experiment DOI', value: link(manifest.doi) },
        { label: 'Journal', value: manifest.journal },
        { label: 'Manuscript DOI', value: link(manifest.manuscript_doi) },
        { label: 'Catalog DOI', value: link(manifest.catalog_doi) },
        { label: 'License', value: manifest.license },
        {
          label: 'Software',
          value: [
            manifest.floatcsep_version && `floatCSEP ${manifest.floatcsep_version}`,
            manifest.pycsep_version && `pyCSEP ${manifest.pycsep_version}`,
          ]
            .filter(Boolean)
            .join(' · '),
        },
      ]}
    />
  );
}

export default function AboutPage() {
  const manifest = useLoadedManifest();
  const { data, error, isLoading, mutate } = useAbout(manifest.about !== null);
  const [open, setOpen] = useState<number | null>(null);
  const { sections, figures } = useMemo(() => outline(data?.markdown ?? ''), [data]);

  const components = useMemo<Components>(() => {
    const figureIndex = new Map(figures.map((f, i) => [f.src, i]));
    return {
      h1: ({ children }) => <h2 className="text-xl font-semibold tracking-tight text-ink">{children}</h2>,
      h2: ({ children }) => (
        <h3
          id={slug(textOf(children))}
          className="mt-8 scroll-mt-6 border-t pt-6 text-base font-semibold tracking-tight text-ink"
        >
          {children}
        </h3>
      ),
      h3: ({ children }) => <h4 className="mt-6 text-sm font-semibold text-ink">{children}</h4>,
      p: ({ node, children }) => {
        // A paragraph holding only an image is a figure, which may not sit inside <p>.
        const only = node?.children.length === 1 ? node.children[0] : null;
        if (only?.type === 'element' && only.tagName === 'img') return <div className="my-6">{children}</div>;
        return <p className="mt-3 text-[0.9rem] leading-7 text-ink-2">{children}</p>;
      },
      a: ({ href, children }) => {
        const external = /^https?:\/\//i.test(href ?? '');
        return (
          <a href={href} className="link" {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
            {children}
          </a>
        );
      },
      ul: ({ children }) => (
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[0.9rem] leading-7 text-ink-2">{children}</ul>
      ),
      ol: ({ children }) => (
        <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[0.9rem] leading-7 text-ink-2">{children}</ol>
      ),
      blockquote: ({ children }) => (
        <blockquote className="mt-4 border-l-2 border-accent/60 pl-4 text-ink-2 [&>p]:mt-1">{children}</blockquote>
      ),
      code: ({ children }) => (
        <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.8em] text-ink">{children}</code>
      ),
      pre: ({ children }) => (
        <pre className="mt-4 overflow-x-auto rounded-lg border bg-surface-2 p-4 text-xs leading-5 [&_code]:bg-transparent [&_code]:p-0">
          {children}
        </pre>
      ),
      table: ({ children }) => (
        <div className="mt-4 overflow-x-auto rounded-lg border">
          <table className="w-full border-collapse text-sm">{children}</table>
        </div>
      ),
      thead: ({ children }) => <thead className="bg-surface-2">{children}</thead>,
      // GFM column alignment arrives as a text-align style.
      th: ({ children, style }) => (
        <th style={style} className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold text-ink-2">
          {children}
        </th>
      ),
      td: ({ children, style }) => (
        <td style={style} className="border-t px-3 py-2 align-top tabular text-ink-2">
          {children}
        </td>
      ),
      hr: () => <hr className="my-8" />,
      img: ({ src, alt, title }) => {
        const source = typeof src === 'string' ? src : '';
        const index = figureIndex.get(source);
        return (
          <figure className="mx-auto max-w-4xl [&_img]:max-h-[34rem] [&_img]:w-auto">
            <FigureImage src={source} alt={alt ?? ''} onOpen={index === undefined ? undefined : () => setOpen(index)} />
            {(title || alt) && <figcaption className="mt-2 text-xs leading-5 text-ink-3">{title || alt}</figcaption>}
          </figure>
        );
      },
    };
  }, [figures]);

  let body: ReactNode;
  if (manifest.about === null || error?.status === 404) {
    body = (
      <EmptyState
        icon={BookOpen}
        title="No description of this experiment yet"
        description={
          <>
            Write an <code className="font-mono">about.md</code> next to the experiment&apos;s configuration: it is
            shown here, with the images it links to.
          </>
        }
      />
    );
  } else if (error) {
    body = (
      <ErrorState
        title="The description could not be loaded"
        message={error.message}
        details={error.details}
        onRetry={() => mutate()}
      />
    );
  } else if (isLoading || !data) {
    body = <LoadingState title="Loading the description…" />;
  } else {
    body = (
      <article className="px-5 py-6 sm:px-8 sm:py-8">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {data.markdown}
        </ReactMarkdown>
      </article>
    );
  }

  return (
    <>
      <PageHeader title="About" description="What the experiment tests, how, and with which data." />
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <Card>{body}</Card>
        <aside className="space-y-5 xl:sticky xl:top-6">
          {sections.length > 1 && (
            <Card>
              <CardHeader title="On this page" />
              <CardBody>
                <nav aria-label="Sections">
                  <ul className="space-y-1.5 text-[0.8rem]">
                    {sections.map((section) => (
                      <li key={section.id}>
                        <a href={`#${section.id}`} className="text-ink-2 hover:text-ink">
                          {section.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </nav>
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader title="Experiment" description={manifest.name} />
            <CardBody>
              <Metadata manifest={manifest} />
            </CardBody>
          </Card>
        </aside>
      </div>
      <Lightbox items={figures} index={open} onIndexChange={setOpen} />
    </>
  );
}
