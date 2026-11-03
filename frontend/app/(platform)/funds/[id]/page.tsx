import Link from "next/link";
import { notFound } from "next/navigation";
import { WatchButton } from "@/components/WatchButton";
import { ReportButtons } from "@/components/ReportButtons";
import { Banner, PageHeader, PillTabs, Panel, SegmentedLinks, StatTile, btnPrimary, btnSecondary } from "@/components/ui/ui";
import {
  BenchmarkTable, CalendarPanel, CumulativeChart, DataIssues, DrawdownDetail, FundDrawdownPanel, FundRollingPanel, OVERVIEW_ROWS, Provenance,
  RiskTable, RollingPanel, TAIL_ROWS, TrailingTable, Unavailable,
} from "@/components/analytics/panels";
import { LineChartMulti } from "@/components/charts/ChartKit";
import { ApiError, api, type Analytics, type FundDetail, type QuantScore } from "@/lib/api";
import { Caveats, FactorBar, LabKicker, ScorePill, TH } from "@/components/quant/QuantUi";
import { Gauge, ShieldAlert, Target } from "lucide-react";
import { crore, dash, fmtPrice, num, pct, tone } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "performance", label: "Performance" },
  { key: "nav", label: "NAV Analysis" },
  { key: "risk", label: "Risk & Returns" },
  { key: "holdings", label: "Portfolio Holdings", gated: "Needs AMC portfolio disclosures (not connected)." },
  { key: "allocation", label: "Asset Allocation", gated: "Needs AMC portfolio disclosures (not connected)." },
  { key: "benchmark", label: "Benchmark Analysis" },
  { key: "manager", label: "Fund Manager", gated: "Needs fund manager history (no source identified)." },
  { key: "score", label: "Quant Score" },
  { key: "ai", label: "AI Research" },
] as const;

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

