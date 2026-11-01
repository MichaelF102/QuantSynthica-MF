import Link from "next/link";
import { BookCheck, Ban, ListChecks, Sparkles } from "lucide-react";
import { FeatureCard, SectionShell } from "./SectionShell";

/** AI research assistant. The example shows the SHAPE of an answer; it contains no numbers because it is not a real answer. */
export function AIAssistantSection() {
  return (
    <SectionShell id="assistant" tone="ai" eyebrow="AI research assistant" title="Ask in plain English." accent="Get sourced answers." lead="The assistant looks things up in the platform's own calculations. It never writes a figure that is not in a tool result.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-xl border border-purple-500/30 bg-panel/95 p-4 shadow-[0_0_14px_rgba(168,85,247,0.15)] lg:col-span-6" role="img" aria-label="Illustration of the structure of an assistant answer">
          <div className="mb-3 flex items-center gap-2 text-xs text-ai"><Sparkles aria-hidden className="h-4 w-4" />Example of the answer format</div>
          <p className="text-xs font-semibold text-strong">&ldquo;How risky is &lt;fund name&gt;?&rdquo;</p>
          <div className="mt-3 rounded-lg border border-line bg-raised p-3 text-xs">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted">Facts</p>
            <ul className="mt-1 divide-y divide-line/50">
              {["3Y volatility", "3Y maximum drawdown", "3Y Sharpe ratio"].map((l) => (
                <li key={l} className="flex items-center justify-between gap-3 py-1.5"><span>{l}</span><span className="font-mono text-faint">value · source · as-of date</span></li>
              ))}
            </ul>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-muted">Not available</p>
            <p className="mt-1 text-muted">Anything it cannot compute is listed here with the reason.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-6">
          <FeatureCard tone="ai" icon={BookCheck} title="Every figure has a source">Value, unit, calculation date and the tool that produced it.</FeatureCard>
          <FeatureCard tone="ai" icon={ListChecks} title="Checked before it is shown">Any model-written explanation is discarded if it contains a number that is not among the sourced facts.</FeatureCard>
          <FeatureCard tone="ai" icon={Ban} title="No advice, no predictions">Questions like &ldquo;should I buy&rdquo; are declined and redirected to facts.</FeatureCard>
          <FeatureCard tone="ai" icon={Sparkles} title="Honest about gaps">If a fund has no linked NAV history, it says so instead of estimating.</FeatureCard>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted">Available to signed-in users. <Link href="/assistant" className="font-medium text-ai hover:underline">Open the assistant</Link>.</p>
    </SectionShell>
  );
}
