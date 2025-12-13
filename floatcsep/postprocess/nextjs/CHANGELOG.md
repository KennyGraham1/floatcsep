# Changelog

All notable changes to the floatCSEP Next.js Dashboard.

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
- Leaflet region map with bounding box overlay
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
- Interactive forecast map with Leaflet
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
- **Maps**: Leaflet 1.9 with dark Stadia basemaps
- **Charts**: Highcharts 11.2
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
