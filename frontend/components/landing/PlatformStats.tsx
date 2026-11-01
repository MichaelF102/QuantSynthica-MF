import { api, type PlatformStats as Stats } from "@/lib/api";
import { SectionShell } from "./SectionShell";

const n = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("en-IN"));
const compact = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v >= 1e6 ? `${(v / 1e6).toFixed(1)} M` : n(v));
const year = (d: string | null | undefined) => (d ? d.slice(0, 4) : "—");

/** Platform statistics: counts read from the live database. A figure that cannot be computed shows a dash, never a guess. */
export async function PlatformStats() {
  let s: Stats | null = null;
  try { s = await api.platformStats(); } catch { s = null; }
  const tiles = [
    { label: "Funds covered", value: n(s?.funds), sub: `${n(s?.categories)} categories` },
    { label: "Fund houses", value: n(s?.fund_houses), sub: "excluding insurer-linked" },
    { label: "NAV observations", value: compact(s?.nav_observations), sub: `${year(s?.history_from)} to ${year(s?.history_to)}` },
    { label: "Funds with NAV history", value: n(s?.funds_with_nav_history), sub: "linked to official records" },
    { label: "Funds scored", value: n(s?.funds_scored), sub: s ? `score ${s.score_version}` : "—" },
    { label: "Strategies tested", value: n(s?.strategies_tested), sub: "point-in-time backtests" },
  ];
  return (
    <SectionShell id="stats" eyebrow="Platform statistics" title="Built on" accent="real, auditable data" lead="These numbers are read from the platform's own database when you open this page.">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20">
            <dt className="text-[10px] uppercase tracking-wider text-muted">{t.label}</dt>
            <dd className="mt-1 font-mono text-2xl font-bold text-strong">{t.value}</dd>
            <p className="mt-0.5 text-[10px] text-faint">{t.sub}</p>
          </div>
        ))}
      </dl>
      {!s && <p role="status" className="mt-3 text-[11px] text-faint">Live statistics are unavailable right now.</p>}
    </SectionShell>
  );
}

export function PlatformStatsSkeleton() {
  return (
    <SectionShell id="stats" eyebrow="Platform statistics" title="Built on" accent="real, auditable data">
      <div aria-busy="true" aria-label="Loading statistics" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-line/40" />)}
      </div>
    </SectionShell>
  );
}
