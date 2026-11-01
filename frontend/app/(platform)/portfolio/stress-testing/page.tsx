import { Flame, ShieldAlert, Zap } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { PortfolioPicker } from "@/components/portfolio/PortfolioPicker";
import { loadPicks, type SP } from "@/components/portfolio/server";
import { ApiError, api, type StressResult } from "@/lib/api";
import { dash, fmtPct, tone } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

export default async function StressPage({ searchParams }: { searchParams: SP }) {
  const { picks, holdings } = await loadPicks(await searchParams);
  let r: StressResult | null = null;
  let error: string | null = null;
  if (holdings.length) {
    try { r = await api.stress(holdings); } catch (e) { error = e instanceof ApiError ? e.message : "Could not run the stress test."; }
  }
  return (
    <>
      <PageHeader title="Stress" accent="Testing" subtitle="PORTFOLIOS"
        description="How the portfolio would have done in the worst equity-market falls in the data, and what a market shock could do to it. Historical episodes are real; hypothetical shocks are illustrations." />
      <PortfolioPicker initial={picks} basePath="/portfolio/stress-testing" />
      {error && <Banner tone="down">{error}</Banner>}
      {!holdings.length && <Panel><EmptyState icon={Flame} title="No portfolio selected" hint="Choose funds and weights above." /></Panel>}
      {r && (
        <>
          <Banner tone="accent"><span>{r.market_proxy}.</span></Banner>
          <Panel icon={Flame} tone="down" title="Worst historical episodes" description={`Peak-to-trough falls of the market proxy, ${r.history.start} to ${r.history.end}`}
            info="Episodes are detected from the proxy itself. A fund that did not exist during an episode shows a dash: nothing is estimated for it.">
            {r.historical_episodes.length === 0 ? <EmptyState title="No significant falls in the common history" hint="Select funds with longer histories." /> : (
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Episode</th><th className={`${TH} text-right`}>Days</th><th className={`${TH} text-right`}>Market proxy</th><th className={`${TH} text-right`}>Your portfolio</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {r.historical_episodes.map((e) => (
                      <tr key={e.peak} className="align-top transition-colors hover:bg-hover">
                        <td className="px-2 py-2 font-mono">{e.peak} to {e.trough}</td><td className="px-2 py-2 text-right">{e.days}</td>
                        <td className="px-2 py-2 text-right font-semibold text-down">{fmtPct(e.fall_pct, 1)}</td>
                        <td className={`px-2 py-2 text-right font-semibold ${tone(e.portfolio_change_pct)}`} title={e.reason ?? undefined}>{e.available ? fmtPct(e.portfolio_change_pct, 1) : `${dash} not available`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {r.historical_episodes.map((e) => e.available && (
                  <details key={`d${e.peak}`} className="mt-3 text-xs"><summary className="cursor-pointer text-muted hover:text-fg">Fund by fund: {e.peak} to {e.trough}</summary>
                    <ul className="mt-1 divide-y divide-line/50">{e.funds.map((f) => <li key={f.scheme_id} className="flex justify-between py-1"><span className="truncate pr-3">{f.name}</span><span className={`font-mono ${tone(f.change_pct)}`}>{f.change_pct === null ? dash : fmtPct(f.change_pct, 1)}</span></li>)}</ul></details>
                ))}
              </div>
            )}
          </Panel>
          <Panel icon={Zap} tone="warn" title="Hypothetical market shocks" description="Illustration: the portfolio's historical beta applied to a market fall"
            info="Real losses in a crisis tend to be larger than beta implies because correlations rise.">
            {!r.hypothetical.available ? <p className="text-xs text-faint">{r.hypothetical.reason}</p> : (
              <>
                <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-line bg-raised p-3 text-xs"><div className="text-muted">Beta to the market proxy</div><div className="font-mono text-lg font-bold text-strong">{r.hypothetical.beta?.toFixed(2)}</div></div>
                  <div className="rounded-lg border border-line bg-raised p-3 text-xs"><div className="text-muted">R-squared</div><div className="font-mono text-lg font-bold text-strong">{r.hypothetical.r_squared?.toFixed(2)}</div></div>
                </div>
                <table className="w-full border-collapse text-left text-xs"><thead><tr className="border-b border-line"><th className={TH}>If the market falls</th><th className={`${TH} text-right`}>Portfolio change (approx.)</th></tr></thead>
                  <tbody className="divide-y divide-line/50">{r.hypothetical.scenarios?.map((s) => <tr key={s.market_shock_pct}><td className="px-2 py-2">{s.market_shock_pct}%</td><td className="px-2 py-2 text-right font-semibold text-down">{fmtPct(s.portfolio_change_pct, 1)}</td></tr>)}</tbody></table>
              </>
            )}
          </Panel>
          <Panel icon={ShieldAlert} title="Read this carefully"><ul className="space-y-1 text-[11px] text-faint">{r.notes.map((n) => <li key={n}>• {n}</li>)}</ul></Panel>
        </>
      )}
    </>
  );
}