export default async function FundPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: SP }) {
  const { id } = await params;
  const sp = await searchParams;
  const fundId = Number(id);
  if (!Number.isInteger(fundId)) notFound();
  let f: FundDetail;
  try {
    f = await api.fund(fundId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const tabKey = TABS.find((t) => t.key === first(sp.tab))?.key ?? "overview";
  const YEARS = ["1", "3", "5", "max"];
  const years = YEARS.includes(first(sp.years) ?? "") ? (first(sp.years) as string) : "3";
  const needsNav = ["performance", "nav", "risk", "benchmark"].includes(tabKey);
  const qs: QuantScore | null = tabKey === "score" ? await api.quantScore(fundId).catch(() => null) : null;
  const a: Analytics | null = needsNav ? await api.analytics(fundId, years).catch(() => null) : null;
  const tab = TABS.find((t) => t.key === tabKey)!;

  const chip = "rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold tracking-wider";
  return (
    <>
      <div className="flex items-center justify-between">
        <Link href="/screener" className="text-[11px] font-medium text-accent hover:underline">← Screener</Link>
        <Link href={`/comparison?ids=${f.id}`} className={btnSecondary}>Compare</Link>
      </div>
      <PageHeader title={f.name} subtitle={`${f.amc.toUpperCase()} · ${f.category.toUpperCase()}`}
        description={`${f.asset_tier} fund · ${[f.plan_type, f.option_type, f.idcw_mode, f.idcw_freq].filter(Boolean).join(" · ")}`}
        right={
          <div className="flex flex-wrap gap-1.5">
            <WatchButton schemeId={f.id} />
            <ReportButtons kind="fund" params={{ scheme_id: f.id }} />
            {f.is_insurer_fund && <span className={`${chip} border-warn/40 bg-warn/15 text-warn`}>INSURER FUND</span>}
            {f.is_discontinued && <span className={`${chip} border-down/40 bg-down/15 text-down`}>DISCONTINUED</span>}
            {f.quarantined && <span className={`${chip} border-down/40 bg-down/15 text-down`}>QUARANTINED</span>}
          </div>
        } />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
        <StatTile label="Price / NAV" value={fmtPrice(f.price)} />
        <StatTile label="Day change" value={pct(f.change_pct)} valueClass={tone(f.change_pct)} />
        <StatTile label="YTD" value={pct(f.ytd_return)} valueClass={tone(f.ytd_return)} />
        {(["1y", "3y", "5y"] as const).map((h) => {
          const navVal = f.nav_metrics?.[`ret_${h}` as "ret_1y"];
          const src = h === "1y" ? f.return_1y : h === "3y" ? f.return_3y : f.return_5y;
          const useNav = navVal !== null && navVal !== undefined;
          const v = useNav ? navVal : src;
          return <StatTile key={h} label={`${h.toUpperCase()}${h === "1y" ? "" : " p.a."}`} value={pct(v)} valueClass={tone(v)}
            sub={useNav ? `from NAV, to ${f.nav_metrics!.as_of}` : "as reported; may be dated"} />;
        })}
        <StatTile label="Net assets" value={crore(f.net_assets)} />
      </div>

      <PillTabs active={tabKey} items={TABS.map((t) => ({ key: t.key, label: t.label, href: `/funds/${f.id}?tab=${t.key}`, muted: "gated" in t }))} />

      {"gated" in tab && <Banner tone="accent"><span><strong>{tab.label}</strong> is not available yet. {tab.gated}</span></Banner>}
      {tabKey === "ai" && (
        <Panel title="AI Research" description="Ask the research assistant about this fund. Answers come from the same verified calculations as this page, with the source and date of every figure.">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Link href="/assistant" className={btnPrimary}>Open the assistant</Link>
            <span className="text-muted">Try: “How risky is {f.name}?” (sign-in required)</span>
          </div>
        </Panel>
      )}
      {tabKey === "overview" && <Overview f={f} />}
      {needsNav && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] text-faint">{tabKey === "nav" ? "Chart period" : "Chart period (metric tables always show 1Y, 3Y and 5Y windows)"}</p>
          <SegmentedLinks label="Period" active={years} items={YEARS.map((y) => ({ key: y, label: y === "max" ? "Max" : `${y}Y`, href: `/funds/${f.id}?tab=${tabKey}&years=${y}` }))} />
        </div>
      )}
      {needsNav && a === null && <Banner tone="down">Could not load NAV analytics. The data service may be unavailable.</Banner>}
      {needsNav && a && !a.available && <Unavailable a={a} />}
      {needsNav && a?.available && <DataIssues a={a} />}
      {tabKey === "performance" && <Performance f={f} a={a} />}
      {tabKey === "nav" && <NavAnalysis f={f} a={a} />}
      {tabKey === "score" && qs === null && <Banner tone="down">Could not load the score. The data service may be unavailable.</Banner>}
      {tabKey === "score" && qs && !qs.available && <Banner tone="accent"><span><strong>No Quant Score.</strong> {qs.reason}</span></Banner>}
      {tabKey === "score" && qs?.available && <ScoreTab q={qs} />}
      {tabKey === "risk" && a?.available && <RiskReturns a={a} />}
      {tabKey === "benchmark" && a?.available && <BenchmarkTab a={a} />}
      {needsNav && a?.available && <Provenance a={a} />}

      <p className="text-[11px] text-faint">Single snapshot (ingestion run {f.ingestion_run_id}; snapshot date unknown). Figures are as reported in the source data.</p>
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line/40 py-1">
      <dt className="text-muted">{k}</dt><dd>{v}</dd>
    </div>
  );
}

