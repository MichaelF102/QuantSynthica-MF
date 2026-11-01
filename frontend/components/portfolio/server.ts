import { api } from "@/lib/api";
import type { Pick } from "@/components/portfolio/PortfolioPicker";
import { decode } from "@/lib/portfolio-url";

export type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

/** Read ?p=id:weight,... and attach fund names (funds that are no longer usable are dropped). */
export async function loadPicks(sp: Awaited<SP>): Promise<{ picks: Pick[]; holdings: { scheme_id: number; weight: number }[]; dropped: number; raw: string }> {
  const raw = first(sp.p) ?? "";
  const parsed = decode(raw);
  if (!parsed.length) return { picks: [], holdings: [], dropped: 0, raw };
  const funds = await api.portfolioFundsByIds(parsed.map((x) => x.scheme_id)).catch(() => []);
  const byId = new Map(funds.map((f) => [f.scheme_id, f]));
  const picks = parsed.filter((x) => byId.has(x.scheme_id)).map((x) => ({ scheme_id: x.scheme_id, weight: x.weight, name: byId.get(x.scheme_id)!.name, category: byId.get(x.scheme_id)!.category }));
  return { picks, holdings: picks.map((p) => ({ scheme_id: p.scheme_id, weight: p.weight })), dropped: parsed.length - picks.length, raw };
}
