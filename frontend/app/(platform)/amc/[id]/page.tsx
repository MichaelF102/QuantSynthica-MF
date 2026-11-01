import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { Banner, PageHeader, Panel, StatTile } from "@/components/ui/ui";
import { dash } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";
const n1 = (v: number | null | undefined) => (v === null || v === undefined ? dash : v.toFixed(1));

export default async function AmcDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();
  let d;
  try { d = await api.amc(id); } catch (e) { if (e instanceof ApiError && e.status === 404) notFound(); throw e; }
  const s = d.summary;
  return (
    <>
      <PageHeader title={s.amc} subtitle="AMC INTELLIGENCE" description="Direct Growth plans, each fund placed against peers in its own category." right={<Link href="/amc" className="text-xs text-accent hover:underline">← All AMCs</Link>} />
      {!s.eligible && <Banner tone="warn">Not ranked: {s.reason}.</Banner>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <StatTile label="Rank" value={s.rank ? `#${s.rank}` : dash} /><StatTile label="Median score percentile" value={n1(s.median_score_percentile)} />
        <StatTile label="Funds (scored)" value={`${s.funds} (${s.scored_funds})`} /><StatTile label="Categories" value={String(s.categories)} />
        <StatTile label="Largest category" value={`${s.largest_category_share.toFixed(0)}%`} sub={s.largest_category} />
      </div>
      <Panel title="By category" description="Median fund percentile within each category">
        <table className="w-full border-collapse text-left text-xs"><thead><tr className="border-b border-line"><th className={TH}>Category</th><th className={`${TH} text-right`}>Funds</th><th className={`${TH} text-right`}>Median percentile</th><th className={`${TH} text-right`}>Best fund</th></tr></thead>
          <tbody className="divide-y divide-line/50">{d.categories.map((c) => <tr key={c.category} className="hover:bg-hover"><td className="px-2 py-2 text-fg">{c.category}</td><td className="px-2 py-2 text-right">{c.funds}</td><td className="px-2 py-2 text-right font-semibold">{n1(c.median_score_percentile)}</td><td className="px-2 py-2 text-right">{n1(c.best_percentile)}</td></tr>)}</tbody></table>
      </Panel>
      <Panel title="Funds" description={d.note}>
        <div className="w-full overflow-x-auto"><table className="w-full border-collapse text-left text-xs"><thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={TH}>Category</th><th className={`${TH} text-right`}>Score percentile</th></tr></thead>
          <tbody className="divide-y divide-line/50">{d.funds.map((f) => <tr key={f.scheme_id} className="hover:bg-hover"><td className="max-w-[320px] truncate px-2 py-2 font-medium" title={f.name}><Link href={`/funds/${f.scheme_id}`} className="text-fg hover:text-accent hover:underline">{f.name}</Link></td><td className="px-2 py-2 text-muted">{f.category}</td><td className="px-2 py-2 text-right font-mono">{n1(f.p_score)}</td></tr>)}</tbody></table></div>
      </Panel>
    </>
  );
}
