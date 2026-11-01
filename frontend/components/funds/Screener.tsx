"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Condition, type FieldDef, type FilterOptions, type Group, type ScreenResult } from "@/lib/api";
import { Search, Save, Download, Plus, GitCompareArrows } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel, btnPrimary, btnSecondary, inputCls } from "@/components/ui/ui";
import { cn } from "@/lib/utils";
import { crore, dash, fmtPrice, pct, tone } from "@/lib/format";

export type Row = { id: string; field: string; op: string; value: string; value2: string; multi: string[] };
export type ScreenState = {
  tab: string; logic: "and" | "or"; rows: Row[]; sort: string; order: "asc" | "desc"; page: number; pageSize: number;
};

const TABS: { key: string; label: string; preset: Condition[]; gated?: string }[] = [
  { key: "all", label: "All Funds", preset: [] },
  { key: "equity", label: "Equity", preset: [{ field: "asset_tier", op: "eq", value: "Equity" }] },
  { key: "debt", label: "Debt", preset: [{ field: "asset_tier", op: "eq", value: "Debt" }] },
  { key: "hybrid", label: "Hybrid", preset: [{ field: "asset_tier", op: "eq", value: "Hybrid" }] },
  { key: "elss", label: "ELSS (Tax saving)", preset: [{ field: "category", op: "eq", value: "ELSS (Tax Savings)" }] },
  { key: "quant", label: "Quant Screener", preset: [], gated: "The QuantSynthica score arrives in Phase 5. NAV-derived filters (Sharpe, drawdown, volatility, beta, peer percentiles) are available in the condition builder now." },
];

const OP_LABEL: Record<string, string> = {
  gt: ">", gte: "≥", lt: "<", lte: "≤", eq: "=", neq: "≠", between: "between", in: "is any of", not_in: "is none of",
  is_null: "is missing", not_null: "is present",
};
const IDCW_FREQ = ["Daily", "Weekly", "Monthly", "Quarterly", "Annual"];
const OPTION_KEY: Record<string, keyof FilterOptions> = {
  amc: "amcs", category: "categories", asset_tier: "asset_tiers", plan_type: "plan_types", option_type: "option_types",
};
const DEFAULT: ScreenState = { tab: "all", logic: "and", rows: [], sort: "name", order: "asc", page: 1, pageSize: 50 };
const MAX_COMPARE = 5;
const uid = () => Math.random().toString(36).slice(2, 9);

function toCondition(r: Row, fields: Record<string, FieldDef>): Condition | null {
  const f = fields[r.field];
  if (!f) return null;
  if (r.op === "is_null" || r.op === "not_null") return { field: r.field, op: r.op };
  if (f.kind === "bool") return { field: r.field, op: "eq", value: r.value === "true" };
  if (r.op === "in" || r.op === "not_in") return r.multi.length ? { field: r.field, op: r.op, value: r.multi } : null;
  if (f.kind === "category") return r.value ? { field: r.field, op: r.op, value: r.value } : null;
  const a = Number(r.value);
  if (r.value.trim() === "" || Number.isNaN(a)) return null;
  if (r.op === "between") {
    const b = Number(r.value2);
    return r.value2.trim() === "" || Number.isNaN(b) ? null : { field: r.field, op: "between", value: [a, b] };
  }
  return { field: r.field, op: r.op, value: a };
}

function describe(r: Row, fields: Record<string, FieldDef>): string {
  const f = fields[r.field];
  const unit = f?.unit && f.kind === "number" && f.unit !== "pctile" && f.unit !== "z" ? ` ${f.unit}` : "";
  const v = r.op === "between" ? `${r.value} and ${r.value2}${unit}` : r.multi.length ? r.multi.join(", ") : r.value + unit;
  return `${f?.label ?? r.field} ${OP_LABEL[r.op] ?? r.op}${r.op === "is_null" || r.op === "not_null" ? "" : " " + v}`;
}

