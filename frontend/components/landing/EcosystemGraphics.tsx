"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion, type TargetAndTransition } from "framer-motion";

/* Schematic diagrams for the ecosystem cards. They illustrate what each layer does and carry no figures.
   Each draws itself once when it scrolls into view. */

const EASE = [0.16, 1, 0.3, 1] as const;
const Frame = ({ children }: { children: React.ReactNode }) => <div className="absolute inset-0 flex items-center justify-center px-6">{children}</div>;
const useIn = () => {
  const reduce = useReducedMotion();
  return (i: number, from: TargetAndTransition, to: TargetAndTransition) => ({ initial: reduce ? to : from, whileInView: to, viewport: { once: true }, transition: { duration: 0.6, ease: EASE, delay: 0.15 + i * 0.08 } });
};

export function DataGraphic() {
  const a = useIn();
  const rows = [["Scheme register", "official"], ["Daily NAV history", "daily"], ["Fund profile mapping", "mapped"]];
  return (
    <Frame>
      <div className="w-full max-w-sm divide-y divide-line/70 overflow-hidden rounded-lg border border-line bg-base/70 shadow-lg shadow-black/30">
        {rows.map(([r, s], i) => (
          <motion.div key={r} {...a(i, { opacity: 0, x: -10 }, { opacity: 1, x: 0 })} className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-accent/5">
            <span className="font-mono text-[11px] text-fg">{r}</span>
            <span className="font-mono text-[10px] text-faint">{s}</span>
          </motion.div>
        ))}
      </div>
    </Frame>
  );
}

