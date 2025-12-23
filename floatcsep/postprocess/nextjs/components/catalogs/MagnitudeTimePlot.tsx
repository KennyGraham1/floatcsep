'use client';

import { useRef } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import { CatalogEvent } from '@/lib/types';

interface MagnitudeTimePlotProps {
  events: CatalogEvent[];
  timeWindows: string[];
  startDate?: string;
}

export default function MagnitudeTimePlot({
  events,
  timeWindows,
  startDate,
}: MagnitudeTimePlotProps) {
  const chartRef = useRef<HighchartsReact.RefObject>(null);

  // Categorize events
  const inputEvents = events.filter((e) =>
    startDate ? new Date(e.time) < new Date(startDate) : false
  );
  const testEvents = events.filter((e) =>
    startDate ? new Date(e.time) >= new Date(startDate) : true
  );

  // Parse time windows for plot bands
  const plotBands = timeWindows.map((tw) => {
    const parts = tw.split(' to ');
    return {
      from: new Date(parts[0]?.trim() || '').getTime(),
      to: new Date(parts[1]?.trim() || parts[0]?.trim() || '').getTime(),
      color: 'rgba(56, 189, 248, 0.1)',
    };
  });

  const options = {
    chart: {
      type: 'scatter',
      backgroundColor: '#0b1120',
      zoomType: 'x',
      height: 350,
    },
    title: {
      text: '',
    },
    xAxis: {
      type: 'datetime',
      title: {
        text: 'Time',
        style: { color: '#e5e7eb' },
      },
      labels: {
        style: { color: '#e5e7eb', fontSize: '10px' },
        format: '{value:%Y-%m-%d}',
      },
      gridLineColor: '#1f2933',
      lineColor: '#6b7280',
      tickColor: '#6b7280',
      plotBands: plotBands,
    },
    yAxis: {
      title: {
        text: 'Magnitude',
        style: { color: '#e5e7eb' },
      },
      labels: {
        style: { color: '#e5e7eb' },
      },
      gridLineColor: '#1f2933',
    },
    legend: {
      itemStyle: { color: '#e5e7eb' },
    },
    plotOptions: {
      scatter: {
        marker: {
          radius: 4,
          states: {
            hover: {
              enabled: true,
              lineColor: '#e5e7eb',
            },
          },
        },
        states: {
          hover: {
            marker: {
              enabled: false,
            },
          },
        },
      },
    },
    series: [
      {
        name: 'Input Catalog',
        type: 'scatter',
        data: inputEvents.map((e) => ({
          x: new Date(e.time).getTime(),
          y: e.magnitude,
          name: e.event_id,
        })),
        color: '#38bdf8',
        marker: {
          fillOpacity: 0.6,
        },
      },
      {
        name: 'Test Catalog',
        type: 'scatter',
        data: testEvents.map((e) => ({
          x: new Date(e.time).getTime(),
          y: e.magnitude,
          name: e.event_id,
        })),
        color: '#ef4444',
        marker: {
          fillOpacity: 0.8,
        },
      },
    ],
    tooltip: {
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      style: { color: '#e5e7eb' },
      formatter: function (this: any) {
        const point = this.point;
        return `<b>${point.name}</b><br/>
                Time: ${Highcharts.dateFormat('%Y-%m-%d %H:%M:%S', this.x)}<br/>
                Magnitude: ${this.y?.toFixed(2)}`;
      },
    },
    credits: {
      enabled: false,
    },
  };

  return (
    <div className="w-full">
      <HighchartsReact highcharts={Highcharts} options={options} ref={chartRef} immutable={true} />
    </div>
  );
}
