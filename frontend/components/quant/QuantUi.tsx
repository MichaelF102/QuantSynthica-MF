import type { ReactNode } from "react";
import { FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import { dash } from "@/lib/format";

/** Purple is reserved for the Quant Lab and AI (DESIGN.md §1.3). */
export function LabKicker({ children = "QUANT RESEARCH LAB" }: { children?: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-ai"><FlaskConical className="h-3 w-3" />{children}</span>;
}

export function scoreColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "transparent";
  const t = Math.max(0, Math.min(100, v)) / 100;
  return t >= 0.5 ? `rgba(16,185,129,${(0.1 + 0.5 * (t - 0.5) * 2).toFixed(2)})` : `rgba(244,63,94,${(0.1 + 0.5 * (0.5 - t) * 2).toFixed(2)})`;
}

export function ScorePill({ v, digits = 1, className }: { v: number | null | undefined; digits?: number; className?: string }) {
  return (
    <span className={cn("inline-block min-w-[3.25rem] rounded px-2 py-0.5 text-center font-mono text-xs font-bold text-strong", className)} style={{ background: scoreColor(v) }}>
      {v === null || v === undefined ? dash : v.toFixed(digits)}
    </span>
  );
}

export function FactorBar({ v, label }: { v: number | null | undefined; label?: string }) {
  if (v === null || v === undefined) return <span className="text-faint" title={label ? `${label}: not available` : undefined}>{dash}</span>;
  return (
    <span className="flex items-center gap-1.5" title={label ? `${label}: ${v.toFixed(0)}` : undefined}>
      <span className="h-1.5 w-14 rounded bg-raised"><span className="block h-1.5 rounded bg-ai" style={{ width: `${Math.max(2, Math.min(100, v))}%` }} /></span>
      <span className="w-6 text-right font-mono text-[11px]">{v.toFixed(0)}</span>
    </span>
  );
}

export const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

export function Caveats({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1 text-[11px] text-faint">
      {items.map((c) => <li key={c}>• {c}</li>)}
    </ul>
  );
}
