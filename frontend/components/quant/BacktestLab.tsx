"use client";

import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { Banner, Panel, StatTile, btnPrimary, inputCls } from "@/components/ui/ui";
import { LineChartMulti } from "@/components/charts/ChartKit";
import { TH } from "@/components/quant/QuantUi";
import { api, type BacktestRequest, type BacktestResult, type BacktestSeg } from "@/lib/api";
import { dash, fmtInt, fmtPct, tone } from "@/lib/format";

const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? dash : v.toFixed(d));

function SegRow({ label, s, b }: { label: string; s: BacktestSeg | undefined; b: BacktestSeg | undefined }) {
  const cell = (x: BacktestSeg | undefined, k: "cagr" | "volatility" | "sharpe" | "max_drawdown", pct = false) => (!x?.available ? dash : pct ? fmtPct(x[k] as number | null, 1) : num(x[k] as number | null));
  return (
    <tr className="transition-colors hover:bg-hover">
      <td className="px-2 py-2 font-medium text-fg">{label}<span className="block text-[10px] font-normal text-faint">{s?.start} to {s?.end}</span></td>
      <td className={`px-2 py-2 text-right font-semibold ${tone(s?.cagr)}`}>{cell(s, "cagr", true)}</td><td className="px-2 py-2 text-right">{cell(b, "cagr", true)}</td>
      <td className="px-2 py-2 text-right">{cell(s, "volatility", true)}</td><td className="px-2 py-2 text-right">{cell(s, "sharpe")}</td><td className="px-2 py-2 text-right">{cell(b, "sharpe")}</td>
      <td className="px-2 py-2 text-right">{cell(s, "max_drawdown", true)}</td><td className="px-2 py-2 text-right">{cell(b, "max_drawdown", true)}</td>
    </tr>
  );
}

