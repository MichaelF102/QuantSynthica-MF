import Link from "next/link";
import { Activity, Gauge, Waves } from "lucide-react";
import { api, type Regimes } from "@/lib/api";
import { SectionShell } from "./SectionShell";

const label = (v: string | null | undefined) => (v ? v.charAt(0).toUpperCase() + v.slice(1) : "—");

/** Market regime intelligence: the current labels from the stored analysis, with a plain statement of what they can and cannot do. */
export async function MarketRegimeSection() {
  let r: Regimes | null = null;
  try { r = await api.quantRegimes(); } catch { r = null; }
  const cards = [
    { icon: Activity, title: "Trend regime", value: r?.current.trend, text: "Bull, bear or sideways from price versus its moving average, using only past data." },
    { icon: Waves, title: "Volatility regime", value: r?.current.volatility, text: "Low, normal or high from the realised volatility percentile at each date." },
    { icon: Gauge, title: "Hidden Markov state", value: r?.current.hmm, text: "A statistical model fitted only on earlier data; states are named by how volatile they are." },
  ];
  return (
    <SectionShell id="regimes" eyebrow="Market regime intelligence" title="Know the" accent="market's current mood" lead={r ? `Measured on ${r.proxy.charAt(0).toLowerCase()}${r.proxy.slice(1)}, as of ${r.end}.` : "Regime analysis is not available right now."}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {cards.map((c) => (
          <div key={c.title} className="rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-muted"><c.icon aria-hidden className="h-4 w-4 text-accent" />{c.title}</div>
            <p className="mt-2 font-mono text-2xl font-bold text-strong">{label(c.value)}</p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">{c.text}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted">
        These labels describe conditions; they do not time the market. In our test, periods labelled bear were not followed by worse returns, and an earlier version that looked ahead by a day was removed.
        <Link href="/quant/regimes" className="ml-1 font-medium text-accent hover:underline">See the regime analysis</Link>.
      </p>
    </SectionShell>
  );
}

export function MarketRegimeSkeleton() {
  return <SectionShell id="regimes" eyebrow="Market regime intelligence" title="Know the" accent="market's current mood"><div aria-busy="true" aria-label="Loading" className="h-40 animate-pulse rounded-xl bg-line/40" /></SectionShell>;
}
