'use client';

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface RegionMapProps {
  bbox?: [number, number, number, number]; // [west, south, east, north]
  regionName?: string | null;
}

export default function RegionMap({ bbox, regionName }: RegionMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Small delay to ensure DOM is ready
    const timer = setTimeout(() => {
      if (!containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: [0, 0],
        zoom: 2,
        zoomControl: true,
      });

      // Add dark basemap
      L.tileLayer(
        'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        {
          attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>',
          maxZoom: 20,
        }
      ).addTo(map);

      // Fit to bbox if provided
      if (bbox) {
        const [west, south, east, north] = bbox;
        map.fitBounds(
          [
            [south, west],
            [north, east],
          ],
          { padding: [50, 50] }
        );

        // Draw rectangle for region
        L.rectangle(
          [
            [south, west],
            [north, east],
          ],
          {
            color: '#14b8a6',
            weight: 2,
            fillOpacity: 0.1,
          }
        ).addTo(map);
      }

      mapRef.current = map;
    }, 100);

    return () => {
      clearTimeout(timer);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [bbox]);

  return (
    <div className="space-y-2">
      <div ref={containerRef} className="w-full h-[400px] rounded-lg border border-border" />
      {regionName && (
        <p className="text-xs text-gray-400">
          <span className="font-semibold">Region:</span> {regionName}
        </p>
      )}
      {bbox && (
        <p className="text-xs text-gray-400">
          <span className="font-semibold">Bounds:</span> [{bbox[0].toFixed(2)}, {bbox[1].toFixed(2)}] to [{bbox[2].toFixed(2)}, {bbox[3].toFixed(2)}]
        </p>
      )}
    </div>
  );
}
