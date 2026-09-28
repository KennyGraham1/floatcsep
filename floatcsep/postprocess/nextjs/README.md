# floatCSEP dashboard (Next.js)

An interactive web dashboard for floatCSEP experiments, launched with
`floatcsep view <config> --ui nextjs`. Built with Next.js 15, React 19,
Tailwind CSS, Apache ECharts and Leaflet.

## Pages

| Page | What it shows |
| --- | --- |
| **Overview** | Key figures, experiment configuration, map of the testing region (or of the forecasts' own grids, such as quadtree grids, with a grid selector), time-window timeline, models and tests. |
| **Catalog** | Filterable event map (before start / experiment period, minimum magnitude), magnitude over time with the forecast windows, magnitude–frequency distribution with an Aki–Utsu b-value, events per time window, largest events. |
| **Forecasts** | Per model and time window: map of expected events per cell or per 10⁴ km² (rate density, for cells of different sizes) with the observed events on top, colour-scale histogram and range, expected vs observed events per magnitude bin, headline numbers (Σλ, observed, peak). Regular and quadtree grids. |
| **Results** | *Charts*: heatmaps of the test scores (models × time windows, and models × grids for multi-grid experiments) and the per-model test intervals, read from the saved evaluation results. *Figures*: every evaluation figure by test and time window, per-model figures, the experiment's own figures (`results/figures/`), a full-screen viewer with download, test configuration and a coverage grid. |

Every chart has a table view, selections live in the URL (views can be
bookmarked), and the interface follows the light/dark system theme with a
manual override. Dates are UTC throughout.

### Multi-grid experiments

When every model is named `<MODEL>=<GRID>` (for example `GEAR1=N50L11`) and
there are at least two grids, the dashboard treats the experiment as the same
models on several grids: the Forecasts page selects a model and a grid, and the
Results page adds heatmaps of models × grids. Tutorial K is such an experiment.

### Experiment figures

Images in the results folder's `figures/` directory (PNG, JPEG, SVG or WebP),
for example written by a `plot_custom` script, are shown under *Experiment
figures* in the Results page.

## Running

```bash
floatcsep view config.yml --ui nextjs
```

`floatcsep view` then:

1. builds the experiment manifest and writes it to `.cache/manifest.json`;
2. finds Node.js ≥ 18.18 on `PATH`, or downloads a private Node.js LTS runtime
   into `.cache/node-runtime`;
3. runs `npm install` when `package.json` / `package-lock.json` changed since the
   last install (tracked by `node_modules/.floatcsep-install-stamp`);
4. builds the dashboard into `.next-prod/` when its sources changed (the first
   launch takes a few minutes), falling back to the development server if the
   build fails;
5. starts the server on `localhost` only and opens the browser.

`run_nextjs_app(experiment, mode=...)` accepts `"auto"` (default, as above),
`"start"` (production) or `"dev"` (hot reload).

## Development

```bash
cd floatcsep/postprocess/nextjs
npm install

# A manifest to work with: run `floatcsep view <config> --ui nextjs` once,
# which writes .cache/manifest.json, then:
export MANIFEST_PATH="$PWD/.cache/manifest.json"
export FLOATCSEP_PYTHON="$(which python)"   # the environment with floatCSEP

npm run dev          # http://localhost:3000, hot reload
npm run lint         # ESLint
npm run typecheck    # TypeScript
npm run build        # production build
```

### Environment variables

| Variable | Purpose |
| --- | --- |
| `MANIFEST_PATH` | Manifest written by `floatcsep view` (required). |
| `APP_ROOT` | Results directory; defaults to `app_root` in the manifest. |
| `FLOATCSEP_PYTHON` | Python interpreter used to parse catalogs and forecasts (`floatcsep view` passes its own). Defaults to `python3`. |
| `FLOATCSEP_DASHBOARD_CACHE` | Where parsed catalogs/forecasts are cached. Defaults to `.cache/data`. |
| `FLOATCSEP_VERSION`, `PYCSEP_VERSION` | Versions shown in the sidebar. |
| `NEXT_DIST_DIR` | Build directory (`floatcsep view` uses `.next-prod`). |

## Architecture

```
floatcsep view config.yml --ui nextjs
  └─ server.py: manifest (.cache/manifest.json) → npm install/build → next start
       Browser ──► /api/manifest            normalized manifest (existing files only)
               ──► /api/catalog             catalog as columns   ┐ manifest_api.py via the
               ──► /api/forecasts?model&window  cell rates        ┘ floatCSEP interpreter
               ──► /api/evaluations         summaries of the saved evaluation results
               ──► /api/results/<path>      result figure (listed in the manifest only)
```

- **Data loading.** `manifest_api.py` parses catalogs and forecasts with
  floatCSEP's own parsers (gridded `.dat/.csv/.xml/.hdf5`, quadtree `.csv` and
  catalog-based forecasts, whose expected rates are computed on the experiment
  grid), and scales rates to the time window like floatCSEP does. It writes
  compact, column-oriented JSON; times are epoch milliseconds (UTC). Regular
  grids are sent as cell indices, quadtree grids as quadkeys.