export function Screener({ fields, options, initial }: { fields: FieldDef[]; options: FilterOptions; initial?: Partial<ScreenState> }) {
  const byKey = useMemo(() => Object.fromEntries(fields.map((f) => [f.key, f])), [fields]);
  const groups = useMemo(() => {
    const g: Record<string, FieldDef[]> = {};
    for (const f of fields) (g[f.group] ??= []).push(f);
    return g;
  }, [fields]);

  const [state, setState] = useState<ScreenState>(() => ({
    ...DEFAULT, ...initial,
    rows: (initial?.rows ?? []).filter((r) => r && typeof r.field === "string").map((r) => ({ ...r, id: r.id ?? uid(), multi: r.multi ?? [], value2: r.value2 ?? "" })),
  }));
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [saved, setSaved] = useState<{ name: string; state: ScreenState }[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const reqId = useRef(0);

  const tab = TABS.find((t) => t.key === state.tab) ?? TABS[0];
  const userConds = useMemo(() => state.rows.map((r) => toCondition(r, byKey)).filter((c): c is Condition => c !== null), [state.rows, byKey]);
  const incomplete = state.rows.length - userConds.length;

  const request = useMemo(() => {
    const items: (Condition | Group)[] = [...tab.preset];
    if (userConds.length) items.push({ op: state.logic, items: userConds });
    return { filter: { op: "and", items } as Group, sort: state.sort, order: state.order, page: state.page, page_size: state.pageSize };
  }, [tab, userConds, state.logic, state.sort, state.order, state.page, state.pageSize]);

  // load saved screens
  useEffect(() => {
    // read after mount (localStorage is unavailable during SSR); deferred to avoid a synchronous setState in the effect
    const t = setTimeout(() => {
      try { setSaved(JSON.parse(localStorage.getItem("qsmf.savedScreens") ?? "[]")); } catch { setSaved([]); }
    }, 0);
    return () => clearTimeout(t);
  }, []);

  // fetch on change (debounced; stale responses ignored)
  useEffect(() => {
    const id = ++reqId.current;
    const t = setTimeout(() => {
      setLoading(true);
      api.screen(request)
        .then((r) => { if (id === reqId.current) { setResult(r); setError(null); } })
        .catch((e: Error) => { if (id === reqId.current) setError(e.message); })
        .finally(() => { if (id === reqId.current) setLoading(false); });
    }, 250);
    return () => clearTimeout(t);
  }, [request]);

  // URL persistence
  useEffect(() => {
    const url = new URL(window.location.href);
    if (JSON.stringify(state) === JSON.stringify(DEFAULT)) url.searchParams.delete("s");
    else url.searchParams.set("s", JSON.stringify(state));
    window.history.replaceState(null, "", url);
  }, [state]);

  const patch = useCallback((p: Partial<ScreenState>) => setState((s) => ({ ...s, page: 1, ...p })), []);
  const updateRow = (id: string, p: Partial<Row>) => patch({ rows: state.rows.map((r) => (r.id === id ? { ...r, ...p } : r)) });
  const addRow = () => {
    const f = fields.find((x) => x.key === "return_1y") ?? fields[0];
    patch({ rows: [...state.rows, { id: uid(), field: f.key, op: f.kind === "number" ? "gt" : "eq", value: "", value2: "", multi: [] }] });
  };
  const changeField = (id: string, key: string) => {
    const f = byKey[key];
    updateRow(id, { field: key, op: f.kind === "number" ? "gt" : "eq", value: f.kind === "bool" ? "true" : "", value2: "", multi: [] });
  };

  const optionsFor = (key: string): string[] =>
    key === "idcw_freq" ? IDCW_FREQ : OPTION_KEY[key] ? options[OPTION_KEY[key]].map((o) => o.value) : [];

  const saveScreen = () => {
    const name = window.prompt("Name this screen");
    if (!name) return;
    const next = [...saved.filter((s) => s.name !== name), { name, state }];
    setSaved(next);
    try { localStorage.setItem("qsmf.savedScreens", JSON.stringify(next)); setNotice(`Saved “${name}” in this browser.`); }
    catch { setNotice("Could not save (browser storage unavailable)."); }
  };
  const deleteSaved = (name: string) => {
    const next = saved.filter((s) => s.name !== name);
    setSaved(next);
    try { localStorage.setItem("qsmf.savedScreens", JSON.stringify(next)); } catch {}
  };

  const exportCsv = async () => {
    try {
      const { blob, truncated } = await api.exportCsv(request);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "quantsynthica-screen.csv";
      a.click();
      URL.revokeObjectURL(a.href);
      setNotice(truncated ? "Export truncated to the first 10,000 rows." : `Exported ${result?.total ?? ""} rows.`);
    } catch (e) { setNotice((e as Error).message); }
  };

  const toggleSel = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= MAX_COMPARE ? s : [...s, id]));

  const sortHeader = (key: string, label: string, right = true) => (
    <th className={`px-3 py-2 font-medium ${right ? "text-right" : ""}`}>
      <button onClick={() => patch({ sort: key, order: state.sort === key && state.order === "asc" ? "desc" : "asc" })} className="hover:text-fg">
        {label}{state.sort === key ? (state.order === "asc" ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );

  const total = result?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / state.pageSize));

  return (
    <div className="space-y-4">
      <PageHeader title="Mutual Fund" accent="Screener" subtitle="DISCOVER"
        description="Combine conditions across fund attributes, returns and category-relative percentiles. Missing values never match a numeric condition."
        right={
          <div className="flex gap-2">
            <button onClick={saveScreen} className={btnSecondary}><Save className="h-3.5 w-3.5" /> Save screen</button>
            <button onClick={exportCsv} className={btnSecondary} disabled={!total}><Download className="h-3.5 w-3.5" /> Export CSV</button>
          </div>
        } />

      <div className="no-scrollbar w-full overflow-x-auto py-2">
        <nav aria-label="Screens" className="flex min-w-max items-center gap-1.5 rounded-xl border border-line bg-raised/80 p-1 backdrop-blur-md">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => patch({ tab: t.key })} aria-current={state.tab === t.key ? "page" : undefined}
              className={cn("rounded-lg px-3.5 py-2 text-xs", state.tab === t.key ? "bg-blue-600 font-semibold text-white shadow-lg shadow-blue-600/30" : "font-medium text-muted hover:bg-hover hover:text-strong")}>
              {t.label}
            </button>
          ))}
        </nav>
      </div>
      {tab.gated && <Banner tone="warn">{tab.gated}</Banner>}

      <Panel>
        <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
          <span className="font-medium">Conditions</span>
          <span className="text-muted">Match</span>
          <select value={state.logic} onChange={(e) => patch({ logic: e.target.value as "and" | "or" })} className={inputCls} aria-label="Match logic">
            <option value="and">ALL (AND)</option>
            <option value="or">ANY (OR)</option>
          </select>
          <span className="text-muted">of the conditions below{tab.preset.length ? `, within ${tab.label}` : ""}</span>
        </div>
        <div className="space-y-2">
          {state.rows.map((r) => {
            const f = byKey[r.field];
            return (
              <div key={r.id} className="flex flex-wrap items-center gap-2 text-xs">
                <select value={r.field} onChange={(e) => changeField(r.id, e.target.value)} className={cn(inputCls, "max-w-[260px]")} aria-label="Field">
                  {Object.entries(groups).map(([g, fs]) => (
                    <optgroup key={g} label={g}>{fs.map((x) => <option key={x.key} value={x.key}>{x.label}{x.unit && x.kind === "number" ? ` (${x.unit})` : ""}</option>)}</optgroup>
                  ))}
                </select>
                {f.kind !== "bool" && (
                  <select value={r.op} onChange={(e) => updateRow(r.id, { op: e.target.value, multi: [] })} className={inputCls} aria-label="Operator">
                    {f.ops.map((o) => <option key={o} value={o}>{OP_LABEL[o] ?? o}</option>)}
                  </select>
                )}
                {f.kind === "bool" && (
                  <select value={r.value || "true"} onChange={(e) => updateRow(r.id, { value: e.target.value, op: "eq" })} className={inputCls}>
                    <option value="true">Yes</option><option value="false">No</option>
                  </select>
                )}
                {f.kind === "number" && r.op !== "is_null" && r.op !== "not_null" && (
                  <>
                    <input type="number" step="any" value={r.value} onChange={(e) => updateRow(r.id, { value: e.target.value })} className={cn(inputCls, "w-28")} aria-label="Value" />
                    {r.op === "between" && (<><span className="text-muted">and</span>
                      <input type="number" step="any" value={r.value2} onChange={(e) => updateRow(r.id, { value2: e.target.value })} className={cn(inputCls, "w-28")} aria-label="Upper value" /></>)}
                  </>
                )}
                {f.kind === "category" && (r.op === "in" || r.op === "not_in") && (
                  <select multiple value={r.multi} onChange={(e) => updateRow(r.id, { multi: Array.from(e.target.selectedOptions, (o) => o.value) })} className={cn(inputCls, "h-24 max-w-[300px]")} aria-label="Values">
                    {optionsFor(r.field).map((o) => <option key={o}>{o}</option>)}
                  </select>
                )}
                {f.kind === "category" && r.op !== "in" && r.op !== "not_in" && r.op !== "is_null" && r.op !== "not_null" && (
                  <select value={r.value} onChange={(e) => updateRow(r.id, { value: e.target.value })} className={cn(inputCls, "max-w-[300px]")} aria-label="Value">
                    <option value="">Select…</option>
                    {optionsFor(r.field).map((o) => <option key={o}>{o}</option>)}
                  </select>
                )}
                <button onClick={() => patch({ rows: state.rows.filter((x) => x.id !== r.id) })} className="px-2 text-muted hover:text-down" aria-label="Remove condition">✕</button>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
          <button onClick={addRow} className={btnSecondary}><Plus className="h-3.5 w-3.5" /> Add condition</button>
          <button onClick={() => { setState(DEFAULT); setSelected([]); }} className="text-[11px] font-medium text-accent hover:underline">Reset all</button>
          {incomplete > 0 && <span className="text-warn" role="status">{incomplete} incomplete condition{incomplete > 1 ? "s" : ""} ignored</span>}
        </div>
        {state.rows.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {state.rows.map((r) => <span key={r.id} className="rounded-full border border-line bg-raised px-3 py-1 font-mono text-[11px] text-fg">{describe(r, byKey)}</span>)}
          </div>
        )}
        {saved.length > 0 && (
          <div className="mt-4 border-t border-line pt-3 text-xs">
            <span className="mr-2 text-muted">Saved screens (this browser):</span>
            {saved.map((s) => (
              <span key={s.name} className="mr-2 inline-flex items-center gap-1 rounded bg-raised px-2 py-1">
                <button onClick={() => { setState({ ...DEFAULT, ...s.state }); setSelected([]); }} className="hover:text-accent">{s.name}</button>
                <button onClick={() => deleteSaved(s.name)} className="text-muted hover:text-down" aria-label={`Delete ${s.name}`}>✕</button>
              </span>
            ))}
          </div>
        )}
      </Panel>

      {notice && <Banner tone="accent">{notice}</Banner>}
      {error && <Banner tone="down">Could not run screen: {error}</Banner>}

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <span className="font-mono text-muted" aria-live="polite">{loading ? "Searching…" : `${total.toLocaleString("en-IN")} fund${total === 1 ? "" : "s"} match`}</span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-muted">{selected.length}/{MAX_COMPARE} selected</span>
          {selected.length >= 1 && <Link href={`/comparison?ids=${selected.join(",")}`} className={btnPrimary}><GitCompareArrows className="h-3.5 w-3.5" /> Compare selected</Link>}
          <label className="text-muted">Rows <select value={state.pageSize} onChange={(e) => patch({ pageSize: Number(e.target.value) })} className="ml-1 rounded border border-line bg-raised px-1 py-0.5 text-fg">
            {[25, 50, 100].map((n) => <option key={n}>{n}</option>)}</select></label>
        </div>
      </div>

      {result && result.items.length === 0 && !loading ? (
        <Panel><EmptyState icon={Search} title="No funds match these conditions" hint="Loosen a filter or reset all." /></Panel>
      ) : (
        <div className="w-full overflow-x-auto rounded-xl border border-line bg-panel/95 p-3 shadow-lg shadow-black/20">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th className="w-8 px-3 py-2" />
                {sortHeader("name", "Fund", false)}
                <th className="px-3 py-2 font-medium">Category</th>
                <th className="px-3 py-2 font-medium">Plan · Option</th>
                {sortHeader("net_assets", "Net assets")}
                {sortHeader("price", "Price")}
                {sortHeader("return_3m", "3M")}
                {sortHeader("return_1y", "1Y")}
                {sortHeader("return_3y", "3Y")}
                {sortHeader("return_5y", "5Y")}
                {sortHeader("quant_score", "Quant score")}
                {sortHeader("sharpe_3y", "Sharpe 3Y")}
                {sortHeader("max_dd_3y", "Max DD 3Y")}
                {sortHeader("cat_pct_1y", "1Y pctile")}
                {sortHeader("cat_pct_3y", "3Y pctile")}
                {sortHeader("cat_pct_5y", "5Y pctile")}
                {sortHeader("price_vs_200d", "vs 200d")}
              </tr>
            </thead>
            <tbody className={cn("divide-y divide-line/50", loading && "opacity-60")}>
              {(result?.items ?? []).map((f) => (
                <tr key={f.id} className="transition-colors hover:bg-hover">
                  <td className="px-3 py-1.5"><input type="checkbox" checked={selected.includes(f.id)} onChange={() => toggleSel(f.id)}
                    disabled={!selected.includes(f.id) && selected.length >= MAX_COMPARE} aria-label={`Select ${f.name}`} /></td>
                  <td className="max-w-[340px] px-3 py-1.5">
                    <Link href={`/funds/${f.id}`} className="hover:text-accent">{f.name}</Link>
                    <div className="truncate text-xs text-muted">{f.amc}{f.is_insurer_fund ? " · insurer" : ""}{f.is_discontinued ? " · discontinued" : ""}</div>
                  </td>
                  <td className="px-3 py-1.5 text-muted">{f.category}</td>
                  <td className="px-3 py-1.5 text-muted">{f.plan_type} · {f.option_type}</td>
                  <td className="px-3 py-1.5 text-right">{crore(f.net_assets)}</td>
                  <td className="px-3 py-1.5 text-right">{fmtPrice(f.price)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.return_3m)}`}>{pct(f.return_3m)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.return_1y)}`}>{pct(f.return_1y)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.return_3y)}`}>{pct(f.return_3y)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.return_5y)}`}>{pct(f.return_5y)}</td>
                  <td className="px-3 py-1.5 text-right">{f.quant_score === null ? dash : f.quant_score.toFixed(1)}</td>
                  <td className="px-3 py-1.5 text-right">{f.sharpe_3y === null ? dash : f.sharpe_3y.toFixed(2)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.max_dd_3y)}`}>{f.max_dd_3y === null ? dash : pct(f.max_dd_3y, 1)}</td>
                  <td className="px-3 py-1.5 text-right">{f.cat_pct_1y === null ? dash : f.cat_pct_1y.toFixed(0)}</td>
                  <td className="px-3 py-1.5 text-right">{f.cat_pct_3y === null ? dash : f.cat_pct_3y.toFixed(0)}</td>
                  <td className="px-3 py-1.5 text-right">{f.cat_pct_5y === null ? dash : f.cat_pct_5y.toFixed(0)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone(f.price_vs_200d)}`}>{f.price_vs_200d === null ? dash : pct(f.price_vs_200d, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] text-faint">1Y, 3Y and 5Y return columns are as reported in the source data and may be measured to earlier dates. Use the NAV-derived fields (Sharpe, drawdown, volatility, peer percentiles) in the condition builder for consistent, dated figures.</p>
      <div className="flex items-center justify-between text-xs text-muted">
        <span className="font-mono">Page {state.page} of {pages}</span>
        <div className="flex gap-3">
          <button disabled={state.page <= 1} onClick={() => setState((s) => ({ ...s, page: s.page - 1 }))} className="enabled:hover:text-fg disabled:opacity-40">← Previous</button>
          <button disabled={state.page >= pages} onClick={() => setState((s) => ({ ...s, page: s.page + 1 }))} className="enabled:hover:text-fg disabled:opacity-40">Next →</button>
        </div>
      </div>
    </div>
  );
}
