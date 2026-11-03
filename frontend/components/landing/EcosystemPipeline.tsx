"use client";

/** Six-step flow strip above the cards. A light travels along it; clicking a step scrolls to that layer and flashes it. */
export function EcosystemPipeline({ stages }: { stages: { id: string; label: string; ai?: boolean }[] }) {
  const go = (id: string) => (e: React.MouseEvent) => {
    const el = document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    const card = el.querySelector(".qs-card");
    card?.classList.add("qs-flash");
    setTimeout(() => card?.classList.remove("qs-flash"), 1400);
  };
  return (
    <nav aria-label="Data flow" className="relative mb-6 hidden grid-cols-6 gap-2.5 md:grid">
      <div aria-hidden className="absolute inset-x-[6%] top-1/2 h-px bg-gradient-to-r from-accent/10 via-accent/50 to-ai/50" />
      <span aria-hidden className="qs-travel pointer-events-none absolute top-1/2 h-1.5 w-14 -translate-y-1/2 rounded-full bg-white/80 blur-[3px]" style={{ animation: "qs-travel 3.2s linear infinite" }} />
      {stages.map((s, i) => (
        <a key={s.id} href={`#${s.id}`} onClick={go(s.id)} className={`relative z-10 rounded-lg border border-line bg-panel px-3 py-2.5 text-center transition-all duration-200 hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:outline-none ${s.ai ? "hover:border-purple-500/50 hover:text-ai" : "hover:border-blue-500/50 hover:text-accent"}`}>
          <span className="block font-mono text-[10px] text-faint">0{i + 1}</span>
          <span className="mt-1 block text-xs font-semibold text-strong">{s.label}</span>
        </a>
      ))}
    </nav>
  );
}
