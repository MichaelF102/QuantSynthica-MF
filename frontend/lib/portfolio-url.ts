export const MAX_FUNDS = 40;

export function encode(p: { scheme_id: number; weight: number }[]) { return p.map((x) => `${x.scheme_id}:${+x.weight.toFixed(4)}`).join(","); }
export function decode(raw: string | undefined): { scheme_id: number; weight: number }[] {
  return (raw ?? "").split(",").map((t) => t.split(":")).map(([a, b]) => ({ scheme_id: Number(a), weight: Number(b ?? 1) }))
    .filter((x) => Number.isInteger(x.scheme_id) && x.scheme_id > 0 && Number.isFinite(x.weight) && x.weight >= 0).slice(0, MAX_FUNDS);
}