export function BacktestLab({ strategies }: { strategies: Record<string, string> }) {
  const [form, setForm] = useState({ strategy: "multi_factor", tier: "Equity", plan: "Direct", top_n: 10, rebalance_months: 3, cost_pct: 0.1, exit_load_pct: 1, delay_days: 3, start: "", end: "", oos_start: "" });
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  const poll = (id: number, started: number) => {
    timer.current = setTimeout(async () => {
      try {
        const j = await api.job(id);
        if (j.status === "succeeded") { setResult(await api.backtest(id)); setState("done"); return; }
        if (j.status === "failed") { setMessage(j.error ?? "The backtest failed."); setState("error"); return; }
        if (Date.now() - started > 5 * 60_000) { setMessage("Still running after 5 minutes; check again later."); setState("error"); return; }
        poll(id, started);
      } catch (e) { setMessage((e as Error).message); setState("error"); }
    }, 1500);
  };

  const run = async () => {
    setState("running"); setMessage(null); setResult(null);
    const req: BacktestRequest = {
      strategy: form.strategy, top_n: form.top_n, rebalance_months: form.rebalance_months, cost_pct: form.cost_pct, exit_load_pct: form.exit_load_pct, delay_days: form.delay_days,
      universe: { tier: form.tier, plan: form.plan }, ...(form.start ? { start: form.start } : {}), ...(form.end ? { end: form.end } : {}), ...(form.oos_start ? { oos_start: form.oos_start } : {}),
    };
    try { const r = await api.submitBacktest(req); poll(r.id, Date.now()); } catch (e) { setMessage((e as Error).message); setState("error"); }
  };

  const field = (label: string, el: React.ReactNode) => <label className="flex flex-col gap-1 text-xs"><span className="text-muted">{label}</span>{el}</label>;
  const numIn = (k: "top_n" | "rebalance_months" | "cost_pct" | "exit_load_pct" | "delay_days", step = 1) => (
    <input type="number" step={step} value={form[k]} onChange={(e) => set(k, Number(e.target.value))} className={`${inputCls} w-24`} />
  );
  const r = result;

  return (
    <>
      <Panel title="Configure" description="Strategies pick funds using only information available on each rebalance date">
        <div className="flex flex-wrap items-end gap-4">
          {field("Strategy", <select value={form.strategy} onChange={(e) => set("strategy", e.target.value)} className={`${inputCls} max-w-[300px]`} aria-label="Strategy">{Object.entries(strategies).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>)}
          {field("Universe tier", <select value={form.tier} onChange={(e) => set("tier", e.target.value)} className={inputCls} aria-label="Tier">{["Equity", "Debt", "Hybrid", "Other"].map((t) => <option key={t}>{t}</option>)}</select>)}
          {field("Plan", <select value={form.plan} onChange={(e) => set("plan", e.target.value)} className={inputCls} aria-label="Plan">{["Direct", "Regular"].map((t) => <option key={t}>{t}</option>)}</select>)}
          {field("Funds held", numIn("top_n"))}
          {field("Rebalance (months)", <select value={form.rebalance_months} onChange={(e) => set("rebalance_months", Number(e.target.value))} className={inputCls} aria-label="Rebalance months">{[1, 3, 6, 12].map((n) => <option key={n}>{n}</option>)}</select>)}
          {field("Transaction cost %", numIn("cost_pct", 0.05))}
          {field("Exit load % (<1y)", numIn("exit_load_pct", 0.25))}
          {field("Execution delay (days)", numIn("delay_days"))}
          {field("Start", <input type="date" value={form.start} onChange={(e) => set("start", e.target.value)} className={inputCls} />)}
          {field("End", <input type="date" value={form.end} onChange={(e) => set("end", e.target.value)} className={inputCls} />)}
          {field("Out-of-sample from", <input type="date" value={form.oos_start} onChange={(e) => set("oos_start", e.target.value)} className={inputCls} />)}
          <button onClick={run} disabled={state === "running"} className={btnPrimary}><Play className="h-3.5 w-3.5" /> {state === "running" ? "Running…" : "Run backtest"}</button>
        </div>
        <p className="mt-3 text-[11px] text-faint">Costs and loads are assumptions you can change. Taxes are not modelled. The benchmark is the equal-weighted eligible universe on the same dates with no costs.</p>
      </Panel>

      {state === "running" && <Banner tone="accent"><span role="status">Running in the background… this takes a few seconds to a minute.</span></Banner>}
      {state === "error" && <Banner tone="down">{message}</Banner>}
      {r && !r.available && <Banner tone="warn">{r.reason}</Banner>}
      {r?.available && (
        <>
          <Banner tone="warn"><ul className="space-y-1">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Banner>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Strategy CAGR" value={fmtPct(r.full?.strategy.cagr, 1)} valueClass={tone(r.full?.strategy.cagr)} sub={`${r.period?.start} to ${r.period?.end}`} />
            <StatTile label="Benchmark CAGR" value={fmtPct(r.full?.benchmark.cagr, 1)} sub="equal-weight eligible funds" />
            <StatTile label="Difference" value={r.excess?.cagr_difference_pp == null ? dash : `${r.excess.cagr_difference_pp > 0 ? "+" : ""}${r.excess.cagr_difference_pp.toFixed(1)} pp`} valueClass={tone(r.excess?.cagr_difference_pp)} sub="per year, after costs" />
            <StatTile label="Months beating benchmark" value={r.excess ? `${r.excess.win_rate_pct.toFixed(0)}%` : dash} sub={`${r.excess?.months} months`} />
            <StatTile label="t-statistic" value={num(r.excess?.t_stat)} sub="rough; monthly excess" />
            <StatTile label="Annual turnover" value={r.costs ? `${r.costs.avg_annual_turnover_pct.toFixed(0)}%` : dash} sub={`${r.costs?.avg_holdings} funds held`} />
          </div>
          <Panel title="Growth of 100" description={`${r.strategy_description} · ${r.universe?.funds} funds · ${r.universe?.tier} ${r.universe?.plan}`}>
            <LineChartMulti series={[{ key: "s", name: "Strategy", data: r.curves!.strategy }, { key: "b", name: "Benchmark", data: r.curves!.benchmark, dashed: true }]} />
          </Panel>
          <Panel title="In-sample versus out-of-sample" description={`Out-of-sample starts ${r.oos_start}. A strategy that only works in-sample is not evidence of skill.`}>
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Period</th><th className={`${TH} text-right`}>CAGR</th><th className={`${TH} text-right`}>Bench CAGR</th><th className={`${TH} text-right`}>Volatility</th>
                  <th className={`${TH} text-right`}>Sharpe</th><th className={`${TH} text-right`}>Bench Sharpe</th><th className={`${TH} text-right`}>Max DD</th><th className={`${TH} text-right`}>Bench Max DD</th></tr></thead>
                <tbody className="divide-y divide-line/50">
                  <SegRow label="Full period" s={r.full?.strategy} b={r.full?.benchmark} />
                  <SegRow label="In-sample" s={r.in_sample?.strategy} b={r.in_sample?.benchmark} />
                  <SegRow label="Out-of-sample" s={r.out_of_sample?.strategy} b={r.out_of_sample?.benchmark} />
                </tbody>
              </table>
            </div>
          </Panel>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel title="Is the difference real?" description="Rough guide only">
              <dl className="divide-y divide-line/50 text-xs">
                {[["Average monthly excess", r.excess ? fmtPct(r.excess.monthly_excess_mean_pct, 2) : dash], ["Annualised excess, 95% interval", r.excess?.annualised_excess_ci95_pp ? `${r.excess.annualised_excess_ci95_pp[0].toFixed(1)} to ${r.excess.annualised_excess_ci95_pp[1].toFixed(1)} pp` : dash], ["Months compared", fmtInt(r.excess?.months)]].map(([k, v]) => (
                  <div key={k} className="flex justify-between py-2"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{v}</dd></div>
                ))}
              </dl>
              <p className="mt-2 text-[11px] text-faint">{r.excess?.note}</p>
            </Panel>
            <Panel title="Costs paid" description="As assumed above">
              <dl className="divide-y divide-line/50 text-xs">
                {[["Transaction costs", `${r.costs?.transaction_pct_of_start_value}% of starting value`], ["Exit loads", `${r.costs?.exit_loads_pct_of_start_value}% of starting value`], ["Rebalances", fmtInt(r.rebalances)]].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between py-2"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{v}</dd></div>
                ))}
              </dl>
            </Panel>
          </div>
          <Panel title="Recent rebalances" description="Last 24; signal on the left, trade executed after the delay">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Signal date</th><th className={TH}>Executed</th><th className={`${TH} text-right`}>Funds</th><th className={`${TH} text-right`}>Turnover</th><th className={`${TH} text-right`}>Cost + load</th></tr></thead>
                <tbody className="divide-y divide-line/50">
                  {r.trades?.map((t) => <tr key={t.signal} className="hover:bg-hover"><td className="px-2 py-1.5 font-mono">{t.signal}</td><td className="px-2 py-1.5 font-mono">{t.execution}</td><td className="px-2 py-1.5 text-right">{t.holdings}</td><td className="px-2 py-1.5 text-right">{t.turnover_pct}%</td><td className="px-2 py-1.5 text-right">{t.cost_pct_of_value}%</td></tr>)}
                </tbody>
              </table>
            </div>
          </Panel>
          <p className="text-[11px] text-faint">Backtest {r.backtest_version} · scoring {r.scoring_version} · identical settings on identical data reproduce this result exactly.</p>
        </>
      )}
    </>
  );
}
