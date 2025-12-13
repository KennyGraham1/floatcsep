import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function lonLatToMercator(lon: number, lat: number): [number, number] {
  const k = 6378137.0; // Earth radius in meters
  const x = k * (lon * Math.PI / 180);
  const y = k * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI / 180) / 2));
  return [x, y];
}
