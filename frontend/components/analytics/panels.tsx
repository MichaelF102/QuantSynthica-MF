import { Activity, BarChart3, CalendarRange, Gauge, LineChart as LineIcon, ShieldAlert, Waves } from "lucide-react";
import { Banner, Panel } from "@/components/ui/ui";
import { DrawdownChart, LineChartMulti, SERIES, YearBars, type Series } from "@/components/charts/ChartKit";
import type { Analytics, MetricT, RiskBlock } from "@/lib/api";
import { dash, fmtInt, fmtPct, tone } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

/** A metric value with its note as a tooltip. Missing values render as an em dash. */
export function Val({ m, digits = 2, pct = false, signed = false, colour = false }: {
  m?: MetricT | null; digits?: number; pct?: boolean; signed?: boolean; colour?: boolean;
}) {
  if (!m || m.value === null) return <span className="text-faint" title={m?.note ?? "Not available"}>{dash}</span>;
  const text = pct ? fmtPct(m.value, digits, signed) : m.value.toFixed(digits);
  const title = `${m.window_start ?? ""} to ${m.window_end ?? ""} · ${fmtInt(m.n_obs)} observations`;
  return <span title={title} className={colour ? tone(m.value) : undefined}>{text}</span>;
}

export function Unavailable({ a }: { a: Analytics }) {
  return <Banner tone="accent"><span><strong>NAV analytics are not available for this fund.</strong> {a.reason}</span></Banner>;
}

export function DataIssues({ a }: { a: Analytics }) {
  if (!a.data_issues?.length) return null;
  return (
    <Banner tone="warn">
      <span>Data issue: NAV moved {a.data_issues.map((d) => `${d.move_pct > 0 ? "+" : ""}${d.move_pct}% on ${d.date}`).join(", ")} in one day
        (probable unit split or data error). Windows containing it are not reported until verified.</span>
    </Banner>
  );
}

export function Provenance({ a }: { a: Analytics }) {
  return (
    <p className="text-[11px] text-faint">
      Methodology {a.methodology_version}. Daily NAV returns, 252-day annualisation, data {a.data_window?.start} to {a.data_window?.end}
      ({fmtInt(a.data_window?.observations)} observations).{a.risk_free_label ? ` Risk-free: ${a.risk_free_label}.` : " No risk-free rate available: 0% assumed."}
      {a.benchmark_label ? ` Benchmark: ${a.benchmark_label}.` : ""}
    </p>
  );
}

