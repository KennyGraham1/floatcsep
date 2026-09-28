'use client';

import L from 'leaflet';
import { useEffect, type ReactNode } from 'react';
import { AttributionControl, MapContainer, Pane, TileLayer, useMap } from 'react-leaflet';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { usePersistentState } from '@/hooks/usePersistentState';
import { useThemeMode } from '@/hooks/useThemeMode';
import { cn } from '@/lib/utils';

const ESRI_CANVAS =
  '<a href="https://www.esri.com">Esri</a>, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS user community';
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services';

interface Basemap {
  url: string;
  attribution: string;
  maxNativeZoom: number;
  /** Place names and boundaries, drawn above the data layers. */
  labels?: string;
}

// Keyless providers only: the dashboard must work without any account.
const BASEMAPS: Record<'light' | 'dark' | 'streets' | 'satellite', Basemap> = {
  light: {
    url: `${ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ESRI}/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    attribution: ESRI_CANVAS,
    maxNativeZoom: 16,
  },
  dark: {
    url: `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ESRI}/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    attribution: ESRI_CANVAS,
    maxNativeZoom: 16,
  },
  streets: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxNativeZoom: 19,
  },
  satellite: {
    url: `${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`,
    attribution: '<a href="https://www.esri.com">Esri</a>, Vantor, Earthstar Geographics, and the GIS user community',
    maxNativeZoom: 18,
  },
};

type BasemapChoice = 'default' | 'streets' | 'satellite';
const CHOICES: readonly BasemapChoice[] = ['default', 'streets', 'satellite'];

const WORLD = L.latLngBounds([-60, -180], [75, 180]);

function FitBounds({ bounds, fitKey }: { bounds: L.LatLngBounds | null; fitKey: string }) {
  const map = useMap();
  useEffect(() => {
    if (bounds?.isValid()) map.fitBounds(bounds, { padding: [24, 24], animate: false, maxZoom: 11 });
    // Refit only when the data extent changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey]);
  return null;
}

/** Leaflet does not notice container resizes (sidebar, window) by itself. */
function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

/** Wheel zoom only after the map is clicked, so scrolling the page never gets captured. */
function ScrollZoomOnFocus() {
  const map = useMap();
  useEffect(() => {
    const enable = () => map.scrollWheelZoom.enable();
    const disable = () => map.scrollWheelZoom.disable();
    map.on('click focus', enable);
    map.on('mouseout blur', disable);
    return () => {
      map.off('click focus', enable);
      map.off('mouseout blur', disable);
    };
  }, [map]);
  return null;
}

interface MapViewProps {
  bounds: L.LatLngBounds | null;
  /** Changes when the map should zoom to `bounds` again. */
  fitKey: string;
  /** Pixel height; without it the map grows to fill a flex-column parent. */
  height?: number;
  ariaLabel: string;
  children?: ReactNode;
  /** HTML overlays (legends, readouts) positioned over the map. */
  overlays?: ReactNode;
  /** Draw place-name labels above the data (for rasters that cover the land). */
  labelsOnTop?: boolean;
  className?: string;
}

export default function MapView({
  bounds,
  fitKey,
  height,
  ariaLabel,
  children,
  overlays,
  labelsOnTop = false,
  className,
}: MapViewProps) {
  const mode = useThemeMode();
  const [choice, setChoice] = usePersistentState<BasemapChoice>('floatcsep:basemap', 'default', CHOICES);
  const tiles = BASEMAPS[choice === 'default' ? mode : choice];

  return (
    <div
      role="region"
      aria-label={ariaLabel}
      className={cn('relative isolate overflow-hidden rounded-lg border', height === undefined && 'min-h-0 flex-1', className)}
      style={height === undefined ? undefined : { height }}
    >
      <MapContainer
        bounds={bounds?.isValid() ? bounds : WORLD}
        boundsOptions={{ padding: [24, 24], maxZoom: 11 }}
        // Whole zoom levels: fractional zoom scales tiles and leaves hairline gaps.
        zoomSnap={1}
        scrollWheelZoom={false}
        preferCanvas
        attributionControl={false}
        className="absolute inset-0"
      >
        <AttributionControl position="bottomright" prefix='<a href="https://leafletjs.com">Leaflet</a>' />
        <TileLayer
          key={choice === 'default' ? mode : choice}
          url={tiles.url}
          attribution={tiles.attribution}
          maxNativeZoom={tiles.maxNativeZoom}
          maxZoom={19}
        />
        {labelsOnTop && tiles.labels && (
          <Pane name="labels" style={{ zIndex: 450, pointerEvents: 'none' }}>
            <TileLayer key={tiles.labels} url={tiles.labels} maxNativeZoom={tiles.maxNativeZoom} maxZoom={19} />
          </Pane>
        )}
        <FitBounds bounds={bounds} fitKey={fitKey} />
        <AutoResize />
        <ScrollZoomOnFocus />
        {children}
      </MapContainer>
      <div className="absolute right-3 top-3 z-[900]">
        <SegmentedControl<BasemapChoice>
          label="Basemap"
          value={choice}
          onChange={setChoice}
          className="bg-surface/95 shadow-card backdrop-blur"
          options={[
            { value: 'default', label: 'Map' },
            { value: 'streets', label: 'Streets' },
            { value: 'satellite', label: 'Satellite' },
          ]}
        />
      </div>
      {overlays}
    </div>
  );
}
