"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, Moon, Sun, X } from "lucide-react";
import { QSLogoMark } from "@/components/brand/QSLogoMark";

const LINKS = [
  { href: "#stats", label: "Platform" },
  { href: "#engine", label: "Quant engine" },
  { href: "#risk", label: "Risk" },
  { href: "#portfolio", label: "Portfolios" },
  { href: "#regimes", label: "Regimes" },
  { href: "#assistant", label: "AI assistant" },
  { href: "#methodology", label: "Methodology" },
];

/** Landing-page navigation: section anchors, theme toggle and the entry into the application. */
export function LandingNav() {
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setDark(document.documentElement.classList.contains("dark")), 0);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => { clearTimeout(t); document.removeEventListener("keydown", onKey); };
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("theme", next ? "dark" : "light"); } catch { /* storage unavailable */ }
  };
  const focus = "focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none";
  return (
    <header className="sticky top-0 z-50 border-b border-line/80 bg-base/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-[96%] max-w-[1720px] items-center gap-6">
        <Link href="/" className={`flex shrink-0 items-center gap-2.5 transition-transform hover:scale-[1.02] ${focus}`} aria-label="QuantSynthica Mutual Funds home">
          <QSLogoMark />
          <span className="leading-tight">
            <span className="block text-[1rem] font-bold tracking-tight text-strong">QuantSynthica</span>
            <span className="block text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">Mutual Funds</span>
          </span>
        </Link>
        <nav aria-label="Landing sections" className="hidden flex-1 items-center gap-1 xl:flex">
          {LINKS.map((l) => <a key={l.href} href={l.href} className={`rounded-lg px-2.5 py-2 text-xs font-medium text-fg transition-colors hover:text-strong ${focus}`}>{l.label}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} className={`rounded-lg p-1.5 text-muted transition-colors hover:bg-hover hover:text-strong ${focus}`}>
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <Link href="/overview" className={`hidden rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-blue-600/20 transition-colors hover:bg-blue-500 sm:inline-flex ${focus}`}>Launch platform</Link>
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="landing-drawer" aria-label={open ? "Close menu" : "Open menu"} className={`rounded-lg p-1.5 text-muted hover:bg-hover hover:text-strong xl:hidden ${focus}`}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="landing-drawer" aria-label="Landing sections (mobile)" className="border-t border-line bg-base px-4 py-3 xl:hidden">
          <ul className="space-y-1">
            {LINKS.map((l) => <li key={l.href}><a href={l.href} onClick={() => setOpen(false)} className={`block rounded-lg px-3 py-2 text-sm text-fg hover:bg-hover ${focus}`}>{l.label}</a></li>)}
            <li><Link href="/overview" className="mt-2 block rounded-lg bg-blue-600 px-3 py-2 text-center text-sm font-semibold text-white">Launch platform</Link></li>
          </ul>
        </nav>
      )}
    </header>
  );
}
