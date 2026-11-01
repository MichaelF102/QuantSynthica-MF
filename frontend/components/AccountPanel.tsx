"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Banner, Panel, btnPrimary, btnSecondary, inputCls } from "@/components/ui/ui";
import { account, getToken, setToken, type Item, type Me } from "@/lib/session";

export function AccountPanel() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => { try { setMe(await account.me()); setItems(await account.items()); } catch { setMe(null); setToken(null); } finally { setReady(true); } };
  useEffect(() => { const t = setTimeout(() => { if (getToken()) void load(); else setReady(true); }, 0); return () => clearTimeout(t); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const r = await (mode === "login" ? account.login : account.register)(email, pw); setToken(r.token); setPw(""); await load(); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  const out = async () => { try { await account.logout(); } catch { /* already invalid */ } setToken(null); setMe(null); setItems([]); };
  const del = async (id: number) => { await account.remove(id); setItems(items.filter((i) => i.id !== id)); };
  const href = (i: Item) => {
    const p = (i.payload as { p?: string; scheme_ids?: number[] }) ;
    if (i.kind === "portfolio" && p.p) return `/portfolio/builder?p=${p.p}`;
    if (i.kind === "watchlist" && p.scheme_ids?.length) return `/comparison?ids=${p.scheme_ids.slice(0, 5).join(",")}`;
    return null;
  };

  if (!ready) return <Panel><div className="h-24 animate-pulse rounded bg-raised" aria-label="Loading" /></Panel>;
  if (!me) {
    return (
      <Panel title={mode === "login" ? "Sign in" : "Create an account"} description="Accounts keep your watchlists and portfolios on the server so they follow you across browsers.">
        <form onSubmit={submit} className="flex max-w-sm flex-col gap-3 text-xs">
          <label className="flex flex-col gap-1"><span className="text-muted">Email</span><input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} /></label>
          <label className="flex flex-col gap-1"><span className="text-muted">Password{mode === "register" ? " (at least 10 characters)" : ""}</span>
            <input type="password" required minLength={mode === "register" ? 10 : 1} autoComplete={mode === "login" ? "current-password" : "new-password"} value={pw} onChange={(e) => setPw(e.target.value)} className={inputCls} /></label>
          {err && <Banner tone="down">{err}</Banner>}
          <div className="flex items-center gap-3"><button disabled={busy} className={btnPrimary}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
            <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(null); }} className="text-accent hover:underline">{mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}</button></div>
        </form>
      </Panel>
    );
  }
  return (
    <>
      <Panel title="Account" description={me.email} right={<button onClick={out} className={btnSecondary}>Sign out</button>}>
        <p className="text-xs text-muted">Saved items are private to this account.</p>
      </Panel>
      <Panel title="Saved items" description={`${items.length} item${items.length === 1 ? "" : "s"}`}>
        {items.length === 0 ? <p className="text-xs text-faint">Nothing saved yet. Use Save in the Portfolio Builder, or the Watchlist button on a fund page.</p> : (
          <ul className="divide-y divide-line/50 text-xs">{items.map((i) => (
            <li key={i.id} className="flex items-center gap-3 py-2"><span className="w-20 shrink-0 font-mono text-[10px] uppercase text-muted">{i.kind}</span>
              <span className="min-w-0 flex-1 truncate font-medium text-fg">{href(i) ? <Link href={href(i)!} className="hover:text-accent hover:underline">{i.name}</Link> : i.name}</span>
              <button onClick={() => del(i.id)} className="text-muted hover:text-down" aria-label={`Delete ${i.name}`}>Delete</button></li>))}</ul>
        )}
      </Panel>
    </>
  );
}
