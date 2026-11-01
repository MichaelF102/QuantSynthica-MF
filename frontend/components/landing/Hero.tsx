import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

/** Hero: the one-line promise, two ways in, and an honest one-line scope statement. */
export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative isolate overflow-hidden border-b border-line/60">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/4 top-0 h-72 w-[28rem] rounded-full bg-blue-600/15 blur-3xl" />
        <div className="absolute right-1/4 top-10 h-72 w-[28rem] rounded-full bg-indigo-600/15 blur-3xl" />
        <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "linear-gradient(var(--qs-fg) 1px, transparent 1px), linear-gradient(90deg, var(--qs-fg) 1px, transparent 1px)", backgroundSize: "56px 56px", maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)" }} />
      </div>
      <div className="app-container flex flex-col items-center py-20 text-center sm:py-28">
        <p className="rounded-full border border-line bg-panel/70 px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-muted">Quantitative research for Indian mutual funds</p>
        <h1 id="hero-title" className="mt-6 max-w-4xl text-4xl font-extrabold tracking-tight text-strong sm:text-6xl">
          Beyond Returns.{" "}
          <span className="block bg-gradient-to-r from-blue-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent">Into Intelligence.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-sm leading-relaxed text-muted sm:text-[1rem]">
          Judge a fund by the risk it took, how it behaved in falling markets and how it compares with true peers, not by one trailing-return number.
          Every figure is computed from official NAV records, shows its method and says plainly when data is missing.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/overview" className="group inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition-colors hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none">
            Launch the platform <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <a href="#methodology" className="inline-flex items-center gap-2 rounded-lg border border-line-strong/80 bg-panel px-6 py-3 text-sm font-medium text-fg transition-colors hover:bg-hover hover:text-strong focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none">
            <ShieldCheck className="h-4 w-4" /> How it works
          </a>
        </div>
        <p className="mt-6 text-[11px] text-faint">A research tool, not investment advice. Past performance does not indicate future results.</p>
      </div>
    </section>
  );
}
