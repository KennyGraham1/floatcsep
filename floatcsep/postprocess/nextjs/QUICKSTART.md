# Quick start: floatCSEP dashboard

1. Run an experiment (or use one that has already run):

   ```bash
   floatcsep run config.yml
   ```

2. Open the dashboard:

   ```bash
   floatcsep view config.yml --ui nextjs
   ```

   The first launch installs the dashboard's dependencies and builds it
   (a few minutes; Node.js is downloaded automatically if needed). Later
   launches start in seconds. The browser opens by itself.

3. Explore:

   - **Overview** — configuration, testing region, time windows, models, tests.
   - **Catalog** — filter events by period and magnitude; map, magnitude over
     time, magnitude–frequency distribution, events per window.
   - **Forecasts** — pick a model and time window; compare expected and observed
     events on the map and per magnitude bin; adjust the colour scale.
   - **Results** — evaluation figures by test and time window; click a figure
     to enlarge or download it.

   Use the chart/table toggle on any chart to read exact values, and the theme
   switch in the sidebar for light or dark mode. Stop the server with `Ctrl+C`.

If something goes wrong, see *Troubleshooting* in [README.md](README.md). The
Panel dashboard remains available with `floatcsep view config.yml --ui panel`.
