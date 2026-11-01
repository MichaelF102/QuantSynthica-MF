import Link from "next/link";
import { Building2 } from "lucide-react";
import { ReportButtons } from "@/components/ReportButtons";
import { Banner, EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { ApiError, api, type AmcRanking } from "@/lib/api";
import { dash } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";
const n1 = (v: number | null | undefined) => (v === null || v === undefined ? dash : v.toFixed(1));

export default async function AmcPage() {
  let d: AmcRanking | null = null;
  let error: string | null = null;
  try { d = await api.amcs(); } catch (e) { error = e instanceof ApiError ? e.message : "Could not load AMC data."; }
  return (
    <>
      <PageHeader title="AMC" accent="Intelligence" subtitle="INTELLIGENCE"
        description="Fund houses compared on how their funds rank against their own category peers, using the median fund rather than the best one."
        right={<ReportButtons kind="amc" params={{}} />} />
      {error && <Banner tone="down">{error}</Banner>}
      {d && (
        <>
          <Banner tone="warn">The underlying score has not shown a net-of-cost selection edge in backtests, and only surviving funds are included. Treat this as a descriptive comparison, not a recommendation.</Banner>
          <Panel icon={Building2} title="Fund houses" description={`${d.eligible} of ${d.amcs.length} have enough funds to be ranked`}
            info="Percentiles run 0 to 100 within each fund's category and plan (100 = best). The AMC figure is the median across its funds.">
            {d.amcs.length === 0 ? <EmptyState title="No AMC data" /> : (
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>#</th><th className={TH}>AMC</th><th className={`${TH} text-right`}>Funds</th><th className={`${TH} text-right`}>Categories</th>
                    <th className={`${TH} text-right`}>Median score pctile</th><th className={`${TH} text-right`}>Above median</th><th className={`${TH} text-right`}>Top quartile</th><th className={`${TH} text-right`}>Bottom quartile</th><th className={`${TH} text-right`}>Largest category</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {d.amcs.map((a) => (
                      <tr key={a.amc_id} className="transition-colors hover:bg-hover">
                        <td className="px-2 py-2 font-mono text-muted">{a.rank ?? dash}</td>
                        <td className="max-w-[280px] truncate px-2 py-2 font-medium" title={a.reason ?? a.amc}><Link href={`/amc/${a.amc_id}`} className="text-fg hover:text-accent hover:underline">{a.amc}</Link>{!a.eligible && <span className="ml-2 text-[10px] text-faint">not ranked</span>}</td>
                        <td className="px-2 py-2 text-right">{a.funds}</td><td className="px-2 py-2 text-right">{a.categories}</td>
                        <td className="px-2 py-2 text-right font-semibold">{n1(a.median_score_percentile)}</td>
                        <td className="px-2 py-2 text-right">{a.share_above_median === null ? dash : `${a.share_above_median.toFixed(0)}%`}</td>
                        <td className="px-2 py-2 text-right">{a.share_top_quartile === null ? dash : `${a.share_top_quartile.toFixed(0)}%`}</td>
                        <td className="px-2 py-2 text-right">{a.share_bottom_quartile === null ? dash : `${a.share_bottom_quartile.toFixed(0)}%`}</td>
                        <td className="px-2 py-2 text-right text-muted" title={a.largest_category}>{a.largest_category_share.toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel title="How this is calculated"><ul className="space-y-1 text-[11px] text-faint">{d.method.map((m) => <li key={m}>• {m}</li>)}</ul></Panel>
        </>
      )}
    </>
  );
}
