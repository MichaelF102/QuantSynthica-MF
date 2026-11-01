"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Star } from "lucide-react";
import { btnSecondary } from "@/components/ui/ui";
import { account, getToken } from "@/lib/session";

const LIST = "Watchlist";

/** Adds or removes a fund from the signed-in user's default watchlist (kind=watchlist, name=Watchlist). */
export function WatchButton({ schemeId }: { schemeId: number }) {
  const [state, setState] = useState<"loading" | "anon" | "off" | "on">("loading");
  const [ids, setIds] = useState<number[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      if (!getToken()) { setState("anon"); return; }
      account.items("watchlist").then((r) => {
        const cur = ((r.find((i) => i.name === LIST)?.payload as { scheme_ids?: number[] } | undefined)?.scheme_ids) ?? [];
        setIds(cur); setState(cur.includes(schemeId) ? "on" : "off");
      }).catch(() => setState("anon"));
    }, 0);
    return () => clearTimeout(t);
  }, [schemeId]);

  if (state === "loading") return null;
  if (state === "anon") return <Link href="/account" className={btnSecondary}><Star className="h-3.5 w-3.5" /> Sign in to watch</Link>;
  const toggle = async () => {
    const next = state === "on" ? ids.filter((i) => i !== schemeId) : [...ids, schemeId];
    try { await account.save("watchlist", LIST, { scheme_ids: next }); setIds(next); setState(next.includes(schemeId) ? "on" : "off"); setErr(null); } catch (e) { setErr((e as Error).message); }
  };
  return (<><button onClick={toggle} aria-pressed={state === "on"} className={btnSecondary}><Star className={`h-3.5 w-3.5 ${state === "on" ? "fill-current text-warn" : ""}`} /> {state === "on" ? "Watching" : "Watch"}</button>{err && <span role="alert" className="text-[11px] text-down">{err}</span>}</>);
}
