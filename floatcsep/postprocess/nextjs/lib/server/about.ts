import crypto from 'crypto';
import fs from 'fs/promises';
import path from 'path';
import { resolveFromRoot, type LoadedManifest } from './manifest';

/**
 * The experiment's about.md, for the About page. The images it references are
 * served by index from /api/about/assets/<n>: the browser never sends a path,
 * and only image files inside the document's own folder can be read.
 */
export interface AboutDocument {
  /** The Markdown, with local image links pointing to /api/about/assets/<n>. */
  markdown: string;
  /** Absolute paths of the referenced images, by index. */
  assets: string[];
  etag: string;
}

// ![alt](src "title"), with <src with spaces>, (balanced) parentheses in src, and
// "title", 'title' or (title)
const IMAGE = /!\[([^\]]*)\]\(\s*(<[^>\n]*>|(?:[^\s()]|\([^\s()]*\))+)(\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)/g;
// [label]: src "title", the definition of a reference-style image ![alt][label]
const DEFINITION = /^( {0,3}\[[^\]]+\]:[ \t]*)(<[^>\n]*>|\S+)(.*)$/;
const FENCE = /^ {0,3}(`{3,}|~{3,})/;
const CODE_SPAN = /(`+)[\s\S]*?\1/g;
const IMAGE_FILE = /\.(png|jpe?g|gif|webp|svg)$/i;
const REMOTE = /^([a-z][a-z0-9+.-]*:|\/\/)/i;

let cached: { key: string; value: AboutDocument } | null = null;

function decode(src: string): string {
  const bare = src.startsWith('<') ? src.slice(1, -1) : src;
  try {
    return decodeURIComponent(bare);
  } catch {
    return bare;
  }
}

/**
 * Replace the destination of every image of a Markdown text, inline or by a reference
 * definition that points to an image file (other definitions are links), except in code
 * (fenced blocks and inline spans), where `![…](…)` is not an image.
 */
function mapDestinations(text: string, replace: (src: string) => string | null): string {
  let fence: string | null = null;
  return text
    .split('\n')
    .map((line) => {
      const marker = FENCE.exec(line)?.[1];
      if (fence) {
        if (marker && marker[0] === fence[0] && marker.length >= fence.length) fence = null;
        return line;
      }
      if (marker) {
        fence = marker;
        return line;
      }
      const definition = DEFINITION.exec(line);
      if (definition && IMAGE_FILE.test(decode(definition[2]))) {
        const target = replace(definition[2]);
        return target === null ? line : `${definition[1]}${target}${definition[3]}`;
      }
      // Rewrite outside inline code spans only
      let out = '';
      let last = 0;
      const images = (part: string) =>
        part.replace(IMAGE, (match, alt: string, src: string, title = '') => {
          const target = replace(src);
          return target === null ? match : `![${alt}](${target}${title})`;
        });
      for (const span of line.matchAll(CODE_SPAN)) {
        out += images(line.slice(last, span.index)) + span[0];
        last = span.index + span[0].length;
      }
      return out + images(line.slice(last));
    })
    .join('\n');
}

export async function loadAbout(loaded: LoadedManifest): Promise<AboutDocument | null> {
  if (!loaded.manifest.about) return null;
  const file = resolveFromRoot(loaded.appRoot, loaded.manifest.about);
  let stat;
  try {
    stat = await fs.stat(file);
  } catch {
    return null;
  }
  const key = `${file}:${stat.mtimeMs}:${stat.size}`;
  if (cached?.key === key) return cached.value;

  const folder = await fs.realpath(path.dirname(file));
  const text = await fs.readFile(file, 'utf-8');

  // Remote images (also written as <url>) are left alone. Local ones must be image files
  // inside the document's folder, once symbolic links are resolved: first find them all,
  // then resolve them, then link each to its index.
  const local = new Set<string>();
  mapDestinations(text, (src) => {
    const link = decode(src);
    if (!REMOTE.test(link)) local.add(link);
    return null;
  });
  const real = new Map<string, string | null>();
  await Promise.all(
    [...local].map(async (link) => {
      const target = await fs.realpath(path.resolve(folder, link)).catch(() => null);
      const inside = target !== null && target.startsWith(folder + path.sep) && IMAGE_FILE.test(target);
      real.set(link, inside && IMAGE_FILE.test(link) ? target : null);
    }),
  );
  const assets: string[] = [];
  const indices = new Map<string, number>();
  const markdown = mapDestinations(text, (src) => {
    const link = decode(src);
    if (REMOTE.test(link)) return null;
    const target = real.get(link) ?? null;
    if (target !== null && !indices.has(target)) indices.set(target, assets.push(target) - 1);
    return `/api/about/assets/${target === null ? -1 : indices.get(target)}`;
  });

  const etag = `"${crypto.createHash('sha1').update(key).digest('hex')}"`;
  cached = { key, value: { markdown, assets, etag } };
  return cached.value;
}
