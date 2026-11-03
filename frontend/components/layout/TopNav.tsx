"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Menu as MenuIcon, Moon, Sun, X } from "lucide-react";
import { QSLogoMark } from "@/components/brand/QSLogoMark";
import { cn } from "@/lib/utils";

// Navigation per docs/decisions/001-navigation.md. Pages not built yet are visible but disabled.
type Item = { label: string; href?: string; children?: { label: string; href: string; description: string }[]; tone?: "ai" };
const ITEMS: Item[] = [
  { label: "Market Overview", href: "/overview" },
  {
    label: "Fund Explorer", href: "/funds",
    children: [
      { label: "Fund Explorer", href: "/funds", description: "Browse and open any scheme" },
      { label: "Comparison", href: "/comparison", description: "Compare up to five schemes" },
    ],
  },
  { label: "Screener", href: "/screener" },
  { label: "Data Coverage", href: "/coverage" },
  {
    label: "Analysis", href: "/performance",
    children: [
      { label: "Performance Analytics", href: "/performance", description: "Returns, rolling windows, calendar years, consistency" },
      { label: "Risk Analytics", href: "/risk", description: "Volatility, drawdown, tail risk, correlation" },
    ],
  },
  {
    label: "Quant Research Lab", href: "/quant/scoring", tone: "ai",
    children: [
      { label: "Fund Scoring", href: "/quant/scoring", description: "QuantSynthica score ranked within peer groups" },
      { label: "Factor Research", href: "/quant/factors", description: "Do factors predict peer-relative returns?" },
      { label: "Statistical Analysis", href: "/quant/statistics", description: "Correlations and distributions" },
      { label: "Fund Clustering", href: "/quant/clustering", description: "K-Means, hierarchical, GMM, DBSCAN, PCA" },
      { label: "Regime Analysis", href: "/quant/regimes", description: "Bull, bear, sideways and volatility regimes" },
      { label: "Strategy Backtesting", href: "/quant/backtesting", description: "Test fund-selection rules" },
    ],
  },
  {
    label: "Portfolios", href: "/portfolio/builder",
    children: [
      { label: "Portfolio Builder", href: "/portfolio/builder", description: "Weights, returns, risk, allocation, correlation" },
      { label: "Optimization", href: "/portfolio/optimization", description: "Min variance, max Sharpe, risk parity, CVaR, frontier" },
      { label: "SIP / SWP Simulators", href: "/portfolio/sip-swp", description: "Replay plans on real history, or project" },
      { label: "Rebalancing", href: "/portfolio/rebalancing", description: "Drift, trades and costs" },
      { label: "Stress Testing", href: "/portfolio/stress-testing", description: "Worst historical falls and market shocks" },
    ],
  },
  { label: "AMC Intelligence", href: "/amc" },
  { label: "AI Assistant", href: "/assistant", tone: "ai" },
  { label: "Account", href: "/account" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setDark(document.documentElement.classList.contains("dark")), 0);
    return () => clearTimeout(t);
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("theme", next ? "dark" : "light"); } catch {}
  };
  return (
    <button type="button" onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="rounded-lg p-2 text-muted transition-colors hover:bg-hover hover:text-strong focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none">
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

function Menu({ item, active }: { item: Item; active: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div ref={ref} className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onBlur={(e) => { if (!ref.current?.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <Link href={item.href!} aria-haspopup="menu" aria-expanded={open} aria-current={active ? "page" : undefined}
        onFocus={() => setOpen(true)}
        className={cn("relative flex items-center gap-1 px-2 py-4 text-xs font-medium hover:text-strong focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none",
          active ? (item.tone === "ai" ? "font-semibold text-ai" : "font-semibold text-accent") : (item.tone === "ai" ? "text-ai" : "text-fg"))}>
        {item.label}<ChevronDown className="h-3 w-3" />
        {active && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-500" />}
      </Link>
      {open && (
        <div role="menu" className="absolute left-0 top-full z-[60] mt-0 w-72 rounded-xl border border-line bg-raised p-1.5 shadow-[0_18px_48px_-12px_rgba(0,0,0,0.65)]">
          {item.children!.map((c) => (
            <Link key={c.href} href={c.href} role="menuitem" onClick={() => setOpen(false)}
              className="block rounded-lg px-2.5 py-2 hover:bg-hover focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none">
              <span className="block text-[12.5px] font-medium text-fg">{c.label}</span>
              <span className="block text-[11px] text-faint">{c.description}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/** Phone/tablet navigation: a full-height drawer with every item, groups expanded (hover menus do not work on touch). */
function MobileDrawer({ path, isActive, onClose }: { path: string; isActive: (i: Item) => boolean; onClose: () => void }) {
  const focus = "focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none";
  return (
    <nav id="mobile-nav" aria-label="Primary (mobile)" data-print-hide
      className="absolute inset-x-0 top-full z-40 h-[calc(100dvh-4rem)] overflow-y-auto overscroll-contain border-t border-line bg-base px-4 pb-10 pt-3 xl:hidden">
      <ul className="mx-auto max-w-xl space-y-1">
        {ITEMS.map((i) => (
          <li key={i.label}>
            {i.href && (
              <Link href={i.href} onClick={onClose} aria-current={isActive(i) && !i.children ? "page" : undefined}
                className={cn("flex min-h-11 items-center rounded-lg px-3 text-sm hover:bg-hover", focus,
                  i.children ? "text-[11px] font-semibold uppercase tracking-wider" : "font-medium",
                  i.tone === "ai" ? "text-ai" : isActive(i) ? "text-accent" : i.children ? "text-muted" : "text-fg")}>
                {i.label}
              </Link>
            )}
            {i.children && (
              <ul className="mb-2 ml-3 space-y-0.5 border-l border-line pl-2">
                {i.children.map((c) => (
                  <li key={c.href}>
                    <Link href={c.href} onClick={onClose} aria-current={path.startsWith(c.href) ? "page" : undefined}
                      className={cn("block rounded-lg px-3 py-2 hover:bg-hover", focus)}>
                      <span className={cn("block text-[13px] font-medium", path.startsWith(c.href) ? "text-accent" : "text-fg")}>{c.label}</span>
                      <span className="block text-[11px] text-faint">{c.description}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function TopNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  // close the drawer on navigation; state is adjusted during render (not in an effect) to avoid a cascading update
  const [lastPath, setLastPath] = useState(path);
  if (lastPath !== path) { setLastPath(path); setOpen(false); }
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = ""; document.removeEventListener("keydown", onKey); };
  }, [open]);
  const isActive = (i: Item) =>
    i.children ? i.children.some((c) => path.startsWith(c.href)) : !!i.href && path.startsWith(i.href);
  return (
    <header data-print-hide className="sticky top-0 z-50 border-b border-line/80 bg-base/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-[96%] max-w-[1720px] items-center gap-3 sm:gap-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5 transition-transform hover:scale-[1.02]" aria-label="QuantSynthica Mutual Funds home">
          <QSLogoMark />
          <span className="leading-tight">
            <span className="block text-[1rem] font-bold tracking-tight text-strong">QuantSynthica</span>
            <span className="block text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">Mutual Funds</span>
          </span>
        </Link>
        <nav aria-label="Primary" className="no-scrollbar hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto xl:flex">
          {ITEMS.map((i) =>
            i.children ? <Menu key={i.label} item={i} active={isActive(i)} /> : i.href ? (
              <Link key={i.label} href={i.href} aria-current={isActive(i) ? "page" : undefined}
                className={cn("relative whitespace-nowrap px-2 py-4 text-xs font-medium hover:text-strong focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none",
                  isActive(i) ? "font-semibold text-accent" : "text-fg")}>
                {i.label}
                {isActive(i) && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-500" />}
              </Link>
            ) : (
              <span key={i.label} aria-disabled="true" title="Planned: not built yet"
                className={cn("cursor-not-allowed whitespace-nowrap px-2 py-4 text-xs font-medium opacity-60", i.tone === "ai" ? "text-ai" : "text-faint")}>
                {i.label}
              </span>
            ),
          )}
        </nav>
        <div className="ml-auto flex items-center gap-1 xl:ml-0">
          <ThemeToggle />
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-nav" aria-label={open ? "Close menu" : "Open menu"}
            className="rounded-lg p-2 text-muted hover:bg-hover hover:text-strong focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none xl:hidden">
            {open ? <X className="h-5 w-5" /> : <MenuIcon className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {open && <MobileDrawer path={path} isActive={isActive} onClose={() => setOpen(false)} />}
    </header>
  );
}
