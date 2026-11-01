import Link from "next/link";
import { BarChart3, Building2, Flame, Grid3x3, Layers, Trophy, Wallet } from "lucide-react";
import { BarRow, Banner, Panel, PageHeader, SegmentedLinks, StatTile, btnSecondary } from "@/components/ui/ui";
import { api, type Horizon } from "@/lib/api";
import { crore, dash, fmtInt, heat, lakhCrore, pct, share, tone } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const HORIZONS: Horizon[] = ["ytd", "3m", "1y", "3y", "5y"];
const LABEL: Record<Horizon, string> = { ytd: "YTD", "3m": "3M", "1y": "1Y", "3y": "3Y", "5y": "5Y" };
const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

export default async function OverviewPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const h = (HORIZONS as string[]).includes(first(sp.horizon) ?? "") ? (first(sp.horizon) as Horizon) : "1y";
  const insurer = first(sp.insurer) === "1";
  const d = await api.overview(h, insurer);
  const c = d.counts;
  const href = (over: { horizon?: string; insurer?: boolean }) =>
    `/overview?horizon=${over.horizon ?? h}${(over.insurer ?? insurer) ? "&insurer=1" : ""}`;
  const maxTier = Math.max(...d.tiers.map((t) => t.schemes));

  return (
    <>
      <PageHeader
        title="Indian Mutual Fund" accent="Market Overview" subtitle="DISCOVER"
        description={`${d.snapshot_note} Universe: ${d.universe.description}.`}
        right={<Link href={href({ insurer: !insurer })} className={btnSecondary}>{insurer ? "Exclude insurer funds" : "Include insurer funds"}</Link>}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <StatTile icon={Layers} label="Schemes in universe" value={fmtInt(c.schemes_in_universe)}
          sub={`of ${fmtInt(c.schemes_total)} in file · ${c.insurer_funds} insurer · ${c.discontinued} discontinued`} />
        <StatTile icon={Layers} label="Fund families" value={fmtInt(c.families)} sub="share classes grouped by fund" />
        <StatTile icon={Building2} label="AMCs · categories" value={`${c.amcs} · ${c.categories}`} />
        <StatTile icon={BarChart3} label="Median 1Y return" value={pct(d.returns_1y.median)} valueClass={tone(d.returns_1y.median)}
          sub={`mean ${pct(d.returns_1y.mean)} · n=${fmtInt(d.returns_1y.n)}`} />
        <StatTile icon={Wallet} label="Reported net assets (sum)" value={lakhCrore(d.aum.total_rupees)}
          sub={`${d.aum.families_with_aum} of ${d.aum.families_total} families (${share(d.aum.coverage)}); not industry AUM`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <Panel icon={Layers} title="Asset tier distribution" description="Schemes (share classes) in universe"
            info="Count of share classes per asset tier. One fund can appear several times (Direct/Regular, Growth/IDCW).">
            {d.tiers.map((t) => <BarRow key={t.tier} label={t.tier} value={t.schemes} max={maxTier} text={fmtInt(t.schemes)} />)}
          </Panel>
        </div>
        <div className="lg:col-span-8">
          <Panel icon={Flame} title="Market breadth" description="Absolute, not category-relative"
            info="Share of schemes with a positive return over each horizon, and share trading above their 50-day and 200-day average price.">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line">
                  <th className={TH}>Tier</th>
                  {HORIZONS.map((x) => <th key={x} className={`${TH} text-right`}>{LABEL[x]} &gt; 0</th>)}
                  <th className={`${TH} text-right`}>&gt; 50d avg</th><th className={`${TH} text-right`}>&gt; 200d avg</th>
                </tr></thead>
                <tbody className="divide-y divide-line/50">
                  {d.breadth.map((b) => (
                    <tr key={b.tier} className="transition-colors hover:bg-hover">
                      <td className="px-2 py-2 font-medium text-fg">{b.tier} <span className="font-mono text-[11px] text-muted">({b.schemes})</span></td>
                      {HORIZONS.map((x) => <td key={x} className="px-2 py-2 text-right">{share(b.positive_return_share[x])}</td>)}
                      <td className="px-2 py-2 text-right">{share(b.above_50d_avg)}</td>
                      <td className="px-2 py-2 text-right">{share(b.above_200d_avg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>

      <Panel icon={Grid3x3} title="Category returns heatmap" description="Median return of schemes in each category (snapshot). † = fewer than 5 schemes."
        info="Median of the reported returns of all schemes in the category. 1M, 6M and 10Y are not in the source data.">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line">
              <th className={TH}>Category</th><th className={TH}>Tier</th><th className={`${TH} text-right`}>Schemes</th>
              {HORIZONS.map((x) => <th key={x} className={`${TH} text-right`}>{LABEL[x]}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line/50">
              {d.categories.map((r) => (
                <tr key={r.category} className="transition-colors hover:bg-hover">
                  <td className="px-2 py-1.5 font-medium text-fg">{r.category}{r.low_sample ? " †" : ""}</td>
                  <td className="px-2 py-1.5 text-muted">{r.asset_tier}</td>
                  <td className="px-2 py-1.5 text-right text-muted">{r.schemes}</td>
                  {HORIZONS.map((x) => (
                    <td key={x} className="px-2 py-1.5 text-right text-strong" style={{ background: heat(r.median_returns[x]) }}>{pct(r.median_returns[x], 1)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel icon={Building2} title="AMC leaderboard" description={`${d.amc_leaderboard.amcs_ranked} of ${d.amc_leaderboard.amcs_in_universe} AMCs have ≥${d.amc_leaderboard.min_schemes} schemes with 3Y data`}
          info="Median 3Y category percentile across an AMC's schemes, so one star fund cannot lift the ranking.">
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line"><th className={`${TH} w-6 text-center`}>#</th><th className={TH}>AMC</th><th className={`${TH} text-right`}>Median pctile</th><th className={`${TH} text-right`}>Schemes</th></tr></thead>
            <tbody className="divide-y divide-line/50">
              {d.amc_leaderboard.rows.slice(0, 15).map((r, i) => (
                <tr key={r.amc} className="transition-colors hover:bg-hover">
                  <td className="py-2 pr-2 text-center font-mono text-[11px] text-muted">{i + 1}</td>
                  <td className="max-w-[180px] truncate px-2 py-2 font-medium text-fg" title={r.amc}>{r.amc}</td>
                  <td className="px-2 py-2 text-right">{r.median_3y_category_percentile.toFixed(0)}</td>
                  <td className="px-2 py-2 text-right text-muted">{r.schemes_with_3y}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel icon={Trophy} tone="up" title={`Top performers (${LABEL[d.top_performers.horizon]})`} description="One share class per family"
          info={d.top_performers.note}
          right={<SegmentedLinks label="Horizon" active={h} items={HORIZONS.map((x) => ({ key: x, label: LABEL[x], href: href({ horizon: x }) }))} />}>
          <ol className="divide-y divide-line/50 text-xs">
            {d.top_performers.rows.map((r, i) => (
              <li key={r.id} className="flex items-baseline justify-between gap-2 py-2">
                <span className="min-w-0"><span className="mr-1 font-mono text-[11px] text-muted">{i + 1}</span>
                  <Link href={`/funds/${r.id}`} className="font-medium text-fg hover:text-accent">{r.name}</Link>
                  <span className="block truncate pl-4 text-[11px] text-muted">{r.category}</span></span>
                <span className="shrink-0 font-mono font-bold text-up">{pct(r.ret, 1)}</span>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel icon={Wallet} title="Largest funds by reported net assets" description="One share class per family"
          info="Values are as reported in the source data and are unverified.">
          <ol className="divide-y divide-line/50 text-xs">
            {d.top_by_aum.rows.map((r, i) => (
              <li key={r.id} className="flex items-baseline justify-between gap-2 py-2">
                <span className="min-w-0"><span className="mr-1 font-mono text-[11px] text-muted">{i + 1}</span>
                  <Link href={`/funds/${r.id}`} className="font-medium text-fg hover:text-accent">{r.name}</Link>
                  <span className="block truncate pl-4 text-[11px] text-muted">{r.category} · 1Y {pct(r.return_1y, 1)}</span></span>
                <span className="shrink-0 font-mono">{crore(r.net_assets)}</span>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
      <Banner tone="accent">{dash} Not shown (no data source yet): net flows, AUM history and trends, 1M / 6M / 10Y returns.</Banner>
    </>
  );
}
