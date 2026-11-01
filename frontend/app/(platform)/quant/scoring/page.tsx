import Link from "next/link";
import { Search, Trophy, Layers } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel, btnPrimary, inputCls } from "@/components/ui/ui";
import { Caveats, FactorBar, LabKicker, ScorePill, TH } from "@/components/quant/QuantUi";
import { api } from "@/lib/api";
import { fmtInt } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const FACTORS = ["performance", "risk_adjusted", "consistency", "downside", "momentum"] as const;

export default async function ScoringPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const page = Math.max(1, Number(first(sp.page)) || 1);
  const group = first(sp.group), tier = first(sp.tier), q = first(sp.q);
  const primary = first(sp.primary) !== "0";
  const [data, groups, m] = await Promise.all([
    api.quantScores({ page, page_size: 50, group, tier, q, primary_only: String(primary) }).catch(() => null),
    api.quantGroups().catch(() => []),
    api.quantMethodology(),
  ]);
  const link = (over: Record<string, string | number | undefined>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries({ group, tier, q, primary: primary ? undefined : "0", page, ...over })) if (v !== undefined && v !== "") p.set(k, String(v));
    return `/quant/scoring?${p.toString()}`;
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader title="Fund" accent="Scoring" subtitle="QUANT RESEARCH LAB"
        description="The QuantSynthica Fund Score ranks each fund against its own peers (same category and plan) on performance, risk-adjusted returns, consistency, downside protection and momentum. A research indicator, not a prediction." />
      <LabKicker>{m.version}</LabKicker>
      <Banner tone="warn"><span>The Stability factor ({m.weights.stability}%) cannot be computed: {m.unavailable.stability}</span></Banner>

      <Panel>
        <form method="get" className="flex flex-wrap items-end gap-3 text-xs" role="search">
          <label className="flex flex-col gap-1"><span className="text-muted">Search</span>
            <span className="relative flex items-center"><Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted" />
              <input name="q" defaultValue={q} placeholder="Fund name" className={`${inputCls} pl-8`} /></span></label>
          <label className="flex flex-col gap-1"><span className="text-muted">Peer group</span>
            <select name="group" defaultValue={group ?? ""} className={`${inputCls} max-w-[260px]`}>
              <option value="">All groups</option>{groups.map((g) => <option key={g.group} value={g.group}>{g.group} ({g.scored})</option>)}</select></label>
          <label className="flex flex-col gap-1"><span className="text-muted">Asset tier</span>
            <select name="tier" defaultValue={tier ?? ""} className={inputCls}><option value="">All</option>{["Equity", "Debt", "Hybrid", "Other"].map((t) => <option key={t}>{t}</option>)}</select></label>
          <label className="flex items-center gap-2 pb-2 text-muted"><input type="checkbox" name="primary" value="1" defaultChecked={primary} /> Direct plans only</label>
          <button className={btnPrimary}>Apply</button>
          <Link href="/quant/scoring" className="px-2 py-2 text-[11px] font-medium text-accent hover:underline">Reset</Link>
        </form>
      </Panel>

      <Panel icon={Trophy} tone="ai" title="Ranked funds" description={data ? `${fmtInt(data.total)} scored funds · as of ${data.as_of} · ${data.methodology_version}` : undefined}
        info="Composite 0-100 within the peer group. Higher is better. Percentile-based, so a group of weak funds still has a top fund.">
        {!data || data.items.length === 0 ? <EmptyState title="No scored funds" hint="Run `python -m app.cli.pipeline quant`, or relax the filters." /> : (
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead><tr className="border-b border-line">
                <th className={`${TH} w-10 text-center`}>#</th><th className={TH}>Fund</th><th className={TH}>Peer group</th>
                <th className={`${TH} text-right`}>Score</th><th className={`${TH} text-right`}>Rank</th><th className={`${TH} text-right`}>Coverage</th>
                {FACTORS.map((f) => <th key={f} className={TH}>{m.factor_labels[f]}</th>)}</tr></thead>
              <tbody className="divide-y divide-line/50">
                {data.items.map((r, i) => (
                  <tr key={r.scheme_id} className="transition-colors hover:bg-hover">
                    <td className="py-2 pr-2 text-center font-mono text-[11px] text-muted">{(data.page - 1) * data.page_size + i + 1}</td>
                    <td className="max-w-[280px] px-2 py-2"><Link href={`/funds/${r.scheme_id}?tab=score`} className="font-medium text-fg hover:text-accent">{r.name}</Link></td>
                    <td className="px-2 py-2 text-muted">{r.peer_group}</td>
                    <td className="px-2 py-2 text-right"><ScorePill v={r.composite} /></td>
                    <td className="px-2 py-2 text-right text-muted">{r.rank_in_group ?? "—"} / {r.peers}</td>
                    <td className="px-2 py-2 text-right text-muted">{r.coverage === null ? "—" : `${Math.round(r.coverage * 100)}%`}</td>
                    {FACTORS.map((f) => <td key={f} className="px-2 py-2"><FactorBar v={r.factors[f]} label={m.factor_labels[f]} /></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <div className="flex items-center justify-between text-xs text-muted">
        <span className="font-mono">Page {page} of {pages}</span>
        <div className="flex gap-4">
          {page > 1 && <Link href={link({ page: page - 1 })} className="font-medium text-accent hover:underline">← Previous</Link>}
          {page < pages && <Link href={link({ page: page + 1 })} className="font-medium text-accent hover:underline">Next →</Link>}
        </div>
      </div>

      <Panel icon={Layers} tone="ai" title="How the score is built" description={`Methodology ${m.version}`}>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead><tr className="border-b border-line"><th className={TH}>Factor</th><th className={`${TH} text-right`}>Weight</th><th className={TH}>Metrics</th></tr></thead>
              <tbody className="divide-y divide-line/50">
                {Object.entries(m.weights).map(([k, w]) => (
                  <tr key={k}><td className="px-2 py-2 font-medium text-fg">{m.factor_labels[k]}</td>
                    <td className="px-2 py-2 text-right">{w}%</td>
                    <td className="px-2 py-2 text-muted">{k === "stability" ? "Not available (needs AUM, expense and manager history)" : m.metrics.filter((x) => x.factor === k).map((x) => x.label).join(", ")}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <Caveats items={m.rules} />
        </div>
      </Panel>
    </>
  );
}