function Overview({ f }: { f: FundDetail }) {
  return (
    <>
      <Panel title="Fund profile">
        <dl className="grid grid-cols-1 gap-x-8 text-xs md:grid-cols-2 xl:grid-cols-3">
          <Row k="AMC" v={f.amc} /><Row k="Category" v={f.category} /><Row k="Asset tier" v={f.asset_tier} />
          <Row k="Plan" v={f.plan_type} /><Row k="Option" v={f.option_type} />
          <Row k="IDCW mode / frequency" v={[f.idcw_mode, f.idcw_freq].filter(Boolean).join(" / ") || dash} />
          <Row k="Min. investment" v={f.initial_investment === null ? dash : `₹${num(f.initial_investment, 0)}`} />
          <Row k="Share classes in family" v={f.n_share_classes?.toString() ?? dash} />
          <Row k="Ticker" v={f.external_ids.yahoo_symbol ?? dash} />
        </dl>
      </Panel>
      {f.siblings.length > 0 && (
        <Panel title={`Other share classes (${f.siblings.length})`} description={f.base_fund ?? undefined}>
          <ul className="space-y-1 text-xs">
            {f.siblings.map((s) => (
              <li key={s.id}><Link href={`/funds/${s.id}`} className="hover:text-accent">{s.name}</Link>
                <span className="text-muted"> — {s.plan_type} · {s.option_type}{s.idcw_freq ? ` · ${s.idcw_freq}` : ""}</span></li>
            ))}
          </ul>
        </Panel>
      )}
      {f.quality_issues.length > 0 && (
        <Panel title="Data quality notes">
          <ul className="space-y-1 text-xs text-muted">
            {f.quality_issues.map((i, n) => <li key={n}>{i.severity}: {i.rule} {JSON.stringify(i.detail)}</li>)}
          </ul>
        </Panel>
      )}
    </>
  );
}

const pctFeat = (f: FundDetail, k: string) => (f.features[k] == null ? null : (f.features[k] as number) * 100);

function PctBar({ v }: { v: number | null }) {
  if (v === null) return <span className="text-muted">{dash}</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 rounded bg-raised"><div className="h-2 rounded bg-accent" style={{ width: `${Math.max(2, v)}%` }} /></div>
      <span className="w-8 text-right">{v.toFixed(0)}</span>
    </div>
  );
}

function Performance({ f, a }: { f: FundDetail; a: Analytics | null }) {
  return (
    <>
      {a?.available && (
        <>
          <CumulativeChart a={a} />
          <Panel icon={Gauge} title="Trailing returns (from NAV)" description="Computed from official daily NAVs ending on the latest NAV date; 3 years and longer are annualised">
            <TrailingTable funds={[a]} />
          </Panel>
          <CalendarPanel funds={[a]} />
          <RollingPanel funds={[a]} />
        </>
      )}
      <SourceReturns f={f} />
    </>
  );
}

