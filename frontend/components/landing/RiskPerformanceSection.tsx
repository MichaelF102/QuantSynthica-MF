import Link from "next/link";
import { Activity, ArrowDownRight, Gauge, LineChart } from "lucide-react";
import { FeatureCard, SectionShell } from "./SectionShell";

const METRICS = [
  { group: "Returns", items: ["Trailing 1M to 10Y", "Calendar year", "Rolling 1Y, 3Y, 5Y", "CAGR", "Positive-month share"] },
  { group: "Risk", items: ["Volatility", "Downside deviation", "Maximum drawdown and recovery", "Beta and tracking error", "Correlation"] },
  { group: "Risk-adjusted", items: ["Sharpe", "Sortino", "Calmar", "Information ratio", "Alpha"] },
  { group: "Tail risk", items: ["Value at risk 95% and 99%", "Expected shortfall", "Skewness", "Excess kurtosis", "Downside capture"] },
];

/** Risk and performance analytics: what is measured and the conventions behind it. */
export function RiskPerformanceSection() {
  return (
    <SectionShell id="risk" eyebrow="Risk & performance analytics" title="See the risk" accent="behind the return" lead="Two funds with the same return can have very different drawdowns. Every window shows both, side by side.">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {METRICS.map((m) => (
          <div key={m.group} className="rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20">
            <h3 className="text-sm font-bold text-strong">{m.group}</h3>
            <ul className="mt-2 space-y-1.5 text-xs text-muted">{m.items.map((i) => <li key={i} className="flex gap-2"><span aria-hidden className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />{i}</li>)}</ul>
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <FeatureCard icon={Gauge} title="Stated conventions">252-day annualisation and a 365.25-day CAGR. The risk-free rate is a proxy built from overnight and liquid funds, labelled as such.</FeatureCard>
        <FeatureCard icon={Activity} title="Peer benchmark, not an index">The benchmark is the equal-weighted average of surviving funds in the same category and plan, excluding the fund itself.</FeatureCard>
        <FeatureCard icon={ArrowDownRight} title="Guards against bad data">Implausible NAV jumps are flagged, and ratios are withheld when volatility is too low to mean anything.</FeatureCard>
      </div>
      <p className="mt-4 text-xs text-muted"><LineChart className="mr-1.5 inline h-3.5 w-3.5" aria-hidden /><Link href="/performance" className="font-medium text-accent hover:underline">Open performance analytics</Link> or <Link href="/risk" className="font-medium text-accent hover:underline">risk analytics</Link>.</p>
    </SectionShell>
  );
}
