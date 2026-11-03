"use client";

import type { ReactNode } from "react";
import { clsx } from "clsx";
import { motion, useReducedMotion } from "framer-motion";

/**
 * Bento card: a diagram area on a slightly raised surface, then the text.
 * Adapted from the supplied component to the QuantSynthica tokens (DESIGN.md): theme colours, hairline borders,
 * no remote images. It rises into place once on scroll; on hover a light rim circles the border, a soft spotlight
 * follows the cursor and the card tilts a few degrees (styles in globals.css, `.qs-card`).
 */
export function BentoCard({ id, tone = "accent", className, eyebrow, title, description, graphic, delay = 0 }: {
  id?: string;
  tone?: "accent" | "ai";
  className?: string;
  eyebrow: ReactNode;
  title: ReactNode;
  description: ReactNode;
  graphic?: ReactNode;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <div
      id={id}
      className={clsx("scroll-mt-28", className)}
      style={{ transition: "transform .4s cubic-bezier(.2,.8,.2,1)" }}
      onMouseMove={(e) => {
        const el = e.currentTarget, r = el.getBoundingClientRect();
        const x = e.clientX - r.left, y = e.clientY - r.top;
        el.style.setProperty("--mx", `${x}px`);
        el.style.setProperty("--my", `${y}px`);
        if (!reduce) el.style.transform = `perspective(1000px) rotateX(${(y / r.height - 0.5) * -3}deg) rotateY(${(x / r.width - 0.5) * 3}deg) translateY(-2px)`;
      }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = ""; }}
    >
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "0px 0px -60px 0px" }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay }}
        data-tone={tone}
        className="qs-card group flex h-full flex-col overflow-hidden rounded-xl border border-line bg-panel"
      >
        <div aria-hidden className="relative h-44 shrink-0 border-b border-line/70 bg-raised/60">{graphic}</div>
        <div className="flex-1 p-5">
          <p className={clsx("font-mono text-[10px] uppercase tracking-wider", tone === "ai" ? "text-ai" : "text-accent")}>{eyebrow}</p>
          <h3 className="mt-1.5 text-base font-semibold tracking-tight text-strong">{title}</h3>
          <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-muted">{description}</p>
        </div>
      </motion.div>
    </div>
  );
}
