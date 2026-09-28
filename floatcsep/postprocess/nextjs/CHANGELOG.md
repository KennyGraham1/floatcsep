# Changelog

All notable changes to the floatCSEP Next.js Dashboard.

## [2.0.0] - 2026-09

### Changed
- Redesigned interface: sidebar navigation, stat tiles, cards and tables,
  light/dark/system themes, responsive layout down to phone widths, floatCSEP
  branding and Noto Sans (bundled, works offline).
- All charts use **Apache ECharts** (Highcharts removed). Every chart has a table
  view, tooltips escape catalog text, and dates are shown in UTC.
- Maps use keyless basemaps (Esri light/dark gray canvas, OpenStreetMap, Esri
  imagery); CARTO tiles now require an API key. Forecast and region grids are
  painted tile by tile on canvas, for regular and quadtree grids alike.
- Upgraded to Next.js 15.5 and React 19 (fixes the Next.js 14 security
  advisories); `npm audit` reports no vulnerabilities.
- `floatcsep view --ui nextjs` builds and serves a production build (rebuilt
  when the dashboard changes), binds to `localhost`, reinstalls dependencies
  when `package.json` changes, and passes its own Python interpreter to the API.
- API: `/api/catalog` and `/api/forecasts?model=&window=` resolve files from the
  manifest instead of accepting paths; results are served only if listed in the
  manifest, with ETags; caches are keyed on file path, size and mtime.

### Added
- Catalog: period and magnitude filters, magnitude–frequency distribution with
  b-value, events per time window, largest events.
- Forecasts: observed events overlay, expected vs observed counts, colour-scale
  histogram with range slider and opacity, neighbouring windows prefetched.
- Forecasts: quadtree forecasts, and a rate-density view (events per 10⁴ km²)
  for cells of different sizes.
- Forecasts: colour palettes for the map (Turbo by default; Viridis, Cividis,
  Plasma, Magma, Inferno, Heat), remembered between visits.
- Results: *Charts* view with heatmaps of the test scores (models × time
  windows, models × grids) and per-model intervals, from `/api/evaluations`.
- Results: coverage grid, per-model figures, full-screen viewer with download,
  and the experiment's own figures (`results/figures/`).
- Multi-grid experiments (models named `<MODEL>=<GRID>`): model and grid
  selectors, a map of each forecast grid on the Overview, and results of grids
  evaluated elsewhere (without forecasts in the experiment) in the heatmaps.
- About page: the experiment's `about.md` with its figures, and its citation
  details.
- Global maps are Pacific-centred.
- Overview: time-window timeline, models and tests tables.

### Fixed
- Catalog-based forecasts failed to load (wrong module import).
- Cached forecasts were keyed by model/window index and could show another
  experiment's data.
- Event times were parsed as local time, misclassifying events near the start.
- Colour-range changes were lost when panning the forecast map.
- Model registry internals and empty plot functions leaked into the manifest.
- Arbitrary paths could be read through the catalog/forecast/results routes.
- Forecasts of time-independent models were not scaled to the time window.
- The catalog path in the manifest assumed a copy inside the results folder,
  which exists only once a run has finished.
- Global grids and catalogs opened at zoom 0 (a small, repeated world), and
  events of a global grid could be drawn a world away from their location.
- The b-value assumed magnitudes binned at 0.1; the binning correction now
  follows the catalog's magnitude resolution (e.g. 0.01 for gCMT Mw).
- Magnitude bins such as 7.45 were rounded to one decimal.
- Evaluation results containing `NaN` or `Infinity` could not be read.

## [1.1.0] - 2025

### Changed
- **BREAKING**: Migrated all map visualizations from Leaflet to Highcharts
- Replaced Leaflet maps with Highcharts equivalents:
  - SpatialMap: Now uses Highcharts Maps with **OpenStreetMap tile basemap** for realistic geography
  - ForecastMap: Now uses Highcharts heatmap with Magma color palette
  - RegionMap: Now uses Highcharts line chart for boundary visualization
