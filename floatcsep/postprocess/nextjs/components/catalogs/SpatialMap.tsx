'use client';

import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { CatalogEvent } from '@/lib/types';

interface SpatialMapProps {
  events: CatalogEvent[];
  bbox?: [number, number, number, number] | null;
  startDate?: string;
}

export default function SpatialMap({ events, bbox, startDate }: SpatialMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<L.CircleMarker[]>([]);
  const [mapReady, setMapReady] = useState(false);

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
      });

      L.tileLayer(
        'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        {
          attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>',
          maxZoom: 20,
        }
      ).addTo(map);

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
  }, []);

  // Update markers when data changes
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    const map = mapRef.current;

    // Clear existing markers
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    if (events.length === 0) {
      return;
    }

    // Calculate magnitude range for sizing
    const mags = events.map((e) => e.magnitude);
    const minMag = Math.min(...mags);
    const maxMag = Math.max(...mags);

    // Colors
    const INPUT_COLOR = '#38bdf8';
    const TEST_COLOR = '#ef4444';

    // Categorize events
    const categorizedEvents = events.map((event) => {
      const eventDate = new Date(event.time);
      const isInput = startDate ? eventDate < new Date(startDate) : false;
      return { ...event, category: isInput ? 'input' : 'test' };
    });

    // Sort so test events are drawn on top
    const sortedEvents = categorizedEvents.sort((a, b) =>
      a.category === 'input' && b.category === 'test' ? -1 : 1
    );

    // Add markers
    sortedEvents.forEach((event) => {
      // Calculate marker size based on magnitude
      const normalized = maxMag > minMag ? (event.magnitude - minMag) / (maxMag - minMag) : 0.5;
      const size = 3 + Math.pow(normalized, 2.5) * 15;

      const color = event.category === 'input' ? INPUT_COLOR : TEST_COLOR;
      const fillOpacity = event.category === 'input' ? 0.35 : 0.6;

      const marker = L.circleMarker([event.lat, event.lon], {
        radius: size,
        fillColor: color,
        fillOpacity: fillOpacity,
        color: '#020617',
        weight: 0.4,
        opacity: 0.5,
      });

      marker.bindPopup(`
        <div style="color: #020617;">
          <strong>${event.event_id}</strong><br/>
          Time: ${new Date(event.time).toLocaleString()}<br/>
          Magnitude: ${event.magnitude.toFixed(2)}<br/>
          Location: ${event.lat.toFixed(2)}, ${event.lon.toFixed(2)}
        </div>
      `);

      marker.addTo(map);
      markersRef.current.push(marker);
    });

    // Fit bounds
    if (bbox) {
      const [west, south, east, north] = bbox;
      map.fitBounds(
        [
          [south, west],
          [north, east],
        ],
        { padding: [50, 50] }
      );
    } else {
      const lats = events.map((e) => e.lat);
      const lons = events.map((e) => e.lon);
      const bounds: L.LatLngBoundsExpression = [
        [Math.min(...lats), Math.min(...lons)],
        [Math.max(...lats), Math.max(...lons)],
      ];
      map.fitBounds(bounds, { padding: [50, 50] });
    }

    return () => {
      // Don't remove map on cleanup, just markers
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
    };
  }, [events, bbox, startDate, mapReady]);

  return (
    <div className="space-y-3">
      <div ref={containerRef} className="w-full h-[450px] rounded-lg border border-border" />
      <div className="text-xs text-gray-400 space-y-1">
        <p className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full bg-[#38bdf8] opacity-60"></span>
          <span>Input Catalog (t &lt; start)</span>
          <span className="ml-4 inline-block w-3 h-3 rounded-full bg-[#ef4444] opacity-80"></span>
          <span>Test Catalog (start ≤ t)</span>
        </p>
        <p><span className="font-semibold">Note:</span> Marker size represents magnitude</p>
      </div>
    </div>
  );
}
