import { FlaskConical, ShieldAlert } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel, SegmentedLinks, StatTile } from "@/components/ui/ui";
import { Caveats, LabKicker, TH } from "@/components/quant/QuantUi";
import { api } from "@/lib/api";
import { dash, fmtInt, share } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const LABEL: Record<string, string> = {
  composite: "Composite score", f_performance: "Performance", f_risk_adjusted: "Risk-adjusted", f_consistency: "Consistency", f_downside: "Downside protection", f_momentum: "Momentum",
};

function icColor(v: number) {
  const t = Math.max(-0.2, Math.min(0.2, v)) / 0.2;
  return t >= 0 ? `rgba(16,185,129,${(0.08 + 0.5 * t).toFixed(2)})` : `rgba(244,63,94,${(0.08 + 0.5 * -t).toFixed(2)})`;
}

export default async function FactorsPage({ searchParams }: { searchParams: SP }) {
  const f = await api.quantFactors().catch(() => null);
  const sp = await searchParams;
  const h = [1, 3, 6, 12].includes(Number(first(sp.h))) ? Number(first(sp.h)) : 3;
  return (
    <>
      <PageHeader title="Factor" accent="Research" subtitle="QUANT RESEARCH LAB"
        description="Do higher scores on each factor precede better returns than peers? Rank information coefficient (IC) of each signal against the next period's peer-relative return, point-in-time." />
      {!f ? <Panel><EmptyState icon={FlaskConical} title="Research not built yet" hint="Run `python -m app.cli.pipeline quant`." /></Panel> : (
        <>
          <LabKicker>{f.scoring_version}</LabKicker>
          <Banner tone="warn"><span>Read with care. {f.caveats[0]} {f.caveats[3]}</span></Banner>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Dates tested" value={fmtInt(f.dates)} sub={`${f.first_date} to ${f.last_date}`} />
            <StatTile label="Signals x horizons" value={fmtInt(f.ic.length)} />
            <StatTile label="Top quartile stays top quartile" value={share(f.persistence.share_in_top_quartile_next)} sub={`vs ${share(f.persistence.random_expectation)} by chance, next ${f.persistence.months} months`} />
            <StatTile label="Observations" value={fmtInt(f.persistence.observations)} sub="overlapping; descriptive only" />
          </div>
          {f.ic.length === 0 ? <Panel><EmptyState icon={FlaskConical} title="Too few funds for a cross-sectional test" hint="At least 20 scored funds per date are needed." /></Panel> : (
            <Panel icon={FlaskConical} tone="ai" title={`Predictive power, ${h}-month horizon`} description="Mean rank IC across dates; t-statistic from non-overlapping dates only"
              right={<SegmentedLinks label="Horizon" active={String(h)} items={[1, 3, 6, 12].map((x) => ({ key: String(x), label: `${x}M`, href: `/quant/factors?h=${x}` }))} />}
              info="IC is the Spearman correlation between a fund's signal percentile and its return minus the peer-group median over the next period. Above 0.05 consistently is usually considered useful; here it is a research result on survivors only.">
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Signal</th><th className={`${TH} text-right`}>Mean IC</th><th className={`${TH} text-right`}>t-stat</th>
                    <th className={`${TH} text-right`}>Hit rate</th><th className={`${TH} text-right`}>Top - bottom (pp)</th><th className={`${TH} text-right`}>Dates</th><th className={`${TH} text-right`}>Independent</th><th className={`${TH} text-right`}>Funds / date</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {f.ic.filter((r) => r.horizon_months === h).sort((a, b) => b.mean_ic - a.mean_ic).map((r) => (
                      <tr key={r.signal} className="transition-colors hover:bg-hover">
                        <td className="px-2 py-2 font-medium text-fg">{LABEL[r.signal] ?? r.signal.replace(/^p_/, "").replace(/_/g, " ")}</td>
                        <td className="px-2 py-2 text-right font-semibold text-strong" style={{ background: icColor(r.mean_ic) }}>{r.mean_ic.toFixed(3)}</td>
                        <td className="px-2 py-2 text-right" title={r.t_stat === null ? "Fewer than 10 non-overlapping dates: no t-statistic is reported" : undefined}>{r.t_stat === null ? dash : r.t_stat.toFixed(2)}</td>
                        <td className="px-2 py-2 text-right">{share(r.hit_rate)}</td>
                        <td className="px-2 py-2 text-right">{r.top_minus_bottom_pct === null ? dash : r.top_minus_bottom_pct.toFixed(2)}</td>
                        <td className="px-2 py-2 text-right text-muted">{r.dates}</td>
                        <td className="px-2 py-2 text-right text-muted">{r.independent_dates}</td>
                        <td className="px-2 py-2 text-right text-muted">{r.avg_funds.toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
          <Panel icon={ShieldAlert} tone="warn" title="Caveats"><Caveats items={f.caveats} /></Panel>
        </>
      )}
    </>
  );
}