- **Evaluations.** `/api/evaluations` condenses every saved result
  (`<window>/evaluations/<test>_<model>.json`, including results written by a
  `plot_custom` script) into scores, intervals and pass/fail verdicts. Results
  of simulation-based tests can hold 10,000 values each, so the summaries are
  cached on disk; `NaN` and `Infinity` written by Python are tolerated.
- **Caching.** Results are cached in `FLOATCSEP_DASHBOARD_CACHE`, keyed on the
  source file's path, size and modification time, so re-running an experiment
  invalidates them. Responses carry an `ETag`; the browser caches with SWR.
- **Safety.** The API never takes file paths from the browser: catalogs and
  forecasts are looked up by index in the manifest, and only figures listed in
  the manifest are served. Python runs through `execFile` (no shell), and the
  server binds to `localhost`.
- **Maps.** Leaflet with keyless basemaps (Esri light/dark gray canvas,
  OpenStreetMap, Esri imagery). Forecast and region grids, regular or quadtree,
  are painted tile by tile on canvas (`components/maps/CellLayer.tsx`), so large
  grids stay fast.
- **Charts.** Apache ECharts, registered module by module in `lib/echarts.ts`.

### Layout

```
app/                      pages (experiment, catalogs, forecasts, results) and API routes
components/charts/        ECharts wrapper, chart theme and chart components
components/maps/          Leaflet map, grid cell and event layers, legends
components/overview/      Overview tables and the grid map card
components/results/       evaluation charts and figure browser
components/layout/        app shell, sidebar, page header
components/ui/            cards, tables, controls, states, lightbox
hooks/ lib/               data hooks, formatting, time (UTC), colours, grid helpers
lib/server/               manifest normalization, evaluation summaries, Python runner, HTTP helpers
manifest_api.py           catalog/forecast parsing (called by the API)
server.py runtime.py      launcher and Node.js/npm management
schemas.py                manifest serialization (Pydantic)
```

### Design system

Colours are tokens in `app/globals.css` (Tailwind names such as `bg-surface`,
`text-ink-2`, `text-accent`), mirrored in `lib/colors.ts` for canvas and
ECharts. Light and dark values are chosen separately and meet WCAG AA contrast.
Data colours come from a colour-blind-validated categorical palette; forecast
rates use a lightness-monotonic heat ramp (yellow→red in light mode,
purple→yellow in dark mode). The accent is the floatCSEP crimson.

## Troubleshooting

- **"The experiment could not be loaded"** — the dashboard was started without
  `MANIFEST_PATH`; launch it through `floatcsep view <config> --ui nextjs`.
- **"Python interpreter not found"** — set `FLOATCSEP_PYTHON` to the Python that
  has floatCSEP installed.
- **A catalog or forecast is slow the first time** — it is parsed by floatCSEP
  and cached; catalog-based forecasts compute expected rates from all simulated
  catalogs.
- **Build problems after updating** — delete `.next-prod/` (and `node_modules/`)
  and launch again.
