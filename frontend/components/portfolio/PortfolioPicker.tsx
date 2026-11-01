"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Save, Scale, Trash2 } from "lucide-react";
import { Banner, Panel, btnPrimary, btnSecondary, inputCls } from "@/components/ui/ui";
import { api, type PFund } from "@/lib/api";
import { cn } from "@/lib/utils";
import { account, getToken } from "@/lib/session";
import { MAX_FUNDS as MAX, encode } from "@/lib/portfolio-url";

export type Pick = { scheme_id: number; name: string; category: string; weight: number };
const KEY = "qsmf.savedPortfolios";

/** Fund search plus weight editing. The selection lives in the URL (?p=id:weight,...) so every portfolio page shares it. */
export function PortfolioPicker({ initial, basePath, showWeights = true, minFunds = 1, note }: {
  initial: Pick[]; basePath: string; showWeights?: boolean; minFunds?: number; note?: string;
}) {
  const router = useRouter();
  const [picks, setPicks] = useState<Pick[]>(initial);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PFund[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ name: string; p: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const req = useRef(0);

  useEffect(() => {
    const t = setTimeout(() => { try { setSaved(JSON.parse(localStorage.getItem(KEY) ?? "[]")); } catch { setSaved([]); } }, 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const id = ++req.current;
    const t = setTimeout(() => {
      if (q.trim().length < 2) { setResults([]); setBusy(false); return; }
      setBusy(true);
      api.portfolioFunds(q.trim()).then((r) => { if (id === req.current) { setResults(r); setErr(null); } })
        .catch((e: Error) => { if (id === req.current) setErr(e.message); }).finally(() => { if (id === req.current) setBusy(false); });
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const total = picks.reduce((a, p) => a + p.weight, 0);
  const add = (f: PFund) => {
    if (picks.some((p) => p.scheme_id === f.scheme_id) || picks.length >= MAX) return;
    setPicks([...picks, { scheme_id: f.scheme_id, name: f.name, category: f.category, weight: picks.length ? 100 / (picks.length + 1) : 100 }]);
    setQ("");
  };
  const apply = () => router.push(`${basePath}?p=${encode(picks.map((p) => ({ scheme_id: p.scheme_id, weight: p.weight })))}`);
  const equalise = () => setPicks(picks.map((p) => ({ ...p, weight: 100 / picks.length })));
  const save = () => {
    const name = window.prompt("Name this portfolio (saved in this browser only)");
    if (!name) return;
    const next = [...saved.filter((s) => s.name !== name), { name, p: encode(picks.map((p) => ({ scheme_id: p.scheme_id, weight: p.weight }))) }];
    setSaved(next);
    const p = encode(picks.map((x) => ({ scheme_id: x.scheme_id, weight: x.weight })));
    if (getToken()) {
      account.save("portfolio", name, { p }).then(() => setMsg(`Saved “${name}” to your account.`)).catch((e: Error) => setMsg(`Could not save to your account: ${e.message}`));
      return;
    }
    try { localStorage.setItem(KEY, JSON.stringify(next)); setMsg(`Saved “${name}” in this browser only. Sign in to keep it on your account.`); } catch { setMsg("Could not save (browser storage unavailable)."); }
  };

  return (
    <Panel title="Portfolio" description={`${picks.length} fund${picks.length === 1 ? "" : "s"}${showWeights ? ` · weights add to ${total.toFixed(1)}% (normalised to 100%)` : ""}`}
      info="Only Growth schemes with a confirmed link to official NAV records can be used. IDCW options are excluded because their NAVs omit distributions.">
      <div className="relative mb-3 max-w-xl">
        <label htmlFor="pf-search" className="text-xs text-muted">Add a fund ({picks.length}/{MAX})</label>
        <input id="pf-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name…" className={cn(inputCls, "mt-1 w-full py-2")} />
        {(results.length > 0 || busy) && (
          <ul className="absolute z-10 mt-1 w-full rounded-xl border border-line bg-raised p-1.5 text-xs shadow-[0_18px_48px_-12px_rgba(0,0,0,0.65)]">
            {busy && <li className="px-3 py-2 text-muted">Searching…</li>}
            {results.map((r) => (
              <li key={r.scheme_id}>
                <button onClick={() => add(r)} disabled={picks.some((p) => p.scheme_id === r.scheme_id)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-hover disabled:opacity-40">
                  <Plus className="h-3.5 w-3.5 shrink-0 text-accent" /><span>{r.name}<span className="block text-[11px] text-faint">{r.category} · {r.plan} · {r.tier}</span></span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {err && <div className="mb-2"><Banner tone="down">{err}</Banner></div>}
      {picks.length === 0 ? <p className="py-4 text-xs text-faint">No funds yet. Search above to add funds.</p> : (
        <ul className="divide-y divide-line/50 text-xs">
          {picks.map((p) => (
            <li key={p.scheme_id} className="flex items-center gap-3 py-2">
              <span className="min-w-0 flex-1"><span className="block truncate font-medium text-fg">{p.name}</span><span className="block truncate text-[11px] text-faint">{p.category}</span></span>
              {showWeights && (
                <label className="flex items-center gap-1 text-muted"><span className="sr-only">Weight for {p.name}</span>
                  <input type="number" min={0} step={0.5} value={Number(p.weight.toFixed(2))} onChange={(e) => setPicks(picks.map((x) => (x.scheme_id === p.scheme_id ? { ...x, weight: Math.max(0, Number(e.target.value)) } : x)))} className={cn(inputCls, "w-20 text-right")} />%
                </label>
              )}
              <button onClick={() => setPicks(picks.filter((x) => x.scheme_id !== p.scheme_id))} className="p-1.5 text-muted hover:text-down" aria-label={`Remove ${p.name}`}><Trash2 className="h-3.5 w-3.5" /></button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button onClick={apply} disabled={picks.length < minFunds} className={btnPrimary}>{minFunds > 1 ? `Use ${picks.length} funds` : "Analyse portfolio"}</button>
        {showWeights && <button onClick={equalise} disabled={!picks.length} className={btnSecondary}><Scale className="h-3.5 w-3.5" /> Equal weights</button>}
        <button onClick={save} disabled={!picks.length} className={btnSecondary}><Save className="h-3.5 w-3.5" /> Save</button>
        {saved.length > 0 && (
          <label className="flex items-center gap-1.5 text-xs text-muted">Saved
            <select className={inputCls} value="" aria-label="Load a saved portfolio" onChange={(e) => { if (e.target.value) router.push(`${basePath}?p=${e.target.value}`); }}>
              <option value="">Load…</option>{saved.map((s) => <option key={s.name} value={s.p}>{s.name}</option>)}
            </select></label>
        )}
        {minFunds > 1 && picks.length < minFunds && <span className="text-[11px] text-faint">Select at least {minFunds} funds.</span>}
      </div>
      {msg && <p className="mt-2 text-[11px] text-muted" role="status">{msg}</p>}
      {note && <p className="mt-2 text-[11px] text-faint">{note}</p>}
    </Panel>
  );
}
