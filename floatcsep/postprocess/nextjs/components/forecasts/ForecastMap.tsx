'use client';

import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface ForecastCell {
  lon: number;
  lat: number;
  rate: number;
}

interface ForecastMapProps {
  cells: ForecastCell[];
  bbox?: [number, number, number, number];
  vmin: number;
  vmax: number;
  colorbarMin?: number;
  colorbarMax?: number;
}

// Magma color palette (20 steps)
const MAGMA_COLORS = [
  '#000004', '#030312', '#0d0829', '#1d0e45', '#300a5d',
  '#440f76', '#56147d', '#681d81', '#7c2981', '#8f3880',
  '#a2487e', '#b45b7a', '#c56f73', '#d4846c', '#e29b67',
  '#eeb365', '#f7cc66', '#fce570', '#fcffa4',
];

// Get color from Magma palette based on normalized value [0, 1]
function getMagmaColor(value: number, alpha: number = 0.7): string {
  const clamped = Math.max(0, Math.min(1, value));
  const index = Math.floor(clamped * (MAGMA_COLORS.length - 1));
  const hex = MAGMA_COLORS[index];

  // Convert hex to rgba
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);

  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function ForecastMap({
  cells,
  bbox,
  vmin,
  vmax,
  colorbarMin,
  colorbarMax,
}: ForecastMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const cellLayersRef = useRef<L.Rectangle[]>([]);
  const [mapReady, setMapReady] = useState(false);

  const effectiveMin = colorbarMin !== undefined ? colorbarMin : vmin;
  const effectiveMax = colorbarMax !== undefined ? colorbarMax : vmax;

  // Initialize map only once on mount
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Small delay to ensure DOM is ready
    const timer = setTimeout(() => {
      if (!containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: [0, 0],
        zoom: 2,
        zoomControl: true,
        attributionControl: false,
      });

      // Add dark basemap
      L.tileLayer(
        'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        {
          maxZoom: 20,
          attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>',
        }
      ).addTo(map);

      // Fit to bbox if provided
      if (bbox) {
        const [west, south, east, north] = bbox;
        map.fitBounds([[south, west], [north, east]], { padding: [30, 30] });
      }

      mapRef.current = map;
      setMapReady(true);
    }, 100);

    return () => {
      clearTimeout(timer);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        setMapReady(false);
      }
    };
  }, [bbox]);

  // Update cells when data changes
  useEffect(() => {
    if (!mapReady || !mapRef.current || cells.length === 0) return;

    // Clear existing cell layers
    cellLayersRef.current.forEach((layer) => layer.remove());
    cellLayersRef.current = [];

    // Infer cell size from first two cells
    const sortedByLon = [...cells].sort((a, b) => a.lon - b.lon);
    const sortedByLat = [...cells].sort((a, b) => a.lat - b.lat);

    const cellWidth = sortedByLon.length > 1
      ? Math.abs(sortedByLon[1].lon - sortedByLon[0].lon)
      : 0.1;
    const cellHeight = sortedByLat.length > 1
      ? Math.abs(sortedByLat[1].lat - sortedByLat[0].lat)
      : 0.1;

    // Add cell rectangles
    cells.forEach((cell) => {
      const logRate = Math.log10(cell.rate);

      // Normalize to [0, 1] using colorbar range
      const normalized = (logRate - effectiveMin) / (effectiveMax - effectiveMin);
      const color = getMagmaColor(normalized, 0.7);

      const bounds: L.LatLngBoundsExpression = [
        [cell.lat - cellHeight / 2, cell.lon - cellWidth / 2],
        [cell.lat + cellHeight / 2, cell.lon + cellWidth / 2],
      ];

      const rectangle = L.rectangle(bounds, {
        color: color,
        fillColor: color,
        fillOpacity: 0.7,
        weight: 0,
      });

      rectangle.bindPopup(`
        <div style="color: #e5e7eb; font-size: 12px;">
          <strong>Forecast Cell</strong><br/>
          Lon: ${cell.lon.toFixed(4)}<br/>
          Lat: ${cell.lat.toFixed(4)}<br/>
          Rate: ${cell.rate.toExponential(3)}<br/>
          log10(Rate): ${logRate.toFixed(3)}
        </div>
      `);

      rectangle.addTo(mapRef.current!);
      cellLayersRef.current.push(rectangle);
    });
  }, [cells, effectiveMin, effectiveMax, mapReady]);

  return (
    <div className="relative w-full">
      <div ref={containerRef} className="w-full h-[500px] rounded-lg border border-border" />
    </div>
  );
}
