"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type FundSummary } from "@/lib/api";
import { Banner, inputCls } from "@/components/ui/ui";
import { cn } from "@/lib/utils";

export function FundPicker({ ids, max, basePath = "/comparison", extra = "" }: { ids: number[]; max: number; basePath?: string; extra?: string }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FundSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const req = useRef(0);
  const full = ids.length >= max;

  useEffect(() => {
    const id = ++req.current;
    const t = setTimeout(() => {
      if (q.trim().length < 2) { setResults([]); setBusy(false); return; }
      setBusy(true);
      api.funds({ q: q.trim(), page_size: 8, sort: "net_assets", order: "desc" })
        .then((r) => { if (id === req.current) { setResults(r.items); setErr(null); } })
        .catch((e: Error) => { if (id === req.current) setErr(e.message); })
        .finally(() => { if (id === req.current) setBusy(false); });
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const add = (id: number) => {
    if (ids.includes(id) || full) return;
    router.push(`${basePath}?ids=${[...ids, id].join(",")}${extra}`);
    setQ("");
  };

  return (
    <div className="relative max-w-xl">
      <label className="text-xs text-muted" htmlFor="fund-search">Add a fund ({ids.length}/{max})</label>
      <input id="fund-search" value={q} onChange={(e) => setQ(e.target.value)} disabled={full}
        placeholder={full ? "Maximum reached — remove a fund first" : "Search by fund or AMC name…"}
        className={cn(inputCls, "mt-1 w-full py-2 disabled:opacity-50")} />
      {err && <div className="mt-1"><Banner tone="down">{err}</Banner></div>}
      {(results.length > 0 || busy) && !full && (
        <ul className="absolute z-10 mt-1 w-full rounded-xl border border-line bg-raised p-1.5 text-xs shadow-[0_18px_48px_-12px_rgba(0,0,0,0.65)]">
          {busy && <li className="px-3 py-2 text-muted">Searching…</li>}
          {results.map((r) => (
            <li key={r.id}>
              <button onClick={() => add(r.id)} disabled={ids.includes(r.id)} className="w-full rounded-lg px-2.5 py-2 text-left hover:bg-hover focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none disabled:opacity-40">
                {r.name}<span className="block text-[11px] text-faint">{r.amc} · {r.category} · {r.plan_type} {r.option_type}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
