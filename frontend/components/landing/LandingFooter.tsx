import Link from "next/link";

const COLS = [
  { title: "Platform", links: [["Market overview", "/overview"], ["Fund explorer", "/funds"], ["Screener", "/screener"], ["Comparison", "/comparison"], ["Data coverage", "/coverage"]] },
  { title: "Analysis", links: [["Performance", "/performance"], ["Risk", "/risk"], ["AMC intelligence", "/amc"]] },
  { title: "Research lab", links: [["Fund scoring", "/quant/scoring"], ["Factor research", "/quant/factors"], ["Regimes", "/quant/regimes"], ["Backtesting", "/quant/backtesting"]] },
  { title: "Portfolios", links: [["Builder", "/portfolio/builder"], ["Optimization", "/portfolio/optimization"], ["SIP / SWP", "/portfolio/sip-swp"], ["Stress testing", "/portfolio/stress-testing"]] },
];

/** Landing-page footer: site map and the standing disclaimer. */
export function LandingFooter() {
  return (
    <footer className="border-t border-line">
      <div className="app-container grid grid-cols-2 gap-8 py-10 md:grid-cols-5">
        <div className="col-span-2 md:col-span-1">
          <p className="text-[1rem] font-bold tracking-tight text-strong">Quant<span className="text-accent">Synthica</span></p>
          <p className="mt-2 text-xs leading-relaxed text-muted">Quantitative research for Indian mutual funds.</p>
        </div>
        {COLS.map((c) => (
          <nav key={c.title} aria-label={c.title}>
            <h3 className="font-mono text-[10px] uppercase tracking-wider text-muted">{c.title}</h3>
            <ul className="mt-3 space-y-2 text-xs">{c.links.map(([l, h]) => <li key={h}><Link href={h} className="text-fg transition-colors hover:text-accent focus-visible:ring-1 focus-visible:ring-accent/70 focus-visible:outline-none">{l}</Link></li>)}</ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-line/60">
        <div className="app-container flex flex-col gap-1 py-4 text-[11px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>Research tool, not investment advice. Past performance does not indicate future results.</span>
          <span>Mutual fund investments are subject to market risks. Times in IST.</span>
        </div>
      </div>
    </footer>
  );
}
