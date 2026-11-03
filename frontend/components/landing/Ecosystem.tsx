import { AnalyticsGraphic, AssistantGraphic, DataGraphic, EngineGraphic, PortfolioGraphic, ReportsGraphic } from "./EcosystemGraphics";
import { EcosystemPipeline } from "./EcosystemPipeline";
import { SectionShell } from "./SectionShell";
import { BentoCard } from "@/components/ui/bento";

// Spans on the 6-column grid: rows of 4+2, 2+4 and 3+3, in the order data flows.
const STAGES = [
  { short: "Data", title: "Data layer", text: "Official scheme register and daily NAV history, mapped to fund profiles, checked and stored with provenance.", span: "lg:col-span-4", graphic: DataGraphic },
  { short: "Engine", title: "Quant engine", text: "One tested library computes returns, risk, scores, factor research, regimes and backtests.", span: "lg:col-span-2", graphic: EngineGraphic },
  { short: "Analytics", title: "Analytics", text: "Fund pages, comparison, screener and AMC views that read from the engine, never re-derive numbers.", span: "lg:col-span-2", graphic: AnalyticsGraphic },
  { short: "Lab", title: "Portfolio lab", text: "Builders, optimisers, SIP/SWP simulators, rebalancing and stress tests on your own mix.", span: "lg:col-span-4", graphic: PortfolioGraphic },
  { short: "Assistant", title: "AI assistant", text: "Answers assembled from the same calculations, with the source and date of every figure.", span: "lg:col-span-3", graphic: AssistantGraphic, ai: true },
  { short: "Reports", title: "Reports", text: "PDF and Excel exports built from the same functions as the screens, tested to match.", span: "lg:col-span-3", graphic: ReportsGraphic },
];

/** QuantSynthica ecosystem: how the pieces connect, in the order data flows. */
export function Ecosystem() {
  return (
    <SectionShell id="ecosystem" eyebrow="QuantSynthica ecosystem" title="One engine," accent="every view" lead="Each layer reads from the one below it, so a number on a fund page, in a report and in an assistant answer comes from the same calculation.">
      <EcosystemPipeline stages={STAGES.map((s, i) => ({ id: `layer-${i + 1}`, label: s.short, ai: s.ai }))} />
      <ol className="grid grid-cols-1 gap-4 lg:grid-cols-6">
        {STAGES.map((s, i) => (
          <li key={s.title} className={`flex ${s.span}`}>
            <BentoCard id={`layer-${i + 1}`} className="w-full" tone={s.ai ? "ai" : "accent"} eyebrow={`Layer 0${i + 1}`} title={s.title} description={s.text} delay={(i % 2) * 0.08} graphic={<s.graphic />} />
          </li>
        ))}
      </ol>
      <div className="mt-6 flex items-center gap-3.5 font-mono text-[11px] text-faint">
        <span className="text-muted">06 layers</span><span aria-hidden className="h-px flex-1 bg-gradient-to-r from-line to-transparent" /><span>one calculation</span>
      </div>
    </SectionShell>
  );
}
