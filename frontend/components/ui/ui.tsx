import Link from "next/link";
import type { ComponentType, ReactNode } from "react";
import { AlertTriangle, Info, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "accent" | "up" | "down" | "warn" | "ai";
type Icon = ComponentType<{ className?: string }>;

const TILE: Record<Tone, string> = {
  accent: "bg-accent/10 border-accent/20 text-accent",
  up: "bg-up/10 border-up/20 text-up",
  down: "bg-down/10 border-down/20 text-down",
  warn: "bg-warn/10 border-warn/20 text-warn",
  ai: "bg-ai/15 border-ai/40 text-ai",
};

/** Card (DESIGN.md §7.1). */
export function Panel({ title, description, icon: IconC, tone = "accent", info, right, children, className }: {
  title?: string; description?: string; icon?: Icon; tone?: Tone; info?: string; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={cn("h-full rounded-xl border border-line bg-panel/95 p-4 shadow-lg shadow-black/20 backdrop-blur-md", className)}>
      {(title || right) && (
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            {IconC && <div className={cn("rounded-lg border p-1.5", TILE[tone])}><IconC className="h-4 w-4" /></div>}
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="text-sm font-bold tracking-wide text-strong">{title}</h2>
                {info && (
                  <button type="button" className="text-faint transition-colors hover:text-fg" title={info} aria-label={`About ${title}: ${info}`}>
                    <Info className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              {description && <p className="text-[11px] text-muted">{description}</p>}
            </div>
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/** KPI tile (§7.8). */
export function StatTile({ label, value, sub, valueClass, icon: IconC }: {
  label: string; value: string; sub?: string; valueClass?: string; icon?: Icon;
}) {
  return (
    <div className="rounded-xl border border-line bg-panel/95 p-3.5">
      <div className="mb-0.5 flex items-center gap-1 text-[10px] text-muted">{IconC && <IconC className="h-3 w-3" />}{label}</div>
      <div className={cn("font-mono text-lg font-bold text-strong", valueClass)}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

/** Page hero (§6.2, §4.5, §5). `accent` is the gradient word. */
export function PageHeader({ title, accent, subtitle, description, right }: {
  title: string; accent?: string; subtitle?: string; description?: string; right?: ReactNode;
}) {
  return (
    <header className="relative flex flex-col gap-4 border-b border-line/60 pb-5 lg:flex-row lg:items-end lg:justify-between">
      {/* glow blobs per DESIGN.md §4.5, clipped so they cannot cause horizontal page scroll on phones */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/4 top-0 h-24 w-96 rounded-full bg-blue-600/10 blur-3xl" />
        <div className="absolute right-1/4 top-0 h-24 w-96 rounded-full bg-indigo-600/10 blur-3xl" />
      </div>
      <div>
        {subtitle && <p className="text-xs font-semibold tracking-wide text-accent sm:text-sm">{subtitle}</p>}
        <h1 className="text-2xl font-extrabold tracking-tight text-strong sm:text-3xl">
          {title}{accent && <> <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent">{accent}</span></>}
        </h1>
        {description && <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted">{description}</p>}
      </div>
      {right}
    </header>
  );
}

/** Pill tab bar (§7.3). Link-based so state lives in the URL. */
export function PillTabs({ items, active }: { items: { key: string; label: string; href: string; muted?: boolean }[]; active: string }) {
  return (
    <div className="no-scrollbar w-full overflow-x-auto py-2">
      <nav aria-label="Sections" className="flex min-w-max items-center gap-1.5 rounded-xl border border-line bg-raised/80 p-1 backdrop-blur-md">
        {items.map((t) => (
          <Link key={t.key} href={t.href} aria-current={t.key === active ? "page" : undefined}
            className={cn("flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs",
              t.key === active ? "bg-blue-600 font-semibold text-white shadow-lg shadow-blue-600/30"
                : cn("font-medium hover:bg-hover hover:text-strong", t.muted ? "text-faint" : "text-muted"))}>
            {t.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

/** Segmented control (§7.4), link-based. */
export function SegmentedLinks({ items, active, label }: { items: { key: string; label: string; href: string }[]; active: string; label: string }) {
  return (
    <div role="group" aria-label={label} className="flex items-center rounded-lg border border-line bg-panel p-0.5">
      {items.map((i) => (
        <Link key={i.key} href={i.href} aria-current={i.key === active ? "true" : undefined}
          className={cn("rounded px-2.5 py-1 font-mono text-[11px]", i.key === active ? "bg-blue-600 font-semibold text-white shadow-sm" : "font-medium text-muted hover:text-strong")}>
          {i.label}
        </Link>
      ))}
    </div>
  );
}

/** Skeleton shell (§7.2). Never show zeros while loading. */
export function SkeletonPanel({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("h-full animate-pulse space-y-3 rounded-xl border border-line bg-panel/95 p-4", className)} aria-hidden>
      <div className="h-4 w-40 rounded bg-line" />
      <div className="space-y-2">{Array.from({ length: rows }, (_, i) => <div key={i} className="h-9 rounded bg-line/50" />)}</div>
    </div>
  );
}

/** Alerts (§7.12). */
export function Banner({ tone = "warn", children, action }: { tone?: "warn" | "down" | "accent"; children: ReactNode; action?: ReactNode }) {
  const c = { warn: "border-warn/30 bg-warn/10 text-warn", down: "border-down/30 bg-down/10 text-down", accent: "border-accent/30 bg-accent/10 text-accent" }[tone];
  return (
    <div role={tone === "down" ? "alert" : "status"} className={cn("flex items-center justify-between gap-3 rounded-lg border p-3 text-xs", c)}>
      <span className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{children}</span>
      {action}
    </div>
  );
}

/** Empty state (§7.13): say what is missing and why. */
export function EmptyState({ title, hint, icon: IconC = Inbox }: { title: string; hint?: string; icon?: Icon }) {
  return (
    <div className="flex flex-col items-center gap-1 py-10 text-center">
      <IconC className="mb-1 h-8 w-8 text-faint" />
      <p className="text-sm text-fg">{title}</p>
      {hint && <p className="text-xs text-faint">{hint}</p>}
    </div>
  );
}

/** Input class strings (§7.9). */
export const inputCls = "rounded-lg border border-line-strong/60 bg-raised px-2.5 py-1.5 text-xs text-strong outline-none placeholder:text-faint hover:border-line-strong focus:border-accent";
export const btnPrimary = "inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-blue-600/20 hover:bg-blue-500 disabled:opacity-50";
export const btnSecondary = "inline-flex items-center gap-1.5 rounded-lg border border-line-strong/80 bg-panel px-3 py-1.5 text-xs font-medium text-fg hover:border-line-strong hover:bg-hover hover:text-strong disabled:opacity-50";

/** Horizontal bar row for distributions. */
export function BarRow({ label, value, max, text, color = "bg-accent" }: { label: string; value: number; max: number; text: string; color?: string }) {
  const w = max > 0 ? Math.max(1, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 py-1 text-xs">
      <div className="w-28 shrink-0 truncate text-muted" title={label}>{label}</div>
      <div className="h-2.5 flex-1 rounded bg-raised"><div className={cn("h-2.5 rounded", color)} style={{ width: `${w}%` }} /></div>
      <div className="w-20 shrink-0 text-right font-mono">{text}</div>
    </div>
  );
}
