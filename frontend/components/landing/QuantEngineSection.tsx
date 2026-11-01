import Link from "next/link";
import { Filter, Network, Scale, TestTube2 } from "lucide-react";
import { api, type QuantMethodology } from "@/lib/api";
import { FeatureCard, SectionShell } from "./SectionShell";

/** Quantitative intelligence engine: the score's real weights (read from the API) and what the research found. */
export async function QuantEngineSection() {
  let m: QuantMethodology | null = null;
  try { m = await api.quantMethodology(); } catch { m = null; }
  const rows = m ? Object.entries(m.weights).map(([k, w]) => ({ key: k, label: m.factor_labels[k] ?? k, weight: w, missing: k in m.unavailable })) : [];
  const max = Math.max(1, ...rows.map((r) => r.weight));
  return (
    <SectionShell id="engine" eyebrow="Quantitative intelligence engine" title="A score built from" accent="five measurable factors" lead="Funds are ranked only against true peers (same category and plan). Each factor is a percentile within that peer group, and the weights are published.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20 lg:col-span-5">
          <h3 className="text-sm font-bold text-strong">QuantSynthica score weights</h3>
          <p className="mb-3 text-[11px] text-muted">{m ? `Methodology ${m.version}` : "Methodology unavailable right now"}</p>
          {rows.length === 0 ? <p className="text-xs text-faint">—</p> : (
            <ul className="space-y-2.5">
              {rows.map((r) => (
                <li key={r.key} className="text-xs">
                  <div className="mb-1 flex justify-between"><span className="text-fg">{r.label}</span><span className="font-mono text-strong">{r.weight}%</span></div>
                  <div className="h-2 rounded bg-raised"><div className={`h-2 rounded ${r.missing ? "bg-line-strong" : "bg-accent"}`} style={{ width: `${(r.weight / max) * 100}%` }} /></div>
                  {r.missing && <p className="mt-1 text-[10px] text-faint">Needs data not yet connected; the other weights are renormalised.</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-7">
          <FeatureCard icon={Scale} title="Peer-relative, not absolute">A debt fund is never ranked against an equity fund. Missing metrics are never filled with zero.</FeatureCard>
          <FeatureCard icon={TestTube2} title="Tested before it is trusted">Factors are checked for rank correlation with later peer-relative returns, using only information available at each date.</FeatureCard>
          <FeatureCard icon={Network} title="Clustering and statistics">K-Means, hierarchical, mixture and density clustering inside each asset tier, plus correlation and distribution views.</FeatureCard>
          <FeatureCard icon={Filter} title="Backtested honestly">Nine selection strategies tested with delay, trading costs and exit loads, against an equal-weighted benchmark of the same funds.</FeatureCard>
        </div>
      </div>
      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted">
        What the evidence says: momentum showed a positive link to later peer-relative returns, but no strategy, including the composite score, beat the benchmark after costs.
        The score is a research indicator, not a prediction. <Link href="/quant/factors" className="font-medium text-accent hover:underline">See the factor research</Link>.
      </p>
    </SectionShell>
  );
}

export function QuantEngineSkeleton() {
  return <SectionShell id="engine" eyebrow="Quantitative intelligence engine" title="A score built from" accent="five measurable factors"><div aria-busy="true" aria-label="Loading" className="h-64 animate-pulse rounded-xl bg-line/40" /></SectionShell>;
}
