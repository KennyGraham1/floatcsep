import type { Model } from '@/lib/types';

/**
 * Experiments that evaluate each model on several grids name the models
 * "<MODEL>=<GRID>" (as the global quadtree experiment does). The dashboard then
 * offers the grid as its own dimension.
 */
export interface ModelGrid {
  /** Model names without the grid, in manifest order. */
  models: string[];
  grids: string[];
  /** Index in manifest.models of a model on a grid, or -1. */
  indexOf: (model: string, grid: string) => number;
}

export function splitModelName(name: string): { model: string; grid: string | null } {
  const at = name.lastIndexOf('=');
  return at > 0 ? { model: name.slice(0, at), grid: name.slice(at + 1) } : { model: name, grid: null };
}

export function modelGrid(models: { name: string }[]): ModelGrid | null {
  const parts = models.map((m) => splitModelName(m.name));
  if (parts.length === 0 || parts.some((p) => p.grid === null)) return null;
  const names: string[] = [];
  const grids: string[] = [];
  const index = new Map<string, number>();
  parts.forEach(({ model, grid }, i) => {
    if (!names.includes(model)) names.push(model);
    if (!grids.includes(grid!)) grids.push(grid!);
    index.set(`${model}\u0000${grid}`, i);
  });
  if (grids.length < 2) return null;
  return { models: names, grids, indexOf: (model, grid) => index.get(`${model}\u0000${grid}`) ?? -1 };
}

/** Cell sizes, in degrees, of the regular grids declared for external forecasts, by grid name. */
export function regularGridSizes(models: Pick<Model, 'name' | 'external'>[]): Map<string, number> {
  const sizes = new Map<string, number>();
  for (const m of models) {
    const grid = splitModelName(m.name).grid;
    if (grid && m.external) sizes.set(grid, m.external.grid.dh);
  }
  return sizes;
}

/** A grid's name for menus: a declared regular grid with its cell size, "G (0.1° grid)". */
export function gridLabel(grid: string, sizes: Map<string, number>): string {
  const dh = sizes.get(grid);
  return dh === undefined ? grid : `${grid} (${dh}° grid)`;
}

/**
 * The longest suffix all names share that starts at a token boundary: a separator, or a
 * letter after a digit ("N50|L11"), so that no name loses part of a word or number.
 */
function sharedSuffix(names: string[]): string {
  if (names.length < 2) return '';
  let suffix = names[0];
  for (const name of names) while (!name.endsWith(suffix)) suffix = suffix.slice(1);
  for (; suffix; suffix = suffix.slice(1)) {
    const head = suffix[0];
    const atBoundary = names.every((name) => {
      const before = name[name.length - suffix.length - 1];
      if (before === undefined) return false;
      return /[\s_.\-]/.test(head) || (/[A-Za-z]/.test(head) && /\d/.test(before));
    });
    if (atBoundary) break;
  }
  return suffix;
}

/**
 * Short grid names for heatmap columns: a declared regular grid by its cell size ("0.1°"),
 * the others without a suffix they all share, such as the zoom level of quadtree grids
 * ("N50L11" -> "N50").
 */
export function shortGridNames(grids: string[], sizes: Map<string, number>): string[] {
  const suffix = sharedSuffix(grids.filter((g) => !sizes.has(g)));
  return grids.map((g) => {
    const dh = sizes.get(g);
    return dh === undefined ? g.slice(0, g.length - suffix.length) : `${dh}°`;
  });
}
