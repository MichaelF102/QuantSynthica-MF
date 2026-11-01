import { ArrowRight, Brain, Calculator, Database, FileText, LineChart, Wallet } from "lucide-react";
import { SectionShell } from "./SectionShell";

const STAGES = [
  { icon: Database, title: "Data layer", text: "Official scheme register and daily NAV history, mapped to fund profiles, checked and stored with provenance." },
  { icon: Calculator, title: "Quant engine", text: "One tested library computes returns, risk, scores, factor research, regimes and backtests." },
  { icon: LineChart, title: "Analytics", text: "Fund pages, comparison, screener and AMC views that read from the engine, never re-derive numbers." },
  { icon: Wallet, title: "Portfolio lab", text: "Builders, optimisers, SIP/SWP simulators, rebalancing and stress tests on your own mix." },
  { icon: Brain, title: "AI assistant", text: "Answers assembled from the same calculations, with the source and date of every figure.", ai: true },
  { icon: FileText, title: "Reports", text: "PDF and Excel exports built from the same functions as the screens, tested to match." },
];

/** QuantSynthica ecosystem: how the pieces connect, in the order data flows. */
export function Ecosystem() {
  return (
    <SectionShell id="ecosystem" eyebrow="QuantSynthica ecosystem" title="One engine," accent="every view" lead="Each layer reads from the one below it, so a number on a fund page, in a report and in an assistant answer comes from the same calculation.">
      <ol className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
        {STAGES.map((s, i) => (
          <li key={s.title} className="relative rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20">
            <div className="mb-3 flex items-center justify-between">
              <span className={`inline-flex rounded-lg p-1.5 ${s.ai ? "bg-purple-500/10 text-ai" : "bg-blue-500/10 text-accent"}`}><s.icon className="h-4 w-4" /></span>
              <span className="font-mono text-[10px] text-faint">0{i + 1}</span>
            </div>
            <h3 className="text-sm font-bold text-strong">{s.title}</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">{s.text}</p>
            {i < STAGES.length - 1 && <ArrowRight aria-hidden className="absolute -right-2.5 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-faint xl:block" />}
          </li>
        ))}
      </ol>
    </SectionShell>
  );
}
