"use client";

import Link from "next/link";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, ShieldCheck } from "lucide-react";
import GlowHorizonFM from "@/components/ui/glow-horizon";

/**
 * Hero: the one-line promise, two ways in, and an honest one-line scope statement.
 * The hero is always dark (the glow needs a dark ground), so it carries its own `dark` token scope.
 * While scrolling past it, each layer moves at a different speed (parallax): the glow drifts slowest,
 * the grid a little faster, the copy fastest and fades out.
 */
export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });

  const glowY = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "22%"]);
  const glowScale = useTransform(scrollYProgress, [0, 1], [1, reduce ? 1 : 1.12]);
  const gridY = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "38%"]);
  const copyY = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "-18%"]);
  const copyOpacity = useTransform(scrollYProgress, [0, 0.75], [1, reduce ? 1 : 0]);

  return (
    <section ref={ref} aria-labelledby="hero-title" className="dark relative isolate overflow-hidden border-b border-line/60 bg-[#050507]">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <motion.div className="absolute inset-0" style={{ y: gridY }}>
          <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "linear-gradient(var(--qs-fg) 1px, transparent 1px), linear-gradient(90deg, var(--qs-fg) 1px, transparent 1px)", backgroundSize: "56px 56px", maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)" }} />
        </motion.div>
        <motion.div className="absolute inset-0" style={{ y: glowY, scale: glowScale }}>
          <GlowHorizonFM variant="top" />
        </motion.div>
      </div>
      <motion.div style={{ y: copyY, opacity: copyOpacity }} className="app-container flex min-h-[calc(100svh-4rem)] flex-col items-center justify-center py-20 text-center sm:py-28">
        <p className="rounded-full border border-line bg-panel/70 px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-muted backdrop-blur">Quantitative research for Indian mutual funds</p>
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
      </motion.div>
    </section>
  );
}
