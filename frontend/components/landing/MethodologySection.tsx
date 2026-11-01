import Link from "next/link";
import { AlertTriangle, FileCheck2, GitBranch, Microscope } from "lucide-react";
import { FeatureCard, SectionShell } from "./SectionShell";

const LIMITS = [
  "Survivorship bias: only funds that exist today are included, which flatters category averages and rankings.",
  "No licensed index: benchmarks are category averages and the risk-free rate is a proxy from overnight and liquid funds.",
  "Only Growth options with a confirmed link to official records are analysed, because IDCW NAVs leave out payouts.",
  "In backtests no selection rule, including the composite score, beat the benchmark after costs. The score is not a prediction.",
  "Category labels are today's labels, not point-in-time; taxes are not modelled.",
];

/** Research methodology and transparency: what is versioned and tested, and the limits stated up front. */
export function MethodologySection() {
  return (
    <SectionShell id="methodology" eyebrow="Research methodology & transparency" title="We show our work," accent="including the limits" lead="Trust comes from being able to check. Here is what is versioned, what is tested, and where the method is weak.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-7">
          <FeatureCard icon={GitBranch} title="Versioned methods">Every metric, score, optimiser and simulator carries a methodology version, shown with the result.</FeatureCard>
          <FeatureCard icon={Microscope} title="Point-in-time research">Past scores, regime labels and trades are tested to be unchanged when future data is altered.</FeatureCard>
          <FeatureCard icon={FileCheck2} title="Reports match screens">Excel and PDF reports come from the same functions as the dashboards, and a test compares them number by number.</FeatureCard>
          <FeatureCard icon={FileCheck2} title="Missing means missing">A dash and a reason, never a placeholder, a zero or an invented value.</FeatureCard>
        </div>
        <div className="rounded-xl border border-amber-500/30 bg-panel/95 p-4 shadow-lg shadow-black/20 lg:col-span-5">
          <h3 className="flex items-center gap-2 text-sm font-bold text-strong"><AlertTriangle aria-hidden className="h-4 w-4 text-warn" />Known limitations</h3>
          <ul className="mt-3 space-y-2 text-xs leading-relaxed text-muted">{LIMITS.map((l) => <li key={l} className="flex gap-2"><span aria-hidden className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warn" />{l}</li>)}</ul>
          <p className="mt-3 text-xs"><Link href="/coverage" className="font-medium text-accent hover:underline">See data coverage</Link></p>
        </div>
      </div>
    </SectionShell>
  );
}
