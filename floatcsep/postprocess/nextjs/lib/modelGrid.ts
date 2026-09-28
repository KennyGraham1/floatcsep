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

/** "N50L11" -> "N50" and "FULL01" -> "0.1°", matching the global experiment's figures. */
export function shortGridName(grid: string): string {
  return grid === 'FULL01' ? '0.1°' : grid.replace(/L11$/, '');
}

/** A grid's name for menus: "FULL01 (0.1° native)", other names as they are. */
export function gridLabel(grid: string): string {
  return grid === 'FULL01' ? 'FULL01 (0.1° native)' : grid;
}
