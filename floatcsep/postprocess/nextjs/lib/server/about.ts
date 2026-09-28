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

// ![alt](src "title") and ![alt](<src with spaces> "title")
const IMAGE = /!\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)(\s+"[^"]*")?\s*\)/g;
const IMAGE_FILE = /\.(png|jpe?g|gif|webp|svg)$/i;

let cached: { key: string; value: AboutDocument } | null = null;

function decode(src: string): string {
  const bare = src.startsWith('<') ? src.slice(1, -1) : src;
  try {
    return decodeURIComponent(bare);
  } catch {
    return bare;
  }
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

  const folder = path.dirname(file);
  const assets: string[] = [];
  const text = await fs.readFile(file, 'utf-8');
  const markdown = text.replace(IMAGE, (match, alt: string, src: string, title = '') => {
    // Remote images are left alone; local ones must stay inside the document's folder.
    if (/^([a-z][a-z0-9+.-]*:|\/\/)/i.test(src)) return match;
    const target = path.resolve(folder, decode(src));
    const inside = target.startsWith(folder + path.sep) && IMAGE_FILE.test(target);
    const index = inside ? assets.push(target) - 1 : -1;
    return `![${alt}](/api/about/assets/${index}${title})`;
  });

  const etag = `"${crypto.createHash('sha1').update(key).digest('hex')}"`;
  cached = { key, value: { markdown, assets, etag } };
  return cached.value;
}
