import Link from "next/link";
import { ArrowUpRight, BarChart3, Building2, FlaskConical, GitCompare, Layers, ListFilter, ShieldAlert, Sparkles, Table2, Wallet } from "lucide-react";
import { SectionShell } from "./SectionShell";

const AREAS = [
  { href: "/overview", icon: BarChart3, title: "Market overview", text: "Universe, categories and top performers at a glance." },
  { href: "/funds", icon: Table2, title: "Fund explorer", text: "Search and filter every fund, then open a full profile." },
  { href: "/screener", icon: ListFilter, title: "Screener", text: "Filter by category, risk and the QuantSynthica score." },
  { href: "/comparison", icon: GitCompare, title: "Comparison", text: "Up to five funds side by side, with correlation." },
  { href: "/performance", icon: Layers, title: "Performance analytics", text: "Trailing, rolling and calendar-year returns." },
  { href: "/risk", icon: ShieldAlert, title: "Risk analytics", text: "Volatility, drawdown, tail risk and downside measures." },
  { href: "/quant/scoring", icon: FlaskConical, title: "Quant research lab", text: "Scoring, factor research, clustering, regimes, backtests.", ai: true },
  { href: "/portfolio/builder", icon: Wallet, title: "Portfolios", text: "Build, optimise, simulate, rebalance and stress-test." },
  { href: "/amc", icon: Building2, title: "AMC intelligence", text: "Fund houses compared by the median fund, not the best one." },
  { href: "/assistant", icon: Sparkles, title: "AI research assistant", text: "Ask questions; get sourced answers.", ai: true },
];

/** Explore the platform: direct links into every working area. */
export function ExplorePlatform() {
  return (
    <SectionShell id="explore" eyebrow="Explore the platform" title="Everything is" accent="one click away" lead="Every card opens a working page, not a mock-up.">
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {AREAS.map((a) => (
          <li key={a.href}>
            <Link href={a.href} className="group flex h-full flex-col rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20 transition-colors hover:border-line-strong hover:bg-hover focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none">
              <div className="mb-3 flex items-center justify-between">
                <span className={`inline-flex rounded-lg p-1.5 ${a.ai ? "bg-purple-500/10 text-ai" : "bg-blue-500/10 text-accent"}`}><a.icon className="h-4 w-4" /></span>
                <ArrowUpRight aria-hidden className="h-4 w-4 text-faint transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-strong" />
              </div>
              <h3 className="text-sm font-bold text-strong">{a.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted">{a.text}</p>
            </Link>
          </li>
        ))}
      </ul>
    </SectionShell>
  );
}