const TRAIL = ["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "10y"];
const TRAIL_LABEL: Record<string, string> = { "1m": "1 month", "3m": "3 months", "6m": "6 months", ytd: "Year to date", "1y": "1 year", "3y": "3 years (p.a.)", "5y": "5 years (p.a.)", "10y": "10 years (p.a.)" };

export function TrailingTable({ funds }: { funds: Analytics[] }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead><tr className="border-b border-line"><th className={TH}>Period</th>
          {funds.map((f) => <th key={f.scheme_id} className={`${TH} text-right`}>{f.name}</th>)}</tr></thead>
        <tbody className="divide-y divide-line/50">
          {TRAIL.map((k) => (
            <tr key={k} className="transition-colors hover:bg-hover">
              <td className="px-2 py-2 text-muted">{TRAIL_LABEL[k]}</td>
              {funds.map((f) => <td key={f.scheme_id} className="px-2 py-2 text-right font-semibold"><Val m={f.trailing_returns?.[k]} pct signed colour /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CalendarPanel({ funds, height = 288 }: { funds: Analytics[]; height?: number }) {
  const years = [...new Set(funds.flatMap((f) => (f.calendar_returns ?? []).map((c) => c.year)))].sort();
  const series = funds.map((f) => ({
    key: `f${f.scheme_id}`, name: f.name,
    values: Object.fromEntries((f.calendar_returns ?? []).map((c) => [c.year, { v: c.return, partial: c.partial }])),
  }));
  return (
    <Panel icon={CalendarRange} title="Calendar-year returns" description="Last NAV of the year vs last NAV of the prior year; dimmed bars are partial years"
      info="The first year starts at the fund's first available NAV and the current year is year to date.">
      <YearBars years={years} series={series} height={height} />
      <div className="mt-3 w-full overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead><tr className="border-b border-line"><th className={TH}>Year</th>{funds.map((f) => <th key={f.scheme_id} className={`${TH} text-right`}>{f.name}</th>)}</tr></thead>
          <tbody className="divide-y divide-line/50">
            {[...years].reverse().map((y) => (
              <tr key={y} className="transition-colors hover:bg-hover">
                <td className="px-2 py-1.5 text-muted">{y}</td>
                {funds.map((f) => {
                  const c = f.calendar_returns?.find((x) => x.year === y);
                  return <td key={f.scheme_id} className={`px-2 py-1.5 text-right font-semibold ${c ? tone(c.return) : "text-faint"}`}>{c ? `${fmtPct(c.return)}${c.partial ? " *" : ""}` : dash}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[11px] text-faint">* partial year</p>
      </div>
    </Panel>
  );
}

export function RollingPanel({ funds }: { funds: Analytics[] }) {
  const rows: [string, "1y" | "3y"][] = [["1-year rolling", "1y"], ["3-year rolling (p.a.)", "3y"]];
  return (
    <Panel icon={Activity} title="Rolling returns" description="Distribution of returns over every trailing window ending on each observation date"
      info="A rolling return shows how often and by how much a fund delivered, independent of the start date chosen.">
      {rows.map(([label, k]) => (
        <div key={k} className="mb-4 w-full overflow-x-auto">
          <h3 className="mb-1 text-xs font-semibold text-strong">{label}</h3>
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>Windows</th>
              <th className={`${TH} text-right`}>Median</th><th className={`${TH} text-right`}>5th pct</th><th className={`${TH} text-right`}>95th pct</th>
              <th className={`${TH} text-right`}>Worst</th><th className={`${TH} text-right`}>Best</th>
              <th className={`${TH} text-right`}>% positive</th><th className={`${TH} text-right`}>% beating category avg</th></tr></thead>
            <tbody className="divide-y divide-line/50">
              {funds.map((f) => {
                const r = f.rolling?.[k];
                return (
                  <tr key={f.scheme_id} className="transition-colors hover:bg-hover">
                    <td className="max-w-[240px] truncate px-2 py-2 font-medium text-fg">{f.name}</td>
                    <td className="px-2 py-2 text-right text-muted">{r ? fmtInt(r.n) : dash}</td>
                    <td className="px-2 py-2 text-right font-semibold">{r?.median == null ? dash : fmtPct(r.median)}</td>
                    <td className="px-2 py-2 text-right">{r?.p5 == null ? dash : fmtPct(r.p5)}</td>
                    <td className="px-2 py-2 text-right">{r?.p95 == null ? dash : fmtPct(r.p95)}</td>
                    <td className="px-2 py-2 text-right">{r?.worst == null ? dash : fmtPct(r.worst)}</td>
                    <td className="px-2 py-2 text-right">{r?.best == null ? dash : fmtPct(r.best)}</td>
                    <td className="px-2 py-2 text-right">{r?.pct_positive == null ? dash : `${r.pct_positive.toFixed(0)}%`}</td>
                    <td className="px-2 py-2 text-right"><Val m={r?.pct_outperform_benchmark} digits={0} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </Panel>
  );
}

const RISK_ROWS: { key: keyof RiskBlock; label: string; digits?: number; pct?: boolean; help?: string }[] = [
  { key: "cagr", label: "Return (CAGR)", pct: true },
  { key: "volatility", label: "Annualised volatility", pct: true },
  { key: "downside_deviation", label: "Downside deviation", pct: true, help: "Annualised, below 0% per period" },
  { key: "sharpe_ratio", label: "Sharpe ratio", help: "Excess return over the risk-free proxy per unit of volatility" },
  { key: "sortino_ratio", label: "Sortino ratio", help: "Excess return per unit of downside deviation" },
  { key: "max_drawdown", label: "Maximum drawdown", pct: true },
  { key: "calmar_ratio", label: "Calmar ratio", help: "CAGR divided by absolute maximum drawdown" },
  { key: "var_95", label: "1-day VaR 95% (historical)", pct: true },
  { key: "cvar_95", label: "1-day CVaR 95%", pct: true, help: "Average loss on the worst 5% of days" },
  { key: "var_99", label: "1-day VaR 99% (historical)", pct: true },
  { key: "cvar_99", label: "1-day CVaR 99%", pct: true },
  { key: "var_param_95", label: "1-day VaR 95% (normal)", pct: true },
  { key: "skewness", label: "Skewness" },
  { key: "excess_kurtosis", label: "Excess kurtosis" },
];

/** Metrics table. `blocks` are the columns (windows of one fund, or one window of several funds). */
export function RiskTable({ columns, rows = RISK_ROWS }: { columns: { label: string; block: RiskBlock | undefined }[]; rows?: typeof RISK_ROWS }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead><tr className="border-b border-line"><th className={TH}>Metric</th>
          {columns.map((c) => <th key={c.label} className={`${TH} text-right`}>{c.label}</th>)}</tr></thead>
        <tbody className="divide-y divide-line/50">
          {rows.map((r) => (
            <tr key={r.key} className="transition-colors hover:bg-hover">
              <td className="px-2 py-2 text-muted" title={r.help}>{r.label}</td>
              {columns.map((c) => (
                <td key={c.label} className="px-2 py-2 text-right font-semibold">
                  {c.block?.available ? <Val m={c.block[r.key] as MetricT | undefined} pct={r.pct} digits={2} colour={r.key === "cagr"} />
                    : <span className="text-faint" title={c.block?.reason}>{dash}</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {columns.some((c) => c.block && !c.block.available) && (
        <p className="mt-2 text-[11px] text-faint">{dash} Not available: {[...new Set(columns.filter((c) => c.block && !c.block.available).map((c) => c.block?.reason))].join("; ")}.</p>
      )}
    </div>
  );
}

export const TAIL_ROWS = RISK_ROWS.filter((r) => ["var_95", "cvar_95", "var_99", "cvar_99", "var_param_95", "skewness", "excess_kurtosis"].includes(r.key as string));
export const OVERVIEW_ROWS = RISK_ROWS.filter((r) => ["cagr", "volatility", "downside_deviation", "sharpe_ratio", "sortino_ratio", "max_drawdown", "calmar_ratio"].includes(r.key as string));

export function DrawdownDetail({ block }: { block: RiskBlock | undefined }) {
  const d = block?.drawdown_detail;
  if (!block?.available || !d) return null;
  const rows: [string, string][] = [
    ["Peak", d.peak_date ?? dash], ["Trough", d.trough_date ?? dash], ["Peak to trough", d.drawdown_days != null ? `${d.drawdown_days} days` : dash],
    ["Recovered", d.recovery_date ?? "Not yet recovered"], ["Trough to recovery", d.recovery_days != null ? `${d.recovery_days} days` : dash],
    ["Current drawdown", d.current_drawdown != null ? fmtPct(d.current_drawdown) : dash],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-8 text-xs md:grid-cols-3">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4 border-b border-line/40 py-1.5"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{v}</dd></div>
      ))}
    </dl>
  );
}

export function BenchmarkTable({ block }: { block: RiskBlock | undefined }) {
  const b = block?.benchmark;
  if (!block?.available || !b) return <p className="text-xs text-faint">Benchmark metrics are not available for this window.</p>;
  const rows: [string, MetricT | null | undefined, number, boolean, string?][] = [
    ["Beta", b.beta, 2, false, "Sensitivity to the category average"], ["Alpha (annualised)", b.alpha, 2, true, "Jensen's alpha over the risk-free proxy"],
    ["R-squared", b.r_squared, 2, false], ["Correlation", b.correlation, 2, false], ["Tracking error", b.tracking_error, 2, true],
    ["Information ratio", b.information_ratio, 2, false], ["Upside capture", b.upside_capture, 1, true, "Monthly, geometric"],
    ["Downside capture", b.downside_capture, 1, true, "Below 100% = loses less than the benchmark in down months"],
    ["Benchmark CAGR", b.benchmark_cagr, 2, true],
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-8 text-xs md:grid-cols-2">
      {rows.map(([k, m, digits, pct, help]) => (
        <div key={k} className="flex justify-between gap-4 border-b border-line/40 py-1.5" title={help}>
          <dt className="text-muted">{k}</dt><dd className="font-mono font-semibold text-strong"><Val m={m} digits={digits} pct={pct} /></dd>
        </div>
      ))}
    </dl>
  );
}

// ---- charts for one fund
export function CumulativeChart({ a }: { a: Analytics }) {
  const c = a.charts?.cumulative;
  if (!c) return null;
  const series: Series[] = [{ key: "fund", name: a.name, data: c.fund }];
  if (c.category_average) series.push({ key: "cat", name: "Category average", data: c.category_average, dashed: true });
  return (
    <Panel icon={LineIcon} title="Cumulative growth" description="Rebased to 100 at the start of the period"
      info="Growth of 100 invested at the start. The category average is an equal-weighted average of today's surviving peers, so it flatters the peer group.">
      <LineChartMulti series={series} />
    </Panel>
  );
}

export function FundDrawdownPanel({ a }: { a: Analytics }) {
  const d = a.charts?.drawdown;
  if (!d) return null;
  const series: Series[] = [{ key: "fund", name: a.name, data: d.fund }];
  if (d.category_average) series.push({ key: "cat", name: "Category average", data: d.category_average });
  return <Panel icon={Waves} tone="down" title="Drawdown" description="Fall from the previous peak"><DrawdownChart series={series} /></Panel>;
}

export function FundRollingPanel({ a }: { a: Analytics }) {
  const r = a.charts?.rolling;
  const v = a.charts?.rolling_volatility_1y;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Panel icon={Activity} title="Rolling returns" description="1-year and 3-year (p.a.) windows">
        <LineChartMulti unit="%" zero series={[
          ...(r?.["1y"] ? [{ key: "r1", name: "1Y rolling", data: r["1y"] }] : []),
          ...(r?.["3y"] ? [{ key: "r3", name: "3Y rolling (p.a.)", data: r["3y"] }] : []),
        ]} />
      </Panel>
      <Panel icon={Gauge} title="Rolling volatility (1Y)" description="Annualised standard deviation of daily returns">
        <LineChartMulti unit="%" legend={false} series={v?.length ? [{ key: "v", name: "Volatility", data: v, color: SERIES[3] }] : []} />
      </Panel>
    </div>
  );
}

export { BarChart3, ShieldAlert };
