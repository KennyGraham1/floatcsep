'use client';

interface ColorbarLegendProps {
  vmin: number;
  vmax: number;
  title?: string;
}

const MAGMA_COLORS = [
  '#000004', '#030312', '#0d0829', '#1d0e45', '#300a5d',
  '#440f76', '#56147d', '#681d81', '#7c2981', '#8f3880',
  '#a2487e', '#b45b7a', '#c56f73', '#d4846c', '#e29b67',
  '#eeb365', '#f7cc66', '#fce570', '#fcffa4',
];

export default function ColorbarLegend({ vmin, vmax, title = 'log10(Rate)' }: ColorbarLegendProps) {
  return (
    <div className="bg-surface p-4 rounded-lg border border-border">
      <h3 className="text-sm font-semibold mb-3">{title}</h3>
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 w-12 text-right">{vmin.toFixed(2)}</span>
        <div className="flex-1 h-6 rounded" style={{
          background: `linear-gradient(to right, ${MAGMA_COLORS.join(', ')})`,
        }} />
        <span className="text-xs text-gray-400 w-12">{vmax.toFixed(2)}</span>
      </div>
    </div>
  );
}