- Removed Leaflet dependencies (leaflet, @types/leaflet)
- Added proj4 for geographic coordinate support
- Unified all visualizations under a single charting library (Highcharts)
- Maintained all interactive features (tooltips, zoom, pan)
- Preserved dark theme styling across all new visualizations
- **Instant map rendering** - Maps now render immediately at the correct zoom and position (no delay or animation from world view)
- **Added automatic zoom to data extent** - Maps automatically calculate optimal zoom level based on data spread
- **Added antimeridian (180°) crossing support** - Special handling for NZ and Pacific data with intelligent centering
- **Smart map centering** - Regions crossing the antimeridian (like New Zealand) are properly centered instead of being pushed to edges
- **Using real basemap tiles** - OpenStreetMap provides actual detailed coastlines, roads, and geographic features

### Benefits
- Single charting library reduces bundle size and complexity
- Consistent API and interaction patterns across all visualizations
- Better TypeScript support and type safety
- Improved customization and theming capabilities

## [1.0.0] - 2024

### Added

#### Phase 1: Foundation
- Next.js 14 project with TypeScript, Tailwind CSS
- Python integration via `server.py` and `manifest_api.py`
- CLI integration with `--ui nextjs` flag in `floatcsep view`
- Manifest serialization from Python to JSON
- SWR-based data fetching with caching
- Dark theme with custom color palette
- Layout components (Header, Footer, Navigation)

#### Phase 2: Experiment Tab
- Interactive metadata accordion (Radix UI)
- Region map with bounding box overlay
- Highcharts time windows timeline (x-range chart)
- DOI badges and version display
- Model and test configuration panels

#### Phase 3: Catalogs Tab
- Spatial event map with magnitude-based marker sizing
- Color-coded events (input vs test catalogs)
- Magnitude-time scatter plot with time window overlays
- Interactive hover tooltips
- Catalog metadata panel

#### Phase 4: Forecasts Tab
- Forecast data API endpoint with in-memory caching
- Interactive forecast heatmap visualization
- Magma color palette for rate visualization (log10 scale)
- Adjustable color range controls (min/max)
- Model and time window selectors
- Statistics panel (cell count, rate range)
- Support for gridded and catalog-based forecasts

#### Phase 5: Results Tab
- Results image API endpoint with security checks
- Cascading selectors (time window → test → model)
- Dynamic PNG loading with error handling
- Test metadata panel (type, function, percentile)
- Model metadata panel (DOI, Zenodo)

#### Phase 6: Polish & Accessibility
- Error boundary component for graceful error handling
- Skip to main content link
- ARIA labels on navigation and interactive elements
- Focus management and keyboard navigation
- Screen reader support (sr-only utility classes)
- Viewport meta tag for mobile responsiveness

#### Phase 7: Documentation
- Updated README with complete feature list
- API endpoint documentation
- Component descriptions
- Troubleshooting guide
- CHANGELOG

### Technical Details

- **Frontend**: Next.js 14, React 18, TypeScript 5.3
- **Styling**: Tailwind CSS, custom dark theme
- **UI Components**: shadcn/ui (Radix UI), Accordion
- **Visualizations**: Highcharts 11.2 (scatter plots, heatmaps, line charts)
- **Data Fetching**: SWR 2.2
- **Backend**: Node.js 20, Python subprocess integration
- **Caching**: Multi-level (SWR + in-memory + HTTP headers)

### Architecture

```
Next.js Frontend (React + TypeScript)
    ↓
Next.js API Routes (Node.js)
    ↓
Python subprocess (manifest_api.py)
    ↓
floatCSEP Python library
```

### File Structure

- 50+ TypeScript/TSX files
- 4 main tabs (Experiment, Catalogs, Forecasts, Results)
- 10+ reusable components
- 4 API routes
- 2 Python integration modules

## Future Releases

### Planned Features
- Static site export
- Offline support
- Advanced catalog filtering
- Forecast comparison view
- Visualization export
- Custom color palettes
