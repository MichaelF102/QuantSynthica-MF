"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { Banner, Panel, StatTile, btnPrimary, inputCls } from "@/components/ui/ui";
import { LineChartMulti } from "@/components/charts/ChartKit";
import { api, type SimResult } from "@/lib/api";
import { dash } from "@/lib/format";

const KINDS: Record<string, string> = {
  sip: "SIP (historical)", lump_sum: "Lump sum (historical)", swp: "SWP (historical)", rolling_sip: "Rolling SIP outcomes (historical)",
  rolling_swp: "SWP survival (historical)", projection: "Projection (hypothetical)", bootstrap: "Bootstrap projection (hypothetical)",
};
const inr = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? `₹${Math.round(v).toLocaleString("en-IN")}` : dash);
const pc = (v: unknown, d = 1) => (typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(d)}%` : dash);
type Pt = [string, number];

export function SimulatorLab({ target }: { target: { scheme_id: number } | { holdings: { scheme_id: number; weight: number }[] } }) {
  const [kind, setKind] = useState("sip");
  const [f, setF] = useState<Record<string, string>>({ monthly: "10000", amount: "100000", corpus: "1000000", withdraw: "8000", years: "10", horizon: "5", stepUp: "0", inflation: "0", start: "" });
  const [state, setState] = useState<"idle" | "running" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const [r, setR] = useState<SimResult | null>(null);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const n = (k: string) => Number(f[k]);

  const run = async () => {
    setState("running"); setMsg(null); setR(null);
    const base: Record<string, unknown> = { kind, target };
    const need = (...ks: string[]) => ks.forEach((k) => (base[{ withdraw: "monthly", horizon: "horizon_years", stepUp: "step_up_pct", inflation: "inflation_pct" }[k] ?? k] = n(k)));
    if (kind === "sip") need("monthly", "stepUp");
    if (kind === "lump_sum") need("amount");
    if (kind === "swp") { need("corpus", "inflation"); base.monthly = n("withdraw"); }
    if (kind === "rolling_sip") { need("monthly", "horizon"); }
    if (kind === "rolling_swp") { need("corpus", "horizon", "inflation"); base.monthly = n("withdraw"); }
    if (kind === "projection" || kind === "bootstrap") { need("monthly", "years"); }
    if (["sip", "lump_sum", "swp"].includes(kind) && f.start) base.start = f.start;
    try { setR(await api.simulate(base)); setState("idle"); } catch (e) { setMsg((e as Error).message); setState("error"); }
  };
  const field = (label: string, k: string, step = 1) => <label className="flex flex-col gap-1 text-xs"><span className="text-muted">{label}</span><input type="number" step={step} value={f[k]} onChange={(e) => set(k, e.target.value)} className={`${inputCls} w-32`} /></label>;
  const hyp = r?.kind === "hypothetical";
  const g = (k: string) => (r as Record<string, unknown> | null)?.[k];
  const pct = g("percentiles") as Record<string, number> | undefined;
  const xp = g("xirr_pct") as Record<string, number> | number | null | undefined;

  return (
    <>
      <Panel title="Simulator" description={`On ${"scheme_id" in target ? "one fund" : `a ${target.holdings.length}-fund portfolio (rebalanced monthly)`}`}>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-xs"><span className="text-muted">Simulation</span>
            <select value={kind} onChange={(e) => { setKind(e.target.value); setR(null); }} className={`${inputCls} max-w-[280px]`} aria-label="Simulation">{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          {["sip", "rolling_sip", "projection", "bootstrap"].includes(kind) && field("Monthly SIP (₹)", "monthly", 500)}
          {kind === "sip" && field("Yearly step-up %", "stepUp")}
          {kind === "lump_sum" && field("Amount (₹)", "amount", 10000)}
          {["swp", "rolling_swp"].includes(kind) && <>{field("Corpus (₹)", "corpus", 100000)}{field("Monthly withdrawal (₹)", "withdraw", 500)}{field("Yearly increase %", "inflation")}</>}
          {["rolling_sip", "rolling_swp"].includes(kind) && field("Horizon (years)", "horizon")}
          {["projection", "bootstrap"].includes(kind) && field("Years", "years")}
          {["sip", "lump_sum", "swp"].includes(kind) && <label className="flex flex-col gap-1 text-xs"><span className="text-muted">Start date (optional)</span><input type="date" value={f.start} onChange={(e) => set("start", e.target.value)} className={inputCls} /></label>}
          <button onClick={run} disabled={state === "running"} className={btnPrimary}><Play className="h-3.5 w-3.5" /> {state === "running" ? "Running…" : "Run"}</button>
        </div>
      </Panel>
      {state === "error" && <Banner tone="down">{msg}</Banner>}
      {r && (
        <>
          <Banner tone={hyp ? "warn" : "accent"}><span><strong>{r.label}.</strong> {r.note ?? ""}</span></Banner>
          {r.available === false ? <Panel><p className="text-xs text-faint">{r.reason}</p></Panel> : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                {g("invested") !== undefined && <StatTile label="Invested" value={inr(g("invested"))} />}
                {g("final_value") !== undefined && <StatTile label="Final value" value={inr(g("final_value"))} />}
                {g("xirr_pct") !== undefined && typeof xp === "number" && <StatTile label="XIRR" value={pc(xp)} />}
                {g("cagr_pct") !== undefined && <StatTile label="CAGR" value={pc(g("cagr_pct"))} />}
                {g("multiple") !== undefined && <StatTile label="Multiple" value={`${(g("multiple") as number).toFixed(2)}x`} />}
                {g("total_withdrawn") !== undefined && <StatTile label="Withdrawn" value={inr(g("total_withdrawn"))} />}
                {g("remaining_value") !== undefined && <StatTile label="Remaining" value={inr(g("remaining_value"))} sub={g("depleted") ? `ran out ${g("depletion_date")}` : "corpus survived"} />}
                {xp && typeof xp === "object" && <><StatTile label="Median XIRR" value={pc(xp.median)} /><StatTile label="Worst 5% XIRR" value={pc(xp.p5)} /><StatTile label="Share losing money" value={pc(g("share_losing_money"), 0)} /></>}
                {g("share_lasting_full_horizon") !== undefined && <StatTile label="Corpus lasted the horizon" value={pc(g("share_lasting_full_horizon"), 0)} sub={`${g("start_dates")} start dates`} />}
                {!!g("remaining_value_percentiles") && <StatTile label="Median remaining" value={inr((g("remaining_value_percentiles") as Record<string, number>).median)} />}
                {pct && <><StatTile label="Median outcome" value={inr(pct.median)} /><StatTile label="Poor case (5th pct.)" value={inr(pct.p5)} /><StatTile label="Good case (95th pct.)" value={inr(pct.p95)} /></>}
                {g("probability_below_invested_pct") !== undefined && <StatTile label="Chance below invested" value={pc(g("probability_below_invested_pct"))} />}
              </div>
              {Array.isArray(g("curve")) && (
                <Panel title="Over time" description="Historical path"><LineChartMulti unit="" digits={0} legend
                  series={kind === "sip" ? [{ key: "v", name: "Value", data: (g("curve") as [string, number, number][]).map(([d, , v]) => [d, v] as Pt) }, { key: "i", name: "Invested", data: (g("curve") as [string, number, number][]).map(([d, i]) => [d, i] as Pt), dashed: true }]
                    : [{ key: "v", name: "Corpus value", data: g("curve") as Pt[] }]} /></Panel>
              )}
              {Array.isArray(g("series")) && <Panel title="XIRR by start date" description="Each point is one start date; start dates overlap, so they are not independent"><LineChartMulti unit="%" series={[{ key: "x", name: "XIRR", data: g("series") as Pt[] }]} legend={false} zero /></Panel>}
              {hyp && !!g("assumptions") && <Panel title="Assumptions"><pre className="overflow-x-auto font-mono text-[11px] text-muted">{JSON.stringify(g("assumptions"), null, 2)}</pre></Panel>}
            </>
          )}
        </>
      )}
    </>
  );
}
