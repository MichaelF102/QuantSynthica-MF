"use client";

import { useMemo } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import type { Point } from "@/lib/api";

// DESIGN.md §4.4 series palette (fixed order) and §8 chart rules.
export const SERIES = ["#2563EB", "#16A34A", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#64748B", "#EA580C"];
const UP = "#10b981";
const DOWN = "#f43f5e";
const AXIS = { fontSize: 10, fill: "#64748b" } as const;
const TOOLTIP = {
  backgroundColor: "var(--qs-panel)", borderColor: "var(--qs-line)", borderRadius: "6px", fontSize: "11px", color: "var(--qs-strong)",
} as const;

export type Series = { key: string; name: string; data: Point[]; color?: string; dashed?: boolean };

/** Merge several [date, value] series into rows keyed by date. Gaps stay gaps (no interpolation). */
function merge(series: Series[]) {
  const rows = new Map<string, Record<string, number | string>>();
  for (const s of series) for (const [d, v] of s.data) {
    const r = rows.get(d) ?? { date: d };
    r[s.key] = v;
    rows.set(d, r);
  }
  return [...rows.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

const fmtDate = (d: string) => {
  const [y, m] = d.split("-");
  return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m) - 1]} ${y.slice(2)}`;
};

export function Empty({ text }: { text: string }) {
  return <div className="flex h-full items-center justify-center text-xs text-faint">{text}</div>;
}

export function LineChartMulti({ series, height = 288, unit = "", digits = 1, zero = false, legend = true }: {
  series: Series[]; height?: number; unit?: string; digits?: number; zero?: boolean; legend?: boolean;
}) {
  const rows = useMemo(() => merge(series), [series]);
  if (!rows.length) return <div style={{ height }}><Empty text="No data for this period" /></div>;
  return (
    <div style={{ height }} role="img" aria-label={`Chart: ${series.map((s) => s.name).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} minTickGap={48} tickFormatter={fmtDate} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => `${v.toFixed(0)}${unit}`} domain={["auto", "auto"]} />
          {zero && <ReferenceLine y={0} stroke="var(--qs-line-strong)" />}
          <Tooltip contentStyle={TOOLTIP} labelFormatter={(d) => String(d)} formatter={(v) => `${Number(v).toFixed(digits)}${unit}`} />
          {legend && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color ?? SERIES[i % SERIES.length]} strokeWidth={2}
              strokeDasharray={s.dashed ? "4 3" : undefined} dot={false} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Drawdown (always <= 0): filled area per series. */