export function EngineGraphic() {
  const a = useIn();
  const d = "M0 62 C 20 58, 30 40, 52 44 S 84 64, 106 40 S 150 22, 172 28 S 190 14, 200 10";
  return (
    <Frame>
      <svg viewBox="0 0 200 80" className="h-28 w-full max-w-sm overflow-visible" fill="none">
        <defs>
          <linearGradient id="qs-eng-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" style={{ stopColor: "var(--qs-accent)", stopOpacity: 0.3 }} />
            <stop offset="1" style={{ stopColor: "var(--qs-accent)", stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        {[20, 40, 60].map((y) => <line key={y} x1="0" x2="200" y1={y} y2={y} stroke="var(--qs-line)" strokeWidth="1" />)}
        <motion.path d={`${d} L200 80 L0 80 Z`} fill="url(#qs-eng-fill)" {...a(4, { opacity: 0 }, { opacity: 1 })} />
        <motion.path d={d} stroke="var(--qs-accent)" strokeWidth="1.75" strokeLinecap="round" {...a(0, { pathLength: 0 }, { pathLength: 1 })} transition={{ duration: 1.2, ease: EASE, delay: 0.2 }} />
        <motion.circle cx="200" cy="10" r="3" fill="var(--qs-accent)" {...a(8, { opacity: 0 }, { opacity: 1 })} />
        <circle cx="200" cy="10" r="3" fill="var(--qs-accent)" className="origin-center [transform-box:fill-box] opacity-30 motion-safe:animate-[qs-beat_2s_ease-in-out_1.6s_infinite]" />
      </svg>
    </Frame>
  );
}

export function AnalyticsGraphic() {
  const a = useIn();
  const h = [38, 56, 44, 70, 52, 92, 64];
  return (
    <Frame>
      <div className="flex h-28 w-full max-w-sm items-end gap-2.5">
        {h.map((v, i) => (
          <motion.div key={i} style={{ height: `${v}%`, originY: 1 }} {...a(i, { scaleY: 0 }, { scaleY: 1 })}
            className={i === 5 ? "flex-1 rounded-t-md rounded-b-sm bg-accent shadow-[0_0_22px_-2px_var(--qs-accent)]" : "flex-1 rounded-t-md rounded-b-sm border border-accent/25 bg-gradient-to-b from-accent/40 to-accent/10 transition-colors hover:from-accent hover:to-accent/60"} />
        ))}
      </div>
    </Frame>
  );
}

export function PortfolioGraphic() {
  const a = useIn();
  return (
    <Frame>
      <div className="w-full max-w-md">
        <div className="grid grid-cols-[2fr_2fr_1.4fr_1fr] gap-1.5">
          {[0, 1, 2, 3].map((i) => (
            <motion.span key={i} style={{ originX: 0 }} {...a(i, { scaleX: 0 }, { scaleX: 1 })}
              className={`relative h-2.5 overflow-hidden rounded-full ${i === 2 ? "bg-gradient-to-r from-accent to-indigo-400 qs-shimmer" : i < 2 ? "bg-accent/70" : "bg-line-strong"}`} />
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {["Builder", "Optimiser", "SIP / SWP", "Stress test"].map((t) => <span key={t} className="rounded-full border border-line bg-panel px-2.5 py-1 font-mono text-[10px] text-muted transition-all hover:-translate-y-0.5 hover:border-accent/50 hover:text-accent">{t}</span>)}
        </div>
      </div>
    </Frame>
  );
}

const ANSWER = "Returns computed from official NAV records over the period you pick, ranked against true category peers.";

export function AssistantGraphic() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.5 });
  const reduce = useReducedMotion();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!seen || reduce) return;
    const t = setInterval(() => setN((v) => { if (v >= ANSWER.length) { clearInterval(t); return v; } return v + 1; }), 26);
    return () => clearInterval(t);
  }, [seen, reduce]);
  const shown = reduce ? ANSWER.length : n;
  const done = shown >= ANSWER.length;
  return (
    <Frame>
      <div ref={ref} className="w-full max-w-sm rounded-xl border border-line bg-base/70 p-4 shadow-lg shadow-black/30">
        <p className="text-[12px] font-medium text-strong">What did this fund return over 3 years?</p>
        <p className={`mt-2 min-h-[3.2rem] text-[12px] leading-relaxed text-muted ${done ? "" : "qs-caret"}`}>{ANSWER.slice(0, shown)}</p>
        <span className={`mt-2 inline-block rounded-md border border-purple-500/30 bg-purple-500/10 px-2 py-1 font-mono text-[10px] text-ai transition-all duration-500 ${done ? "translate-y-0 opacity-100" : "translate-y-1.5 opacity-0"}`}>source · date</span>
      </div>
    </Frame>
  );
}

export function ReportsGraphic() {
  const a = useIn();
  return (
    <Frame>
      <div className="flex items-center gap-4">
        {["PDF", "XLSX"].map((t, i) => (
          <motion.div key={t} {...a(i, { opacity: 0, y: 8 }, { opacity: 1, y: 0 })}>
            <div className={`qs-float flex h-32 w-24 flex-col gap-2 rounded-xl border border-line bg-gradient-to-br from-raised to-base p-3 shadow-lg shadow-black/40 transition-transform duration-500 ease-out ${i === 0 ? "-rotate-6 group-hover:-translate-x-2 group-hover:-rotate-12" : "translate-y-3 rotate-[5deg] group-hover:translate-x-2 group-hover:translate-y-4 group-hover:rotate-[10deg]"}`} style={i ? { animationDelay: "-2.5s" } : undefined}>
              <span className={`font-mono text-[10px] font-bold tracking-wider ${i === 0 ? "text-down" : "text-up"}`}>{t}</span>
              <i className="h-1 w-full rounded bg-line-strong" /><i className="h-1 w-3/4 rounded bg-line-strong" /><i className="h-1 w-5/6 rounded bg-line-strong" />
              <div className="mt-auto h-1 overflow-hidden rounded bg-line"><motion.span className="block h-full bg-up" initial={{ width: 0 }} whileInView={{ width: "100%" }} viewport={{ once: true }} transition={{ duration: 1.8, delay: 0.6 }} /></div>
            </div>
          </motion.div>
        ))}
      </div>
    </Frame>
  );
}
