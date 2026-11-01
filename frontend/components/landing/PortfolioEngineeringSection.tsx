import Link from "next/link";
import { CalendarClock, Layers, PieChart, Scale, Target, Zap } from "lucide-react";
import { FeatureCard, SectionShell } from "./SectionShell";

/** Portfolio engineering: builders, optimisers, simulators, rebalancing and stress tests, with the limits stated. */
export function PortfolioEngineeringSection() {
  return (
    <SectionShell id="portfolio" eyebrow="Portfolio engineering" title="From a list of funds to" accent="a portfolio you understand" lead="Pick up to 40 Growth funds and see how the mix behaves, where its risk really comes from, and how different weighting rules change it.">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <FeatureCard icon={PieChart} title="Builder and analytics">Weights, allocation by category and tier, risk contribution per fund, correlation and effective number of funds.</FeatureCard>
        <FeatureCard icon={Target} title="Optimisation">Minimum variance, maximum Sharpe, risk parity, minimum CVaR and Black-Litterman, with weight, category and fund-count limits and an efficient frontier.</FeatureCard>
        <FeatureCard icon={Layers} title="SIP, SWP and lump sum">Replay a plan on real NAV history, see the spread of outcomes across start dates, or run a clearly labelled hypothetical projection.</FeatureCard>
        <FeatureCard icon={Scale} title="Rebalancing">Enter what you hold; get the buys and sells that return you to target, with transaction cost and exit-load estimates.</FeatureCard>
        <FeatureCard icon={Zap} title="Stress testing">How the mix behaved in the worst falls found in the data, plus beta-based market-shock illustrations.</FeatureCard>
        <FeatureCard icon={CalendarClock} title="Out-of-sample check">Each optimisation is fitted before the last twelve months and tested on them, and the page warns when equal weight did better.</FeatureCard>
      </div>
      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted">
        Expected returns are shrunk historical averages, not forecasts. Historical results and hypothetical projections are always labelled apart, and taxes are not modelled.
        <Link href="/portfolio/builder" className="ml-1 font-medium text-accent hover:underline">Open the portfolio builder</Link>.
      </p>
    </SectionShell>
  );
}
