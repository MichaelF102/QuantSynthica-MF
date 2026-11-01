"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { Banner, Panel, btnPrimary, inputCls } from "@/components/ui/ui";
import { account, getToken } from "@/lib/session";

type Fact = { label: string; value: number | string | null; unit: string; as_of: string | null; source: string; tool: string };
type Reply = { refused: boolean; facts: Fact[]; unavailable: string[]; text: string; interpretation: string | null; interpretation_note: string | null; disclaimer: string; tool_calls: { name: string; ok: boolean }[] };
type Turn = { q: string; r?: Reply; err?: string };
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EXAMPLES = ["How risky is Tata India Consumer?", "What is the score of HDFC Flexi Cap and why?", "Which AMC ranks best?"];

const show = (v: Fact["value"]) => (typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : v ?? "—");

export function AssistantChat() {
  const [signed, setSigned] = useState<boolean | null>(null);
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { const t = setTimeout(() => { if (!getToken()) { setSigned(false); return; } account.me().then(() => setSigned(true)).catch(() => setSigned(false)); }, 0); return () => clearTimeout(t); }, []);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setBusy(true); setQ(""); setTurns((t) => [...t, { q: question }]);
    try {
      const r = await fetch(`${BASE}/api/v1/assistant/ask`, { method: "POST", headers: { "content-type": "application/json", authorization: `Bearer ${getToken()}` }, body: JSON.stringify({ question }) });
      const body = await r.json();
      if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request failed");
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, r: body as Reply } : x)));
    } catch (e) { setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, err: (e as Error).message } : x))); } finally { setBusy(false); }
  };

  if (signed === null) return <Panel><div className="h-24 animate-pulse rounded bg-raised" aria-label="Loading" /></Panel>;
  if (!signed) return <Panel tone="ai" icon={Sparkles} title="Sign in to use the assistant"><p className="text-xs text-muted">The assistant is available to signed-in users. <Link href="/account" className="text-accent hover:underline">Sign in or create an account</Link>.</p></Panel>;
  return (
    <>
      <Banner tone="accent">The assistant looks things up in this platform&rsquo;s own calculations and shows where each figure comes from. It does not give investment advice or predict returns.</Banner>
      <Panel tone="ai" icon={Sparkles} title="Ask about a fund or AMC">
        <div className="mb-3 flex flex-wrap gap-2">{EXAMPLES.map((e) => <button key={e} onClick={() => ask(e)} className="rounded-full border border-line px-3 py-1 text-[11px] text-muted hover:bg-hover hover:text-fg">{e}</button>)}</div>
        <div className="space-y-4" aria-live="polite">
          {turns.map((t, i) => (
            <div key={i} className="space-y-2">
              <p className="text-xs font-semibold text-strong">{t.q}</p>
              {!t.r && !t.err && <div className="h-10 animate-pulse rounded bg-raised" />}
              {t.err && <Banner tone="down">{t.err}</Banner>}
              {t.r && (
                <div className="rounded-lg border border-line bg-raised p-3 text-xs">
                  {t.r.refused ? <p>{t.r.text}</p> : (
                    <>
                      {t.r.facts.length > 0 && <><div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">Facts</div>
                        <table className="w-full border-collapse"><tbody className="divide-y divide-line/50">{t.r.facts.map((f, k) => (
                          <tr key={k}><td className="py-1 pr-3">{f.label}</td><td className="whitespace-nowrap py-1 text-right font-mono font-semibold">{show(f.value)} {f.unit}</td>
                            <td className="hidden py-1 pl-3 text-[10px] text-faint sm:table-cell">{f.source}{f.as_of ? ` · ${f.as_of}` : ""}</td></tr>))}</tbody></table></>}
                      {t.r.unavailable.length > 0 && <><div className="mb-1 mt-3 font-mono text-[10px] uppercase tracking-wider text-muted">Not available</div><ul className="space-y-0.5 text-muted">{t.r.unavailable.map((u) => <li key={u}>• {u}</li>)}</ul></>}
                      {t.r.facts.length === 0 && t.r.unavailable.length === 0 && <p>{t.r.text}</p>}
                      {t.r.interpretation && <><div className="mb-1 mt-3 font-mono text-[10px] uppercase tracking-wider text-[var(--qs-ai,#a78bfa)]">Model interpretation (every figure checked against the facts)</div><p>{t.r.interpretation}</p></>}
                      {t.r.interpretation_note && <p className="mt-2 text-[11px] text-faint">{t.r.interpretation_note}</p>}
                    </>
                  )}
                  <p className="mt-3 text-[10px] text-faint">{t.r.disclaimer}</p>
                </div>
              )}
            </div>
          ))}
          <div ref={end} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); void ask(q); }} className="mt-4 flex gap-2">
          <label className="sr-only" htmlFor="ask">Your question</label>
          <input id="ask" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder="e.g. How risky is Tata India Consumer?" className={`${inputCls} flex-1 py-2`} />
          <button disabled={busy || !q.trim()} className={btnPrimary}><Send className="h-3.5 w-3.5" /> Ask</button>
        </form>
      </Panel>
    </>
  );
}
