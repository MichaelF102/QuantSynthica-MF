import type { ReactNode } from "react";

/** Shared section frame for the landing page: anchor id, eyebrow, title with an optional gradient word, lead paragraph. */
export function SectionShell({ id, eyebrow, title, accent, lead, tone = "accent", children }: {
  id: string; eyebrow: string; title: string; accent?: string; lead?: string; tone?: "accent" | "ai"; children: ReactNode;
}) {
  const grad = tone === "ai" ? "from-purple-400 via-fuchsia-400 to-indigo-400" : "from-blue-400 via-indigo-400 to-cyan-400";
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 border-b border-line/50 py-16 sm:py-20">
      <div className="app-container">
        <div className="mb-10 max-w-3xl">
          <p className={`font-mono text-[10px] uppercase tracking-wider ${tone === "ai" ? "text-ai" : "text-muted"}`}>{eyebrow}</p>
          <h2 id={`${id}-title`} className="mt-2 text-2xl font-extrabold tracking-tight text-strong sm:text-4xl">
            {title}{accent && <> <span className={`bg-gradient-to-r ${grad} bg-clip-text text-transparent`}>{accent}</span></>}
          </h2>
          {lead && <p className="mt-3 text-sm leading-relaxed text-muted">{lead}</p>}
        </div>
        {children}
      </div>
    </section>
  );
}

/** Small card used across landing sections. */
export function FeatureCard({ icon: Icon, title, children, tone = "accent" }: {
  icon: React.ComponentType<{ className?: string }>; title: string; children: ReactNode; tone?: "accent" | "ai";
}) {
  return (
    <div className="group rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20 transition-colors hover:border-line-strong">
      <div className={`mb-3 inline-flex rounded-lg p-1.5 ${tone === "ai" ? "bg-purple-500/10 text-ai" : "bg-blue-500/10 text-accent"}`}><Icon className="h-4 w-4" /></div>
      <h3 className="text-sm font-bold tracking-wide text-strong">{title}</h3>
      <div className="mt-1.5 text-xs leading-relaxed text-muted">{children}</div>
    </div>
  );
}
