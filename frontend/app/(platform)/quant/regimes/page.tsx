import { Activity, Compass, Waves } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel, StatTile } from "@/components/ui/ui";
import { BandedLine, type Band } from "@/components/charts/ChartKit";
import { Caveats, LabKicker, TH } from "@/components/quant/QuantUi";
import { api, type RegimeStat } from "@/lib/api";
import { dash, fmtPct } from "@/lib/format";

const COLOR: Record<string, string> = { bull: "#10b981", bear: "#f43f5e", sideways: "#D97706", low: "#10b981", medium: "#D97706", high: "#f43f5e", calm: "#10b981", moderate: "#D97706", turbulent: "#f43f5e" };
const bands = (tl: { regime: string; start: string; end: string }[] | undefined): Band[] => (tl ?? []).map((t) => ({ start: t.start, end: t.end, color: COLOR[t.regime] ?? "#64748B" }));

function Stats({ rows }: { rows: RegimeStat[] | undefined }) {
  if (!rows?.length) return <p className="text-xs text-faint">No statistics.</p>;
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead><tr className="border-b border-line"><th className={TH}>Regime</th>{["Share of days", "Ann. return", "Ann. volatility", "Avg duration (days)", "Episodes"].map((h) => <th key={h} className={`${TH} text-right`}>{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line/50">
          {rows.map((r) => (
            <tr key={r.regime} className="transition-colors hover:bg-hover"><td className="px-2 py-2 font-medium capitalize" style={{ color: COLOR[r.regime] }}>{r.regime}</td>
              <td className="px-2 py-2 text-right">{(r.share * 100).toFixed(0)}%</td><td className="px-2 py-2 text-right font-semibold">{fmtPct(r.annualised_return, 1)}</td>
              <td className="px-2 py-2 text-right">{r.annualised_vol.toFixed(1)}%</td><td className="px-2 py-2 text-right">{r.avg_duration_days.toFixed(0)}</td><td className="px-2 py-2 text-right">{r.episodes}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Trans({ t }: { t: { states: string[]; matrix: number[][] } | undefined }) {
  if (!t) return null;
  return (
    <table className="mt-3 border-collapse text-xs">
      <thead><tr><th className="pr-3 text-left text-[10px] font-medium uppercase tracking-wider text-muted">From \ to</th>{t.states.map((s) => <th key={s} className="px-3 text-[10px] font-medium capitalize text-muted">{s}</th>)}</tr></thead>
      <tbody>{t.matrix.map((row, i) => <tr key={i}><th className="pr-3 text-left text-[11px] font-medium capitalize text-muted">{t.states[i]}</th>{row.map((v, j) => <td key={j} className="px-3 py-1.5 text-center font-mono text-strong" style={{ background: `rgba(59,130,246,${(v * 0.55).toFixed(2)})` }}>{v.toFixed(2)}</td>)}</tr>)}</tbody>
    </table>
  );
}

export default async function RegimesPage() {
  const r = await api.quantRegimes().catch(() => null);
  return (
    <>
      <PageHeader title="Regime" accent="Analysis" subtitle="QUANT RESEARCH LAB"
        description="Bull, bear and sideways phases and calm or turbulent volatility, measured on an internal equity market proxy. Point-in-time rules use only past data; the mixture model is descriptive hindsight." />
      <LabKicker />
      {!r ? <Panel><EmptyState icon={Compass} title="Not built yet" hint="Run `python -m app.cli.pipeline quant`." /></Panel> : (
        <>
          <Banner tone="accent"><span>Market proxy: {r.proxy}. There is no licensed index connected, so this is a peer-fund proxy and carries survivorship bias.</span></Banner>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Trend regime now" value={r.current.trend ?? dash} valueClass="capitalize" sub="200-day average and 6-month momentum" />
            <StatTile label="Volatility regime now" value={r.current.volatility ?? dash} valueClass="capitalize" sub="vs its own past" />
            <StatTile label="Volatility state now (HMM)" value={r.current.hmm ?? dash} valueClass="capitalize" sub={r.hmm.train_end ? `fitted to ${r.hmm.train_end}, filtered after` : undefined} />
            <StatTile label="Proxy period" value={r.start.slice(0, 4) + "-" + r.end.slice(0, 4)} sub={`${r.start} to ${r.end}`} />
          </div>
          {(() => {
            const bull = r.trend.stats.find((x) => x.regime === "bull"), bear = r.trend.stats.find((x) => x.regime === "bear");
            return bull && bear && bear.annualised_return >= bull.annualised_return - 2 ? (
              <Banner tone="warn"><span>On this data the trend regime did not separate forward returns: the day after a bear label returned {fmtPct(bear.annualised_return, 1)} a year versus {fmtPct(bull.annualised_return, 1)} after a bull label. Do not read the labels as a timing signal.</span></Banner>
            ) : null;
          })()}
          <Panel icon={Compass} tone="ai" title="Trend regimes over time" description="Shaded by regime; log scale" info={r.trend.rule}>
            <BandedLine data={r.index} bands={bands(r.trend.timeline)} name="Market proxy" />
            <div className="mt-2 flex gap-4 text-[11px] text-muted">{["bull", "sideways", "bear"].map((k) => <span key={k} className="inline-flex items-center gap-1.5 capitalize"><span className="inline-block h-2 w-3 rounded-sm" style={{ background: COLOR[k], opacity: 0.5 }} />{k}</span>)}</div>
            <div className="mt-3"><Stats rows={r.trend.stats} /><Trans t={r.trend.transitions} /></div>
          </Panel>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel icon={Waves} tone="ai" title="Volatility regimes" description="Low / medium / high" info={r.volatility.rule}><Stats rows={r.volatility.stats} /></Panel>
            <Panel icon={Activity} tone="ai" title="Hidden Markov model" description="Three volatility states, filtered (forward-only) probabilities" info={r.hmm.note}>
              {r.hmm.stats ? <><Stats rows={r.hmm.stats} /><Trans t={r.hmm.transitions} />
                <p className="mt-2 text-[11px] text-faint">{r.hmm.note} Labels before {r.hmm.train_end} are in-sample. States are named by fitted volatility because a model on daily returns separates calm from turbulent periods, not bull from bear.</p></> : <p className="text-xs text-faint">{r.hmm.reason}</p>}
            </Panel>
          </div>
          <Panel icon={Activity} tone="ai" title="Gaussian mixture (descriptive only)" description="Fitted on the full sample: hindsight, never used for decisions"><Stats rows={r.gmm.stats} /><p className="mt-2 text-[11px] text-faint">{r.gmm.note}</p></Panel>
          <Caveats items={["Regime statistics use the return on the day AFTER each label, so a label is never credited with the move that created it.", "Regimes describe the past; they are not forecasts.", "Few episodes per regime means statistics are noisy.", "A regime-aware strategy built on them is tested in Strategy Backtesting with the same point-in-time rules."]} />
        </>
      )}
    </>
  );
}
