// Number formatting (DESIGN.md §9). A non-numeric value becomes "—".
export const dash = "—";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export const fmtPrice = (v: unknown) =>
  isNum(v) ? `₹${v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : dash;
export const fmtPct = (v: unknown, digits = 2, signed = true) => {
  if (!isNum(v)) return dash;
  const r = Number(v.toFixed(digits)); // avoid "-0.0%" for tiny negatives
  return `${signed && r > 0 ? "+" : ""}${(r === 0 ? 0 : v).toFixed(digits)}%`;
};
export const fmtInt = (v: unknown) => (isNum(v) ? v.toLocaleString("en-IN") : dash);
export const fmtNum = (v: unknown, digits = 2) =>
  isNum(v) ? v.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : dash;
/** Input in ₹ Cr: >= 1,00,000 Cr shown as ₹x.xxT (trillion). */
export const fmtCapCr = (v: unknown) =>
  !isNum(v) || v <= 0 ? dash : v >= 100000 ? `₹${(v / 100000).toFixed(2)}T` : `₹${Math.round(v).toLocaleString("en-IN")} Cr`;

// Compatibility wrappers used across pages
export const pct = fmtPct;
export const num = fmtNum;
export const price = fmtPrice;
/** Source net assets are in rupees; 1 Cr = 1e7. */
export const crore = (v: number | null | undefined) => (isNum(v) ? fmtCapCr(v / 1e7) : dash);
export const lakhCrore = (v: number | null | undefined) => (isNum(v) ? fmtCapCr(v / 1e7) : dash);
export const share = (v: number | null | undefined) => (isNum(v) ? `${Math.round(v * 100)}%` : dash);

export function tone(v: number | null | undefined): string {
  if (!isNum(v) || v === 0) return "text-fg";
  return v > 0 ? "text-up" : "text-down";
}

// Heatmap background for a return value (percent), muted so text stays readable.
export function heat(v: number | null | undefined, scale = 25): string {
  if (!isNum(v)) return "transparent";
  const t = Math.max(-1, Math.min(1, v / scale));
  return t >= 0 ? `rgba(16,185,129,${(0.08 + 0.5 * t).toFixed(2)})` : `rgba(244,63,94,${(0.08 + 0.5 * -t).toFixed(2)})`;
}
