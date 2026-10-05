import { area, line, scaleLinear, scaleTime } from 'd3';
import { useId, useState } from 'react';
import { date, number } from '../../lib/format';
import type { Point, Sale } from '../../types/api';

interface Datum {
  day: Date;
  observed?: number;
  central?: number;
  lower?: number;
  upper?: number;
}
export function DemandChart({
  sales,
  points,
  cutoff,
}: {
  sales: Sale[];
  points: Point[];
  cutoff: string;
}) {
  const id = useId();
  const [selected, setSelected] = useState<Datum | null>(null);
  const data: Datum[] = [
    ...sales.map((s) => ({ day: new Date(s.day), observed: s.units })),
    ...points.map((p) => ({
      day: new Date(p.day),
      central: Number(p.yhat),
      lower: p.lower == null ? undefined : Number(p.lower),
      upper: p.upper == null ? undefined : Number(p.upper),
    })),
  ];
  if (!data.length) return <p className="empty">No demand series available.</p>;
  const width = 900,
    height = 290,
    left = 52,
    right = 22,
    top = 20,
    bottom = 42;
  const x = scaleTime()
    .domain([data[0].day, data[data.length - 1].day])
    .range([left, width - right]);
  const y = scaleLinear()
    .domain([0, Math.max(1, ...data.map((d) => d.upper ?? d.central ?? d.observed ?? 0)) * 1.12])
    .nice()
    .range([height - bottom, top]);
  const historical = line<Datum>()
    .defined((d) => d.observed !== undefined)
    .x((d) => x(d.day))
    .y((d) => y(d.observed ?? 0));
  const central = line<Datum>()
    .defined((d) => d.central !== undefined)
    .x((d) => x(d.day))
    .y((d) => y(d.central ?? 0));
  const band = area<Datum>()
    .defined((d) => d.lower !== undefined && d.upper !== undefined)
    .x((d) => x(d.day))
    .y0((d) => y(d.lower ?? 0))
    .y1((d) => y(d.upper ?? 0));
  return (
    <figure className="chart">
      <div className="chart-legend">
        <span className="observed">Observed sales</span>
        <span className="predicted">Forecast</span>
        <span className="band">90% empirical interval</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={id}>
        <title id={id}>
          Demand through {date(cutoff)} and {points.length} forecast points. Recorded sales are a
          demand proxy.
        </title>
        {y.ticks(5).map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} stroke="#e3e9ed" />
            <text x={left - 12} y={y(tick) + 4} textAnchor="end">
              {number(tick)}
            </text>
          </g>
        ))}
        {x.ticks(6).map((tick) => (
          <text key={tick.toISOString()} x={x(tick)} y={height - 12} textAnchor="middle">
            {tick.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })}
          </text>
        ))}
        <path d={band(data) ?? ''} fill="#d6e9ec" />
        <path d={historical(data) ?? ''} fill="none" stroke="#7d929b" strokeWidth="2" />
        <path d={central(data) ?? ''} fill="none" stroke="#176675" strokeWidth="3" />
        <line
          x1={x(new Date(cutoff))}
          x2={x(new Date(cutoff))}
          y1={top}
          y2={height - bottom}
          stroke="#ae7b20"
          strokeDasharray="5 5"
        />
        <text x={x(new Date(cutoff)) - 8} y={top + 12} textAnchor="end">
          Forecast cutoff
        </text>
        {data.map((datum, index) => (
          <circle
            role="img"
            key={index}
            cx={x(datum.day)}
            cy={y(datum.central ?? datum.observed ?? 0)}
            r="7"
            fill="transparent"
            tabIndex={0}
            aria-label={`${date(datum.day.toISOString())}: ${number(datum.central ?? datum.observed, 1)} units`}
            onFocus={() => setSelected(datum)}
            onMouseEnter={() => setSelected(datum)}
            onBlur={() => setSelected(null)}
            onMouseLeave={() => setSelected(null)}
          />
        ))}
      </svg>
      <figcaption aria-live="polite">
        {selected
          ? `${date(selected.day.toISOString())} · ${number(selected.central ?? selected.observed, 1)} units${selected.lower !== undefined ? ` · interval ${number(selected.lower, 1)}–${number(selected.upper, 1)}` : ''}`
          : 'Focus or hover over a point to inspect units. Shading shows an empirical interval, not a service guarantee.'}
      </figcaption>
    </figure>
  );
}