export function DrawdownChart({ series, height = 288 }: { series: Series[]; height?: number }) {
  const rows = useMemo(() => merge(series), [series]);
  if (!rows.length) return <div style={{ height }}><Empty text="No data for this period" /></div>;
  return (
    <div style={{ height }} role="img" aria-label="Drawdown chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {series.map((s, i) => (
              <linearGradient key={s.key} id={`dd-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color ?? SERIES[i % SERIES.length]} stopOpacity={0} />
                <stop offset="100%" stopColor={s.color ?? SERIES[i % SERIES.length]} stopOpacity={0.3} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} minTickGap={48} tickFormatter={fmtDate} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => `${v.toFixed(0)}%`} domain={["auto", 0]} />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${Number(v).toFixed(2)}%`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map((s, i) => (
            <Area key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color ?? SERIES[i % SERIES.length]} strokeWidth={2}
              fill={`url(#dd-${s.key})`} dot={false} connectNulls isAnimationActive={false} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Calendar-year returns, grouped bars (one per series). Partial years are dimmed. */
export function YearBars({ years, series, height = 288 }: {
  years: number[]; series: { key: string; name: string; values: Record<number, { v: number; partial: boolean }>; color?: string }[]; height?: number;
}) {
  const rows: Record<string, string | number | null>[] = years.map((y) => ({ year: String(y), ...Object.fromEntries(series.map((s) => [s.key, s.values[y]?.v ?? null])) }));
  if (!rows.length) return <div style={{ height }}><Empty text="No calendar-year data" /></div>;
  return (
    <div style={{ height }} role="img" aria-label="Calendar year returns">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="year" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
          <ReferenceLine y={0} stroke="var(--qs-line-strong)" />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${Number(v).toFixed(2)}%`} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color ?? SERIES[i % SERIES.length]} radius={[2, 2, 0, 0]} isAnimationActive={false}>
              {rows.map((r, j) => {
                const partial = s.values[years[j]]?.partial;
                const v = r[s.key] as number | null;
                const base = series.length === 1 ? (v !== null && v < 0 ? DOWN : UP) : (s.color ?? SERIES[i % SERIES.length]);
                return <Cell key={j} fill={base} fillOpacity={partial ? 0.45 : 1} />;
              })}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}


export type Band = { start: string; end: string; color: string };

/** Line chart with shaded background bands (regime periods). */
export function BandedLine({ data, bands, height = 288, name = "Index", logScale = true }: { data: Point[]; bands: Band[]; height?: number; name?: string; logScale?: boolean }) {
  const rows = data.map(([date, v]) => ({ date, v }));
  if (!rows.length) return <div style={{ height }}><Empty text="No data" /></div>;
  const dates = new Set(rows.map((r) => r.date));
  const snap = (d: string, dir: 1 | -1) => {
    if (dates.has(d)) return d;
    const i = rows.findIndex((r) => r.date >= d);
    return rows[dir === 1 ? Math.max(0, i === -1 ? rows.length - 1 : i) : Math.max(0, (i === -1 ? rows.length : i) - 1)].date;
  };
  return (
    <div style={{ height }} role="img" aria-label={`${name} with regime periods shaded`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" vertical={false} />
          {bands.map((b, i) => <ReferenceArea key={i} x1={snap(b.start, 1)} x2={snap(b.end, -1)} fill={b.color} fillOpacity={0.14} strokeOpacity={0} />)}
          <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} minTickGap={48} tickFormatter={fmtDate} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} scale={logScale ? "log" : "auto"} domain={["auto", "auto"]} tickFormatter={(v: number) => v.toFixed(0)} />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => Number(v).toFixed(1)} />
          <Line type="monotone" dataKey="v" name={name} stroke={SERIES[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export type ClusterPoint = { x: number; y: number; cluster: number; name: string };

/** PCA scatter coloured by cluster (palette in fixed order; noise = slate). */
export function ClusterScatter({ points, height = 360 }: { points: ClusterPoint[]; height?: number }) {
  const ids = [...new Set(points.map((p) => p.cluster))].sort((a, b) => a - b);
  if (!points.length) return <div style={{ height }}><Empty text="No data" /></div>;
  return (
    <div style={{ height }} role="img" aria-label="Fund clusters on the first two principal components">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" name="PC1" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis type="number" dataKey="y" name="PC2" tick={AXIS} axisLine={false} tickLine={false} width={36} />
          <ZAxis range={[28, 28]} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ strokeDasharray: "3 3" }}
            content={({ payload }) => payload?.length ? (
              <div style={{ ...TOOLTIP, border: "1px solid var(--qs-line)", padding: 6 }}>{(payload[0].payload as ClusterPoint).name}<br />cluster {(payload[0].payload as ClusterPoint).cluster}</div>) : null} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {ids.map((id) => (
            <Scatter key={id} name={id === -1 ? "Outliers" : `Cluster ${id + 1}`} data={points.filter((p) => p.cluster === id)} fill={id === -1 ? "#64748B" : SERIES[id % SERIES.length]} isAnimationActive={false} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export type FrontierProps = {
  frontier: { x: number; y: number }[]; assets: { x: number; y: number; name: string }[];
  selected: { x: number; y: number }; equal: { x: number; y: number }; height?: number;
};

/** Risk (x) versus expected return (y), both in percent. */
export function FrontierChart({ frontier, assets, selected, equal, height = 340 }: FrontierProps) {
  return (
    <div style={{ height }} role="img" aria-label="Efficient frontier with individual funds and the chosen portfolio">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 16 }}>
          <CartesianGrid stroke="var(--qs-line)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" name="Volatility" unit="%" tick={AXIS} axisLine={false} tickLine={false} domain={["auto", "auto"]} label={{ value: "Volatility (% a year)", position: "insideBottom", offset: -8, fontSize: 10, fill: "#64748b" }} />
          <YAxis type="number" dataKey="y" name="Expected return" unit="%" tick={AXIS} axisLine={false} tickLine={false} width={44} domain={["auto", "auto"]} />
          <ZAxis range={[40, 40]} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ strokeDasharray: "3 3" }}
            content={({ payload }) => payload?.length ? (
              <div style={{ ...TOOLTIP, border: "1px solid var(--qs-line)", padding: 6 }}>
                {(payload[0].payload as { name?: string }).name ?? payload[0].name}<br />risk {Number((payload[0].payload as { x: number }).x).toFixed(1)}% · return {Number((payload[0].payload as { y: number }).y).toFixed(1)}%
              </div>) : null} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Scatter name="Efficient frontier" data={frontier} fill={SERIES[0]} line={{ stroke: SERIES[0], strokeWidth: 2 }} shape={() => <g />} isAnimationActive={false} />
          <Scatter name="Individual funds" data={assets} fill="#64748B" isAnimationActive={false} />
          <Scatter name="Equal weight" data={[equal]} fill={SERIES[2]} isAnimationActive={false} />
          <Scatter name="Chosen portfolio" data={[selected]} fill={SERIES[1]} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
