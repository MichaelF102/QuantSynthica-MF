import Link from "next/link";
import { ArrowRight } from "lucide-react";

/** Final call to action. */
export function FinalCTA() {
  return (
    <section aria-labelledby="cta-title" className="relative isolate overflow-hidden py-20 sm:py-24">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-1/2 h-64 w-[36rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600/15 blur-3xl" />
      </div>
      <div className="app-container text-center">
        <h2 id="cta-title" className="mx-auto max-w-3xl text-3xl font-extrabold tracking-tight text-strong sm:text-4xl">
          Start researching funds with{" "}
          <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent">evidence, not headlines</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-sm text-muted">Open the platform, pick a fund or build a portfolio, and see the method behind every number.</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/overview" className="group inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition-colors hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none">
            Launch the platform <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link href="/funds" className="inline-flex items-center rounded-lg border border-line-strong/80 bg-panel px-6 py-3 text-sm font-medium text-fg transition-colors hover:bg-hover hover:text-strong focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none">Browse funds</Link>
        </div>
      </div>
    </section>
  );
}