function SourceReturns({ f }: { f: FundDetail }) {
  const rows: [string, number | null, string, string][] = [
    ["YTD", f.ytd_return, "ytd_return_cat_pct", "ytd_return_cat_z"],
    ["3 months", f.return_3m, "3mo_return_cat_pct", "3mo_return_cat_z"],
    ["1 year", f.return_1y, "1year_return_cat_pct", "1year_return_cat_z"],
    ["3 years", f.return_3y, "3year_return_cat_pct", "3year_return_cat_z"],
    ["5 years", f.return_5y, "5year_return_cat_pct", "5year_return_cat_z"],
  ];
  return (
    <Panel title="Reported returns vs category peers" description="As reported in the source data. YTD and 3M are current; 1Y, 3Y and 5Y are measured to earlier, fund-specific dates (see Data Coverage). Prefer the NAV-derived figures above.">
      <table className="w-full text-xs">
        <thead className="text-left text-muted"><tr>
          <th className="py-1 font-medium">Period</th><th className="text-right font-medium">Return</th>
          <th className="px-4 font-medium">Category percentile</th><th className="text-right font-medium">Z-score</th></tr></thead>
        <tbody>
          {rows.map(([label, ret, pk, zk]) => (
            <tr key={label} className="border-t border-line/50">
              <td className="py-1.5">{label}</td>
              <td className={`text-right ${tone(ret)}`}>{pct(ret)}</td>
              <td className="px-4"><PctBar v={pctFeat(f, pk)} /></td>
              <td className="text-right">{f.features[zk] == null ? dash : (f.features[zk] as number).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-[11px] text-faint">NAV-derived trailing, rolling and calendar-year returns are shown above for funds with a confirmed link to official NAV records.</p>
    </Panel>
  );
}

function NavAnalysis({ f, a }: { f: FundDetail; a: Analytics | null }) {
  const nc = a?.charts?.nav_chart;
  const lo = f.low_52w, hi = f.high_52w, p = f.price;
  const pos = lo !== null && hi !== null && p !== null && hi > lo ? Math.min(100, Math.max(0, ((p - lo) / (hi - lo)) * 100)) : null;
  const vs = (avg: number | null) => (avg && p ? (p / avg - 1) * 100 : null);
  const above = (avg: number | null) => (avg && p ? (p > avg ? "Above" : "Below") : dash);
  const cross = f.avg_50d && f.avg_200d ? (f.avg_50d > f.avg_200d ? "50-day above 200-day average (uptrend signal)" : "50-day below 200-day average (downtrend signal)") : dash;
  return (
    <>
      {nc && (
        <Panel title="NAV with 50 and 200 observation moving averages" description="Official daily NAV; averages are over the last 50 and 200 observations"
          info="Trend indicators on a NAV series; they are not a substitute for risk analytics.">
          <LineChartMulti digits={2} series={[
            { key: "nav", name: "NAV", data: nc.nav }, { key: "d50", name: "50-day average", data: nc.dma_50, dashed: true },
            { key: "d200", name: "200-day average", data: nc.dma_200, dashed: true },
          ]} />
        </Panel>
      )}
      <Panel title="52-week range">
        {pos === null ? <p className="text-xs text-muted">Range not available (flat or missing).</p> : (
          <div>
            <div className="relative h-3 rounded bg-raised">
              <div className="absolute top-0 h-3 w-1 rounded bg-accent" style={{ left: `calc(${pos}% - 2px)` }} />
            </div>
            <div className="mt-1 flex justify-between text-xs text-muted"><span>Low {num(lo)}</span><span>Price {num(p)} · {pos.toFixed(0)}% of range</span><span>High {num(hi)}</span></div>
          </div>
        )}
      </Panel>
      <Panel title="Trend vs moving averages" description="Averages of the reported price series. Trend indicators are not a substitute for risk analytics.">
        <dl className="grid grid-cols-1 gap-x-8 text-xs md:grid-cols-2">
          <Row k="50-day average" v={num(f.avg_50d)} /><Row k="Price vs 50-day" v={`${above(f.avg_50d)} (${pct(vs(f.avg_50d))})`} />
          <Row k="200-day average" v={num(f.avg_200d)} /><Row k="Price vs 200-day" v={`${above(f.avg_200d)} (${pct(vs(f.avg_200d))})`} />
          <Row k="52-week price change" v={pct(f.price_change_52w_pct)} /><Row k="Crossover state" v={cross} />
        </dl>
        <p className="mt-3 text-[11px] text-faint">The NAV chart needs historical NAV (Phase 3).</p>
      </Panel>
    </>
  );
}


function RiskReturns({ a }: { a: Analytics }) {
  const wins = a.windows ?? [];
  const sel = wins.find((w) => w.years === (a.chart_years ?? 3)) ?? wins.find((w) => w.years === 3) ?? wins[0];
  return (
    <>
      <Panel icon={ShieldAlert} tone="warn" title="Risk and return by window" description="All metrics use daily NAV returns; windows end on the latest NAV date"
        info="Sharpe and Sortino use a risk-free proxy built from overnight and liquid funds. Ratios are withheld when volatility is too low for them to be meaningful.">
        <RiskTable columns={wins.map((w) => ({ label: `${w.years}Y`, block: w }))} rows={[...OVERVIEW_ROWS, ...TAIL_ROWS]} />
      </Panel>
      <FundDrawdownPanel a={a} />
      <Panel icon={ShieldAlert} tone="down" title="Largest drawdown" description={`Within the ${sel?.years}-year window`}>
        <DrawdownDetail block={sel} />
      </Panel>
      <FundRollingPanel a={a} />
    </>
  );
}

function BenchmarkTab({ a }: { a: Analytics }) {
  const wins = a.windows ?? [];
  return (
    <>
      {!a.charts?.cumulative?.category_average && <Banner tone="warn">{a.benchmark_label ?? "Category average unavailable."}</Banner>}
      <CumulativeChart a={a} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {wins.map((w) => (
          <Panel key={w.years} icon={Target} title={`${w.years}-year vs category average`} description={w.available ? `${w.window_start} to ${w.window_end}` : "Not available"}>
            {w.available ? <BenchmarkTable block={w} /> : <p className="text-xs text-faint">{w.reason}</p>}
          </Panel>
        ))}
      </div>
      <p className="text-[11px] text-faint">No licensed index data is connected. The benchmark is the equal-weighted average of comparable funds that exist today, so it carries survivorship bias and is shown as a peer comparison, not an index comparison.</p>
    </>
  );
}


function ScoreTab({ q }: { q: QuantScore }) {
  const byFactor = (k: string) => q.metrics?.filter((m) => m.factor === k) ?? [];
  return (
    <>
      <LabKicker>{q.methodology_version}</LabKicker>
      {!q.scored && <Banner tone="warn">{q.not_scored_reason}</Banner>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="QuantSynthica score" value={q.composite == null ? dash : q.composite.toFixed(1)} sub="0-100 within peer group" />
        <StatTile label="Rank in peer group" value={q.rank_in_group == null ? dash : `${q.rank_in_group} / ${q.peers}`} sub={q.peer_group} />
        <StatTile label="Data completeness" value={q.coverage == null ? dash : `${Math.round(q.coverage * 100)}%`} sub="of total factor weight available" />
        <StatTile label="As of" value={q.as_of ?? dash} sub="NAV information up to this date" />
      </div>
      <Panel title="Factor breakdown" description="Weights are research hypotheses; missing factors are renormalised, never zero-filled"
        info="Contribution = renormalised weight x factor score. The contributions add up to the composite.">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line"><th className={TH}>Factor</th><th className={`${TH} text-right`}>Weight</th><th className={TH}>Score</th><th className={`${TH} text-right`}>Contribution</th></tr></thead>
            <tbody className="divide-y divide-line/50">
              {q.factors?.map((f) => (
                <tr key={f.key} className="transition-colors hover:bg-hover">
                  <td className="px-2 py-2 font-medium text-fg">{f.label}</td>
                  <td className="px-2 py-2 text-right">{f.weight}%</td>
                  <td className="px-2 py-2">{f.score === null ? <span className="text-faint" title="Not available">{dash} not available</span> : <FactorBar v={f.score} />}</td>
                  <td className="px-2 py-2 text-right">{f.contribution === null || f.score === null ? dash : f.contribution.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Underlying metrics" description="Raw value, percentile within peers (higher is better) and z-score after winsorising">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line"><th className={TH}>Factor</th><th className={TH}>Metric</th><th className={`${TH} text-right`}>Value</th><th className={`${TH} text-right`}>Percentile</th><th className={`${TH} text-right`}>Z-score</th></tr></thead>
            <tbody className="divide-y divide-line/50">
              {q.factors?.filter((f) => byFactor(f.key).length).flatMap((f) => byFactor(f.key).map((m, i) => (
                <tr key={m.key} className="transition-colors hover:bg-hover">
                  <td className="px-2 py-1.5 text-muted">{i === 0 ? f.label : ""}</td>
                  <td className="px-2 py-1.5 text-fg" title={m.higher_is_better ? "Higher is better" : "Lower is better"}>{m.label}</td>
                  <td className="px-2 py-1.5 text-right">{m.raw === null ? dash : m.raw.toFixed(2)}</td>
                  <td className="px-2 py-1.5 text-right"><ScorePill v={m.percentile} digits={0} /></td>
                  <td className="px-2 py-1.5 text-right">{m.z === null ? dash : m.z.toFixed(2)}</td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Caveats items={[q.caveat ?? "", "Funds are compared only with peers in the same category and plan; scores are not comparable across groups."]} />
    </>
  );
}
