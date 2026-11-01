import { Gauge, Grid3x3, ShieldAlert, Waves } from "lucide-react";
import { PageHeader, Panel } from "@/components/ui/ui";
import { DrawdownDetail, OVERVIEW_ROWS, RiskTable, TAIL_ROWS } from "@/components/analytics/panels";
import { DrawdownChart, LineChartMulti, SERIES } from "@/components/charts/ChartKit";
import { Shell, load, readParams, type SP } from "@/components/analytics/MultiFundPage";
import { dash } from "@/lib/format";

const TABS = [
  { key: "overview", label: "Risk Overview" }, { key: "volatility", label: "Volatility" }, { key: "drawdown", label: "Drawdown" },
  { key: "tail", label: "Tail Risk" }, { key: "correlation", label: "Correlation" },
];

export default async function RiskPage({ searchParams }: { searchParams: SP }) {
  const { ids, years, tab } = await readParams(await searchParams, TABS.map((t) => t.key));
  const { data, error } = await load(ids, years);
  const funds = (data?.funds ?? []).filter((f) => f.available);
  const w = Number(years === "max" ? 5 : years);
  const col = (f: (typeof funds)[number]) => ({ label: f.name, block: f.windows?.find((x) => x.years === w) });
  const series = (m: Record<string, [string, number][]> | undefined) =>
    funds.filter((f) => m?.[f.scheme_id]).map((f, i) => ({ key: `f${f.scheme_id}`, name: f.name, data: m![f.scheme_id], color: SERIES[i] }));

  return (
    <>
      <PageHeader title="Risk" accent="Analytics" subtitle="ANALYTICS"
        description="Volatility, drawdowns, risk-adjusted returns and tail risk from official daily NAVs. Sharpe and Sortino use a risk-free proxy built from overnight and liquid funds." />
      <Shell base="/risk" ids={ids} years={years} tab={tab} tabs={TABS} data={data} error={error}>
        {tab === "overview" && funds.length > 0 && (
          <Panel icon={ShieldAlert} tone="warn" title={`Risk overview, ${w}-year window`} description="Windows end on each fund's latest NAV date"
            info="Ratios are withheld (shown as a dash) when volatility is too low for them to be meaningful, e.g. liquid funds.">
            <RiskTable columns={funds.map(col)} rows={OVERVIEW_ROWS} />
          </Panel>
        )}
        {tab === "volatility" && funds.length > 0 && (
          <Panel icon={Gauge} title="Rolling volatility (1 year)" description="Annualised standard deviation of daily returns, 252-day window">
            <LineChartMulti unit="%" series={series(data?.chart.rolling_volatility_1y)} />
          </Panel>
        )}
        {tab === "drawdown" && funds.length > 0 && (
          <>
            <Panel icon={Waves} tone="down" title="Drawdown comparison" description={`Fall from the previous peak, ${data?.chart.start ?? ""} to ${data?.chart.end ?? ""}`}>
              <DrawdownChart series={series(data?.chart.drawdown)} />
            </Panel>
            {funds.map((f) => (
              <Panel key={f.scheme_id} icon={ShieldAlert} tone="down" title={f.name} description={`Largest drawdown in the ${w}-year window`}>
                {f.windows?.find((x) => x.years === w)?.available ? <DrawdownDetail block={f.windows?.find((x) => x.years === w)} /> : <p className="text-xs text-faint">{f.windows?.find((x) => x.years === w)?.reason ?? dash}</p>}
              </Panel>
            ))}
          </>
        )}
        {tab === "tail" && funds.length > 0 && (
          <Panel icon={ShieldAlert} tone="down" title={`Tail risk, ${w}-year window`} description="1-day losses; VaR is the loss exceeded on the worst 5% (or 1%) of days, CVaR the average loss beyond it"
            info="Historical estimates from daily NAV returns. Normal VaR assumes a bell-shaped distribution and understates risk when kurtosis is high.">
            <RiskTable columns={funds.map(col)} rows={TAIL_ROWS} />
          </Panel>
        )}
        {tab === "correlation" && (data?.correlation.ids.length ?? 0) >= 2 && data && (
          <Panel icon={Grid3x3} title="Correlation of daily returns" description={`${data.correlation.observations} common daily observations, ${data.chart.start} to ${data.chart.end}`}>
            <div className="w-full overflow-x-auto">
              <table className="border-collapse text-xs">
                <thead><tr><th />{data.correlation.ids.map((id) => <th key={id} className="max-w-[140px] truncate px-2 py-1.5 text-[10px] font-medium text-muted">{funds.find((f) => f.scheme_id === id)?.name}</th>)}</tr></thead>
                <tbody>
                  {data.correlation.matrix.map((row, i) => (
                    <tr key={i}>
                      <th className="max-w-[160px] truncate pr-2 text-left text-[11px] font-medium text-muted">{funds.find((f) => f.scheme_id === data.correlation.ids[i])?.name}</th>
                      {row.map((v, j) => <td key={j} className="px-3 py-2 text-center font-mono text-strong" style={{ background: `rgba(59,130,246,${(Math.max(0, v) * 0.55).toFixed(2)})` }}>{v.toFixed(2)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
        {tab === "correlation" && (data?.correlation.ids.length ?? 0) < 2 && data && <Panel><p className="py-6 text-center text-xs text-faint">Select at least two analysable funds to see correlations.</p></Panel>}
      </Shell>
    </>
  );
}
