import Link from "next/link";
import { GitCompareArrows } from "lucide-react";
import { Banner, EmptyState, Panel, PillTabs, SegmentedLinks } from "@/components/ui/ui";
import { FundPicker } from "@/components/funds/FundPicker";
import { Unavailable } from "@/components/analytics/panels";
import { ApiError, api, type CompareAnalytics } from "@/lib/api";

export const MAX = 5;
export type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

export async function readParams(sp: Awaited<SP>, tabs: string[]) {
  const raw = first(sp.ids) ?? "";
  const ids = [...new Set(raw.split(",").map(Number).filter((x) => Number.isInteger(x) && x > 0))].slice(0, MAX);
  const years = ["1", "3", "5", "max"].includes(first(sp.years) ?? "") ? (first(sp.years) as string) : "3";
  const tab = tabs.includes(first(sp.tab) ?? "") ? (first(sp.tab) as string) : tabs[0];
  return { ids, years, tab };
}

export async function load(ids: number[], years: string): Promise<{ data: CompareAnalytics | null; error: string | null }> {
  if (!ids.length) return { data: null, error: null };
  try {
    return { data: await api.analyticsCompare(ids, years), error: null };
  } catch (e) {
    return { data: null, error: e instanceof ApiError && e.status === 404 ? "One or more funds were not found." : "Could not load analytics. The data service may be unavailable." };
  }
}

/** Shared shell: fund picker, period control, tab bar and per-fund availability notices. */
export function Shell({ base, ids, years, tab, tabs, data, error, children }: {
  base: string; ids: number[]; years: string; tab: string; tabs: { key: string; label: string }[];
  data: CompareAnalytics | null; error: string | null; children: React.ReactNode;
}) {
  const href = (over: { tab?: string; years?: string }) => `${base}?ids=${ids.join(",")}&tab=${over.tab ?? tab}&years=${over.years ?? years}`;
  return (
    <>
      <FundPicker ids={ids} max={MAX} basePath={base} extra={`&tab=${tab}&years=${years}`} />
      {error && <Banner tone="down">{error}</Banner>}
      {!ids.length && (
        <Panel><EmptyState icon={GitCompareArrows} title="No funds selected" hint="Search above to add up to five funds. Only Growth schemes with a confirmed link to official NAV records can be analysed." /></Panel>
      )}
      {data && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PillTabs active={tab} items={tabs.map((t) => ({ ...t, href: href({ tab: t.key }) }))} />
            <SegmentedLinks label="Period" active={years} items={["1", "3", "5", "max"].map((y) => ({ key: y, label: y === "max" ? "Max" : `${y}Y`, href: href({ years: y }) }))} />
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            {data.funds.map((f, i) => (
              <span key={f.scheme_id} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-0.5">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: ["#2563EB", "#16A34A", "#D97706", "#7C3AED", "#DC2626"][i] }} />
                <Link href={`/funds/${f.scheme_id}`} className="text-fg hover:text-accent">{f.name}</Link>
                <Link href={`${base}?ids=${ids.filter((x) => x !== f.scheme_id).join(",")}&tab=${tab}&years=${years}`} className="text-muted hover:text-down" aria-label={`Remove ${f.name}`}>remove</Link>
              </span>
            ))}
          </div>
          {data.funds.filter((f) => !f.available).map((f) => <Unavailable key={f.scheme_id} a={f} />)}
          {children}
        </>
      )}
    </>
  );
}
