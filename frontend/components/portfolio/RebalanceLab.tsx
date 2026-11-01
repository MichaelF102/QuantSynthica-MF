"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { Banner, Panel, StatTile, btnPrimary, inputCls } from "@/components/ui/ui";
import { api, type RebalanceResult } from "@/lib/api";
import { dash, fmtPct, tone } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";
const inr = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;
type Row = { scheme_id: number; name: string; value: string; held: string; target: string };

export function RebalanceLab({ funds }: { funds: { scheme_id: number; name: string; weight: number }[] }) {
  const [rows, setRows] = useState<Row[]>(funds.map((f) => ({ scheme_id: f.scheme_id, name: f.name, value: "", held: "", target: String(+f.weight.toFixed(2)) })));
  const [o, setO] = useState({ newCash: "0", threshold: "5", minTrade: "0", cost: "0.1", exitLoad: "1", buysOnly: false });
  const [r, setR] = useState<RebalanceResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const upd = (i: number, k: keyof Row, v: string) => setRows(rows.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  const run = async () => {
    setBusy(true); setErr(null); setR(null);
    try {
      setR(await api.rebalance({
        holdings: rows.map((x) => ({ scheme_id: x.scheme_id, value: Number(x.value || 0), ...(x.held !== "" ? { held_days: Number(x.held) } : {}) })),
        targets: rows.map((x) => ({ scheme_id: x.scheme_id, weight: Number(x.target || 0) })),
        new_cash: Number(o.newCash), threshold_pct: Number(o.threshold), min_trade: Number(o.minTrade), cost_pct: Number(o.cost), exit_load_pct: Number(o.exitLoad), buys_only: o.buysOnly,
      }));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const setOpt = (k: keyof typeof o, v: string) => setO({ ...o, [k]: v });
  const opt = (label: string, k: "newCash" | "threshold" | "minTrade" | "cost" | "exitLoad") => <label className="flex flex-col gap-1 text-xs"><span className="text-muted">{label}</span><input type="number" step="any" min={0} value={o[k]} onChange={(e) => setOpt(k, e.target.value)} className={`${inputCls} w-28`} /></label>;

  return (
    <>
      <Panel title="Your holdings" description="Enter what you hold today (₹) and the weights you want">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>Current value (₹)</th><th className={`${TH} text-right`}>Days held (optional)</th><th className={`${TH} text-right`}>Target %</th></tr></thead>
            <tbody className="divide-y divide-line/50">
              {rows.map((x, i) => (
                <tr key={x.scheme_id}><td className="max-w-[280px] truncate px-2 py-2 font-medium text-fg" title={x.name}>{x.name}</td>
                  {(["value", "held", "target"] as const).map((k) => <td key={k} className="px-2 py-1.5 text-right"><input type="number" min={0} aria-label={`${k} for ${x.name}`} value={x[k]} onChange={(e) => upd(i, k, e.target.value)} className={`${inputCls} w-28 text-right`} /></td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          {opt("New cash to invest (₹)", "newCash")}{opt("Drift threshold %", "threshold")}{opt("Minimum trade (₹)", "minTrade")}{opt("Transaction cost %", "cost")}{opt("Exit load % (units held under 1 year)", "exitLoad")}
          <label className="flex items-center gap-2 pb-2 text-xs text-muted"><input type="checkbox" checked={o.buysOnly} onChange={(e) => setO({ ...o, buysOnly: e.target.checked })} /> Buys only (no selling)</label>
          <button onClick={run} disabled={busy} className={btnPrimary}><Play className="h-3.5 w-3.5" /> {busy ? "Working…" : "Plan trades"}</button>
        </div>
      </Panel>
      {err && <Banner tone="down">{err}</Banner>}
      {r && (
        <>
          <Banner tone={r.rebalance_triggered ? "warn" : "accent"}>{r.rebalance_triggered ? `Largest drift ${r.max_drift_pct.toFixed(1)} points is above your ${r.threshold_pct}% threshold: rebalancing is suggested.` : `Largest drift ${r.max_drift_pct.toFixed(1)} points is within your ${r.threshold_pct}% threshold.`}</Banner>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatTile label="Portfolio value" value={inr(r.total_value)} /><StatTile label="Largest drift" value={`${r.max_drift_pct.toFixed(1)} pts`} /><StatTile label="Estimated costs" value={inr(r.estimated_fees)} sub="transaction cost plus exit load" />
          </div>
          <Panel title="Weights" description="Current versus target">
            <table className="w-full border-collapse text-left text-xs"><thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>Current</th><th className={`${TH} text-right`}>Target</th><th className={`${TH} text-right`}>Drift</th></tr></thead>
              <tbody className="divide-y divide-line/50">{r.weights.map((w) => <tr key={w.scheme_id}><td className="max-w-[280px] truncate px-2 py-2 text-fg" title={w.name}>{w.name}</td><td className="px-2 py-2 text-right">{w.current_pct.toFixed(1)}%</td><td className="px-2 py-2 text-right">{w.target_pct.toFixed(1)}%</td><td className={`px-2 py-2 text-right font-semibold ${tone(w.drift_pct)}`}>{fmtPct(w.drift_pct, 1)}</td></tr>)}</tbody></table>
          </Panel>
          <Panel title="Trades" description="Buy and sell amounts that reach the target">
            {r.trades.length === 0 ? <p className="text-xs text-faint">No trades needed.</p> : (
              <table className="w-full border-collapse text-left text-xs"><thead><tr className="border-b border-line"><th className={TH}>Action</th><th className={TH}>Fund</th><th className={`${TH} text-right`}>Amount</th><th className={`${TH} text-right`}>Cost</th><th className={`${TH} text-right`}>Exit load</th></tr></thead>
                <tbody className="divide-y divide-line/50">{r.trades.map((t) => <tr key={t.scheme_id}><td className={`px-2 py-2 font-semibold uppercase ${t.action === "buy" ? "text-up" : "text-down"}`}>{t.action}</td><td className="max-w-[280px] truncate px-2 py-2 text-fg" title={t.name}>{t.name}</td><td className="px-2 py-2 text-right font-mono">{inr(t.amount)}</td><td className="px-2 py-2 text-right font-mono">{t.cost ? inr(t.cost) : dash}</td><td className="px-2 py-2 text-right font-mono">{t.exit_load ? inr(t.exit_load) : dash}</td></tr>)}</tbody></table>
            )}
            <p className="mt-2 text-[11px] text-faint">{r.note}</p>
          </Panel>
        </>
      )}
    </>
  );
}
