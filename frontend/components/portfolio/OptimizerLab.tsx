"use client";

import Link from "next/link";
import { useState } from "react";
import { Play, Target } from "lucide-react";
import { Banner, Panel, StatTile, btnPrimary, inputCls } from "@/components/ui/ui";
import { FrontierChart } from "@/components/charts/ChartKit";
import { api, type OptimizeResult } from "@/lib/api";
import { encode } from "@/lib/portfolio-url";
import { dash } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";
const METHODS: Record<string, string> = {
  equal_weight: "Equal weight", min_variance: "Minimum variance", max_sharpe: "Maximum Sharpe (shrunk expected returns)", risk_parity: "Risk parity (equal risk contribution)",
  min_cvar: "Minimum CVaR (95%, historical scenarios)", black_litterman: "Black-Litterman (needs your views)",
};
const n1 = (v: number | null | undefined, d = 1) => (v === null || v === undefined || !Number.isFinite(v) ? dash : v.toFixed(d));

export function OptimizerLab({ funds }: { funds: { scheme_id: number; name: string }[] }) {
  const [f, setF] = useState({ method: "max_sharpe", lookback: 3, shrink: 0.5, minW: 0, maxW: 40, maxFunds: 0, catMax: 0 });
  const [views, setViews] = useState<Record<number, string>>({});
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const [r, setR] = useState<OptimizeResult | null>(null);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const run = async () => {
    setState("running"); setMsg(null); setR(null);
    const limits: Record<string, number> = { min_weight_pct: f.minW, max_weight_pct: f.maxW };
    if (f.maxFunds > 0) limits.max_funds = f.maxFunds;
    if (f.catMax > 0) limits.category_max_pct = f.catMax;
    const vs = Object.entries(views).filter(([, v]) => v.trim() !== "" && Number.isFinite(Number(v))).map(([id, v]) => ({ scheme_id: Number(id), annual_return_pct: Number(v) }));
    try {
      setR(await api.optimize({ scheme_ids: funds.map((x) => x.scheme_id), method: f.method, lookback_years: f.lookback, shrink: f.shrink, limits, ...(f.method === "black_litterman" ? { views: vs } : {}) }));
      setState("done");
    } catch (e) { setMsg((e as Error).message); setState("error"); }
  };
  const field = (label: string, el: React.ReactNode, help?: string) => <label className="flex flex-col gap-1 text-xs" title={help}><span className="text-muted">{label}</span>{el}</label>;
  const num = (k: "lookback" | "shrink" | "minW" | "maxW" | "maxFunds" | "catMax", step = 1) => <input type="number" step={step} value={f[k]} onChange={(e) => set(k, Number(e.target.value))} className={`${inputCls} w-24`} />;
  const useLink = r ? `/portfolio/builder?p=${encode(r.funds.map((x) => ({ scheme_id: x.scheme_id, weight: x.weight_pct })))}` : "#";

  return (
    <>
      <Panel title="Settings" description="Constraints are hard limits; every result lists its assumptions">
        <div className="flex flex-wrap items-end gap-4">
          {field("Method", <select value={f.method} onChange={(e) => set("method", e.target.value)} className={`${inputCls} max-w-[300px]`} aria-label="Method">{Object.entries(METHODS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>)}
          {field("Lookback (years)", num("lookback"), "History used to estimate risk and return")}
          {field("Return shrinkage (0-1)", num("shrink", 0.1), "0 = raw historical averages; 1 = every fund gets the same expected return")}
          {field("Min weight %", num("minW", 0.5))}{field("Max weight %", num("maxW", 1))}
          {field("Max funds (0 = any)", num("maxFunds"))}{field("Max per category % (0 = none)", num("catMax", 5))}
          <button onClick={run} disabled={state === "running" || funds.length < 2} className={btnPrimary}><Play className="h-3.5 w-3.5" /> {state === "running" ? "Optimising…" : "Optimise"}</button>
        </div>
        {f.method === "black_litterman" && (
          <div className="mt-4 border-t border-line pt-3"><p className="mb-2 text-[11px] text-faint">Your views: expected annual return (%) for any fund. Leave blank for no view. At least one is required.</p>
            <div className="grid gap-2 sm:grid-cols-2">{funds.map((x) => <label key={x.scheme_id} className="flex items-center gap-2 text-xs"><span className="min-w-0 flex-1 truncate" title={x.name}>{x.name}</span>
              <input type="number" step="0.5" placeholder="view %" value={views[x.scheme_id] ?? ""} onChange={(e) => setViews({ ...views, [x.scheme_id]: e.target.value })} className={`${inputCls} w-24`} aria-label={`View for ${x.name}`} /></label>)}</div></div>
        )}
        <p className="mt-3 text-[11px] text-faint">Long-only and fully invested. Expected returns are shrunk historical averages, not forecasts.</p>
      </Panel>
      {state === "running" && <Banner tone="accent"><span role="status">Optimising…</span></Banner>}
      {state === "error" && <Banner tone="down">{msg}</Banner>}
      {r && (
        <>
          {r.warnings.length > 0 && <Banner tone="warn"><ul className="space-y-1">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Banner>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Expected return" value={`${n1(r.stats.expected_return)}%`} sub={`equal weight ${n1(r.equal_weight_stats.expected_return)}%`} />
            <StatTile label="Volatility" value={`${n1(r.stats.volatility)}%`} sub={`equal weight ${n1(r.equal_weight_stats.volatility)}%`} />
            <StatTile label="Sharpe (estimated)" value={n1(r.stats.sharpe, 2)} sub={`equal weight ${n1(r.equal_weight_stats.sharpe, 2)}`} />
            <StatTile label="Effective funds" value={n1(r.risk.effective_number_of_funds)} />
            <StatTile label="Diversification ratio" value={n1(r.risk.diversification_ratio, 2)} />
            {r.daily_cvar_95_pct !== undefined && <StatTile label="Daily CVaR 95%" value={`-${n1(r.daily_cvar_95_pct, 2)}%`} sub="average loss in the worst 5% of days" />}
          </div>
          <Panel icon={Target} tone="ai" title={r.method_label} description="Weights" right={<Link href={useLink} className="text-[11px] font-medium text-accent hover:underline">Open in Portfolio Builder →</Link>}>
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={TH}>Category</th><th className={`${TH} text-right`}>Weight</th><th className={`${TH} text-right`}>Risk share</th></tr></thead>
                <tbody className="divide-y divide-line/50">
                  {r.funds.map((x, i) => (
                    <tr key={x.scheme_id} className="transition-colors hover:bg-hover"><td className="max-w-[300px] truncate px-2 py-2 font-medium text-fg" title={x.name}>{x.name}</td><td className="px-2 py-2 text-muted">{x.category}</td>
                      <td className="px-2 py-2 text-right font-semibold">{x.weight_pct < 0.05 ? "0.0" : x.weight_pct.toFixed(1)}%</td><td className="px-2 py-2 text-right">{r.risk.risk_contribution_pct[i].toFixed(1)}%</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          {r.frontier && (
            <Panel title="Efficient frontier" description="Lowest risk for each expected return, within your constraints"
              info="Based on shrunk historical returns and the estimated covariance. Funds far below the frontier are dominated by a mix of the others.">
              <FrontierChart frontier={r.frontier.map((p) => ({ x: p.volatility, y: p.expected_return }))} assets={r.assets.map((a) => ({ x: a.volatility, y: a.expected_return, name: a.name }))}
                selected={{ x: r.stats.volatility, y: r.stats.expected_return }} equal={{ x: r.equal_weight_stats.volatility, y: r.equal_weight_stats.expected_return }} />
            </Panel>
          )}
          <Panel title="Out-of-sample check" description="Fit before the last 12 months, then compare on those 12 months" info="A weighting that only looks good in-sample usually does worse than equal weight afterwards.">
            {!r.holdout.available ? <p className="text-xs text-faint">{r.holdout.reason}</p> : (
              <>
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Portfolio</th><th className={`${TH} text-right`}>Return (annualised)</th><th className={`${TH} text-right`}>Volatility</th><th className={`${TH} text-right`}>Sharpe</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {([["Optimised", r.holdout.optimised], ["Equal weight", r.holdout.equal_weight]] as const).map(([k, v]) => (
                      <tr key={k}><td className="px-2 py-2 font-medium text-fg">{k}</td><td className="px-2 py-2 text-right">{n1(v?.return)}%</td><td className="px-2 py-2 text-right">{n1(v?.volatility)}%</td><td className="px-2 py-2 text-right">{n1(v?.sharpe, 2)}</td></tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-[11px] text-faint">Fitted to {r.holdout.fit_end}; tested {r.holdout.holdout_start} to {r.holdout.holdout_end} ({r.holdout.observations} days). {r.holdout.note}</p>
              </>
            )}
          </Panel>
          <Panel title="Assumptions" description={`Methodology ${r.version}`}>
            <dl className="grid grid-cols-1 gap-x-8 text-xs md:grid-cols-2">
              {[["Estimation window", `${r.assumptions.estimation_window.start} to ${r.assumptions.estimation_window.end} (${r.assumptions.estimation_window.observations} days)`], ["Return shrinkage", String(r.assumptions.mean_return_shrinkage)],
                ["Risk-free rate", `${n1(r.assumptions.risk_free_pct, 2)}% (proxy)`], ["Covariance", `${r.assumptions.covariance}, intensity ${n1(r.assumptions.covariance_shrinkage_intensity, 2)}`], ["Condition number", r.assumptions.condition_number.toExponential(1)]].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-line/40 py-1.5"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{v}</dd></div>
              ))}
            </dl>
          </Panel>
        </>
      )}
    </>
  );
}
