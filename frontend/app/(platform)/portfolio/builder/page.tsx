import { Layers, PieChart, Grid3x3, ShieldAlert } from "lucide-react";
import { ReportButtons } from "@/components/ReportButtons";
import { Banner, EmptyState, PageHeader, Panel, SegmentedLinks, StatTile } from "@/components/ui/ui";
import { PortfolioPicker } from "@/components/portfolio/PortfolioPicker";
import { encode } from "@/lib/portfolio-url";
import { loadPicks, type SP } from "@/components/portfolio/server";
import { CumulativeChart, DataIssues, FundDrawdownPanel, OVERVIEW_ROWS, Provenance, RiskTable, TAIL_ROWS } from "@/components/analytics/panels";
import { BarRow } from "@/components/ui/ui";
import { ApiError, api, type PortfolioAnalysis } from "@/lib/api";
import { dash, fmtPct, tone } from "@/lib/format";

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

export default async function BuilderPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const { picks, holdings, dropped } = await loadPicks(sp);
  const years = ["1", "3", "5", "max"].includes(first(sp.years) ?? "") ? (first(sp.years) as string) : "3";
  let a: PortfolioAnalysis | null = null;
  let error: string | null = null;
  if (holdings.length) {
    try { a = await api.analyzePortfolio(holdings, years); } catch (e) { error = e instanceof ApiError ? e.message : "Could not analyse the portfolio."; }
  }
  const p = encode(holdings);
  const w3 = a?.analytics.windows?.find((w) => w.years === 3);

  return (
    <>
      <PageHeader title="Portfolio" accent="Builder" subtitle="PORTFOLIOS"
        description="Combine funds, set weights and see how the mix would have behaved: returns, risk, drawdowns, correlation and where the risk really comes from."
        right={holdings.length ? <ReportButtons kind="portfolio" params={{ holdings }} /> : undefined} />
      <PortfolioPicker initial={picks} basePath="/portfolio/builder" note="History starts on the first date every selected fund has a NAV, and the portfolio is rebalanced to your weights each month." />
      {dropped > 0 && <Banner tone="warn">{dropped} fund{dropped > 1 ? "s" : ""} in the link cannot be used and {dropped > 1 ? "were" : "was"} left out.</Banner>}
      {error && <Banner tone="down">{error}</Banner>}
      {!holdings.length && <Panel><EmptyState icon={Layers} title="No funds selected" hint="Search above to add funds, then choose weights." /></Panel>}
      {a && (
        <>
          <DataIssues a={a.analytics} />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Return (3Y CAGR)" value={fmtPct(w3?.cagr?.value)} valueClass={tone(w3?.cagr?.value)} sub={`history ${a.history.start} to ${a.history.end}`} />
            <StatTile label="Volatility (3Y)" value={fmtPct(w3?.volatility?.value, 1, false)} />
            <StatTile label="Sharpe (3Y)" value={w3?.sharpe_ratio?.value == null ? dash : w3.sharpe_ratio.value.toFixed(2)} sub="risk-free proxy" />
            <StatTile label="Max drawdown (3Y)" value={fmtPct(w3?.max_drawdown?.value, 1)} valueClass="text-down" />
            <StatTile label="Effective funds" value={a.risk ? a.risk.effective_number_of_funds.toFixed(1) : dash} sub={`of ${a.funds.length} held`} />
            <StatTile label="Diversification ratio" value={a.risk?.diversification_ratio == null ? dash : a.risk.diversification_ratio.toFixed(2)} sub="1 = no diversification benefit" />
          </div>
          <div className="flex justify-end"><SegmentedLinks label="Period" active={years} items={["1", "3", "5", "max"].map((y) => ({ key: y, label: y === "max" ? "Max" : `${y}Y`, href: `/portfolio/builder?p=${p}&years=${y}` }))} /></div>
          <CumulativeChart a={{ ...a.analytics, name: "Your portfolio", charts: a.charts } as never} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel icon={PieChart} title="Allocation" description="By category, asset tier and plan">
              {([["Category", a.allocation.by_category], ["Asset tier", a.allocation.by_tier], ["Plan", a.allocation.by_plan]] as const).map(([label, rows]) => (
                <div key={label} className="mb-3"><div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">{label}</div>
                  {rows.map((r) => <BarRow key={r.name} label={r.name} value={r.weight_pct} max={100} text={`${r.weight_pct.toFixed(1)}%`} />)}</div>
              ))}
            </Panel>
            <Panel icon={ShieldAlert} tone="warn" title="Where the risk comes from" description="Share of portfolio variance contributed by each fund"
              info="A fund with 20% of the money but 40% of the risk contribution is a concentrated bet. Risk parity would equalise these shares.">
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>Weight</th><th className={`${TH} text-right`}>Risk share</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {a.funds.map((f, i) => (
                      <tr key={f.scheme_id} className="transition-colors hover:bg-hover"><td className="max-w-[260px] truncate px-2 py-2 font-medium text-fg" title={f.name}>{f.name}</td>
                        <td className="px-2 py-2 text-right">{f.weight_pct.toFixed(1)}%</td>
                        <td className="px-2 py-2 text-right font-semibold">{a.risk ? `${a.risk.risk_contribution_pct[i].toFixed(1)}%` : dash}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {a.risk && <p className="mt-2 text-[11px] text-faint">Estimated on {a.risk.window.observations} daily observations, {a.risk.window.start} to {a.risk.window.end}.</p>}
            </Panel>
          </div>
          {a.risk && a.funds.length > 1 && (
            <Panel icon={Grid3x3} title="Correlation of daily returns" description="Last 3 years; the closer to 1, the less diversification between two funds">
              <div className="w-full overflow-x-auto">
                <table className="border-collapse text-xs">
                  <thead><tr><th />{a.funds.map((f) => <th key={f.scheme_id} className="max-w-[90px] px-1 py-1 text-[10px] font-medium text-muted"><span className="block truncate" title={f.name}>{f.name}</span></th>)}</tr></thead>
                  <tbody>{a.risk.correlation.matrix.map((row, i) => (
                    <tr key={i}><th className="max-w-[160px] truncate pr-2 text-left text-[11px] font-medium text-muted">{a.funds[i].name}</th>
                      {row.map((v, j) => <td key={j} className="px-2 py-1.5 text-center font-mono text-[11px] text-strong" style={{ background: `rgba(59,130,246,${(Math.max(0, v) * 0.6).toFixed(2)})` }}>{v.toFixed(2)}</td>)}</tr>
                  ))}</tbody>
                </table>
              </div>
            </Panel>
          )}
          <Panel icon={ShieldAlert} tone="warn" title="Risk and return by window" description="Portfolio rebalanced monthly to your weights; Sharpe and Sortino use the risk-free proxy">
            <RiskTable columns={(a.analytics.windows ?? []).map((w) => ({ label: `${w.years}Y`, block: w }))} rows={[...OVERVIEW_ROWS, ...TAIL_ROWS]} />
          </Panel>
          <FundDrawdownPanel a={{ ...a.analytics, name: "Your portfolio", charts: a.charts } as never} />
          {a.warnings.length > 0 && <Banner tone="warn"><ul className="space-y-1">{a.warnings.map((x) => <li key={x}>{x}</li>)}</ul></Banner>}
          <Provenance a={a.analytics} />
        </>
      )}
    </>
  );
}
