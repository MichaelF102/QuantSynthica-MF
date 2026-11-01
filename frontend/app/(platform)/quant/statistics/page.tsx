import { BarChart3, Grid3x3 } from "lucide-react";
import { EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { LabKicker, TH } from "@/components/quant/QuantUi";
import { api, type QuantStats } from "@/lib/api";

function Heat({ keys, matrix, label }: { keys: string[]; matrix: number[][]; label: (k: string) => string }) {
  if (!matrix.length) return <EmptyState title="Not enough funds" hint="Needs at least 30 scored funds per date." />;
  return (
    <div className="w-full overflow-x-auto">
      <table className="border-collapse text-xs">
        <thead><tr><th />{keys.map((k) => <th key={k} className="max-w-[90px] px-1 py-1 text-[10px] font-medium text-muted"><span className="block truncate" title={label(k)}>{label(k)}</span></th>)}</tr></thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}><th className="max-w-[160px] truncate pr-2 text-left text-[11px] font-medium text-muted">{label(keys[i])}</th>
              {row.map((v, j) => <td key={j} className="px-2 py-1.5 text-center font-mono text-[11px] text-strong" style={{ background: `rgba(${v >= 0 ? "59,130,246" : "244,63,94"},${Math.abs(v * 0.6).toFixed(2)})` }}>{v.toFixed(2)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
const nice = (k: string) => k.replace(/^(f_|p_)/, "").replace(/_/g, " ");

export default async function StatisticsPage() {
  const s: QuantStats | null = await api.quantStats().catch(() => null);
  return (
    <>
      <PageHeader title="Statistical" accent="Analysis" subtitle="QUANT RESEARCH LAB"
        description="How the factors relate to each other and how scores and metrics are distributed across funds." />
      <LabKicker />
      {!s ? <Panel><EmptyState title="Not built yet" hint="Run `python -m app.cli.pipeline quant`." /></Panel> : (
        <>
          <Panel icon={Grid3x3} tone="ai" title="Factor correlations" description={`Average cross-sectional rank correlation${s.correlations.dates ? ` across ${s.correlations.dates} dates` : ""}`}
            info="High correlation between factors means they carry overlapping information, so their weights double-count.">
            <Heat keys={s.correlations.keys} matrix={s.correlations.matrix} label={nice} />
          </Panel>
          <Panel icon={Grid3x3} tone="ai" title="Metric percentile correlations" description="Same, for the individual metrics inside the factors">
            <Heat keys={s.metric_correlations.keys} matrix={s.metric_correlations.matrix} label={nice} />
          </Panel>
          <Panel icon={BarChart3} title="Distributions (latest date)" description="Across all scored funds; extremes are winsorised only inside the score">
            {s.distributions.length === 0 ? <EmptyState title="Not enough funds" /> : (
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Metric</th>{["n", "mean", "std", "5th", "median", "95th", "skew", "ex. kurtosis"].map((h) => <th key={h} className={`${TH} text-right`}>{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {s.distributions.map((d) => (
                      <tr key={d.metric} className="transition-colors hover:bg-hover"><td className="px-2 py-2 font-medium text-fg">{nice(d.metric)}</td>
                        {[d.n, d.mean, d.std, d.p5, d.median, d.p95, d.skew, d.excess_kurtosis].map((v, i) => <td key={i} className="px-2 py-2 text-right">{i === 0 ? v : v.toFixed(2)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel icon={BarChart3} title="Scores by asset tier" description="Composite is peer-relative, so averages near 50 are expected; the spread is what matters">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Tier</th>{["Scored", "Mean", "10th", "Median", "90th"].map((h) => <th key={h} className={`${TH} text-right`}>{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-line/50">
                  {s.score_by_tier.map((t) => <tr key={t.tier}><td className="px-2 py-2 font-medium text-fg">{t.tier}</td>{[t.scored, t.mean, t.p10, t.median, t.p90].map((v, i) => <td key={i} className="px-2 py-2 text-right">{i === 0 ? v : v.toFixed(1)}</td>)}</tr>)}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
