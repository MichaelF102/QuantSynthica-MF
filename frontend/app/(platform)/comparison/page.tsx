import Link from "next/link";
import { GitCompareArrows, BarChart3 } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { FundPicker } from "@/components/funds/FundPicker";
import { ApiError, api, type CompareFund } from "@/lib/api";
import { crore, dash, fmtPrice, fmtPct, tone, num } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;
const MAX = 5;
const COLORS = ["bg-[#2563EB]", "bg-[#16A34A]", "bg-[#D97706]", "bg-[#7C3AED]", "bg-[#DC2626]"]; // series palette, DESIGN.md §4.4

export default async function ComparisonPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.ids) ? sp.ids[0] : sp.ids;
  const ids = [...new Set((raw ?? "").split(",").map((x) => Number(x)).filter((x) => Number.isInteger(x) && x > 0))].slice(0, MAX);

  let funds: CompareFund[] = [];
  let warnings: string[] = [];
  let error: string | null = null;
  if (ids.length) {
    try {
      const r = await api.compare(ids);
      funds = r.funds;
      warnings = r.warnings;
    } catch (e) {
      error = e instanceof ApiError && e.status === 404 ? "One or more funds were not found." : "Could not load comparison.";
    }
  }
  const without = (id: number) => `/comparison?ids=${ids.filter((x) => x !== id).join(",")}`;

  type Cell = (f: CompareFund) => { text: string; cls?: string };
  const rows: { label: string; cell: Cell }[] = [
    { label: "AMC", cell: (f) => ({ text: f.amc }) },
    { label: "Category", cell: (f) => ({ text: f.category }) },
    { label: "Plan · Option", cell: (f) => ({ text: `${f.plan_type} · ${f.option_type}` }) },
    { label: "Price / NAV", cell: (f) => ({ text: fmtPrice(f.price) }) },
    { label: "Net assets", cell: (f) => ({ text: crore(f.net_assets) }) },
    { label: "Min. investment", cell: (f) => ({ text: f.initial_investment === null ? dash : `₹${num(f.initial_investment, 0)}` }) },
    { label: "YTD", cell: (f) => ({ text: fmtPct(f.ytd_return), cls: tone(f.ytd_return) }) },
    { label: "3M", cell: (f) => ({ text: fmtPct(f.return_3m), cls: tone(f.return_3m) }) },
    { label: "1Y", cell: (f) => ({ text: fmtPct(f.return_1y), cls: tone(f.return_1y) }) },
    { label: "3Y", cell: (f) => ({ text: fmtPct(f.return_3y), cls: tone(f.return_3y) }) },
    { label: "5Y", cell: (f) => ({ text: fmtPct(f.return_5y), cls: tone(f.return_5y) }) },
    { label: "1Y category percentile", cell: (f) => ({ text: f.metrics.cat_pct_1y == null ? dash : f.metrics.cat_pct_1y.toFixed(0) }) },
    { label: "3Y category percentile", cell: (f) => ({ text: f.metrics.cat_pct_3y == null ? dash : f.metrics.cat_pct_3y.toFixed(0) }) },
    { label: "5Y category percentile", cell: (f) => ({ text: f.metrics.cat_pct_5y == null ? dash : f.metrics.cat_pct_5y.toFixed(0) }) },
    { label: "52w range position", cell: (f) => ({ text: f.metrics.range_position == null ? dash : `${f.metrics.range_position.toFixed(0)}%` }) },
    { label: "Price vs 50-day avg", cell: (f) => ({ text: fmtPct(f.metrics.price_vs_50d, 1), cls: tone(f.metrics.price_vs_50d) }) },
    { label: "Price vs 200-day avg", cell: (f) => ({ text: fmtPct(f.metrics.price_vs_200d, 1), cls: tone(f.metrics.price_vs_200d) }) },
  ];

  const bars: { label: string; get: (f: CompareFund) => number | null }[] = [
    { label: "1Y return", get: (f) => f.return_1y },
    { label: "3Y return", get: (f) => f.return_3y },
    { label: "5Y return", get: (f) => f.return_5y },
  ];

  return (
    <>
      <PageHeader title="Fund" accent="Comparison" subtitle="DISCOVER"
        description={`Compare up to ${MAX} schemes side by side using snapshot data. Risk, rolling-return and holdings comparisons need NAV and holdings data (not yet loaded).`} />
      <FundPicker ids={ids} max={MAX} />
      {error && <Banner tone="down">{error}</Banner>}
      {warnings.length > 0 && (
        <Banner tone="warn"><ul className="space-y-1">{warnings.map((w) => <li key={w}>{w}</li>)}</ul></Banner>
      )}
      {funds.length === 0 && !error ? (
        <Panel><EmptyState icon={GitCompareArrows} title="No funds selected"
          hint="Search above to add funds, or select funds in the Screener." /></Panel>
      ) : funds.length > 0 && (
        <>
          <Panel icon={GitCompareArrows} title="Side by side" description="Snapshot metrics, as reported in the source data">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-line">
                    <th className="w-44 px-2 py-2 text-[10px] font-medium uppercase tracking-wider text-muted">Metric</th>
                    {funds.map((f, i) => (
                      <th key={f.id} className="min-w-[200px] px-2 py-2 align-top text-xs font-medium">
                        <span className={`mr-2 inline-block h-2 w-2 rounded-full ${COLORS[i]}`} />
                        <Link href={`/funds/${f.id}`} className="text-strong hover:text-accent">{f.name}</Link>
                        <Link href={without(f.id)} className="ml-2 text-[11px] text-muted hover:text-down" aria-label={`Remove ${f.name}`}>remove</Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/50">
                  {rows.map((r) => (
                    <tr key={r.label} className="transition-colors hover:bg-hover">
                      <td className="px-2 py-2 text-muted">{r.label}</td>
                      {funds.map((f) => { const c = r.cell(f); return <td key={f.id} className={`px-2 py-2 font-mono ${c.cls ?? ""}`}>{c.text}</td>; })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel icon={BarChart3} title="Reported returns" description="Same scale across funds; missing values are blank">
            <div className="space-y-4">
              {bars.map((b) => {
                const vals = funds.map((f) => b.get(f));
                const max = Math.max(1, ...vals.map((v) => Math.abs(v ?? 0)));
                return (
                  <div key={b.label}>
                    <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">{b.label}</div>
                    {funds.map((f, i) => {
                      const v = b.get(f);
                      return (
                        <div key={f.id} className="flex items-center gap-2 py-0.5 text-[11px]">
                          <div className="w-40 shrink-0 truncate text-muted" title={f.name}>{f.name}</div>
                          <div className="h-2.5 flex-1 rounded bg-raised">
                            {v !== null && <div className={`h-2.5 rounded ${v >= 0 ? COLORS[i] : "bg-down"}`} style={{ width: `${(Math.abs(v) / max) * 100}%` }} />}
                          </div>
                          <div className="w-16 shrink-0 text-right font-mono">{fmtPct(v, 1)}</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
