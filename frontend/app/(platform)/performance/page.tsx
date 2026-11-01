import { Activity, BarChart3, LineChart as LineIcon, Target } from "lucide-react";
import { PageHeader, Panel } from "@/components/ui/ui";
import { CalendarPanel, RollingPanel, TrailingTable, Val } from "@/components/analytics/panels";
import { LineChartMulti, SERIES } from "@/components/charts/ChartKit";
import { Shell, load, readParams, type SP } from "@/components/analytics/MultiFundPage";
import { dash } from "@/lib/format";

const TABS = [
  { key: "returns", label: "Return Analysis" }, { key: "rolling", label: "Rolling Returns" }, { key: "calendar", label: "Calendar Returns" },
  { key: "consistency", label: "Consistency" }, { key: "benchmark", label: "Category Comparison" },
];
const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

export default async function PerformancePage({ searchParams }: { searchParams: SP }) {
  const { ids, years, tab } = await readParams(await searchParams, TABS.map((t) => t.key));
  const { data, error } = await load(ids, years);
  const funds = (data?.funds ?? []).filter((f) => f.available);
  const w = Number(years === "max" ? 5 : years);

  return (
    <>
      <PageHeader title="Performance" accent="Analytics" subtitle="ANALYTICS"
        description="Returns, rolling-return distributions, calendar years, consistency and comparison with the category average, computed from official daily NAVs." />
      <Shell base="/performance" ids={ids} years={years} tab={tab} tabs={TABS} data={data} error={error}>
        {tab === "returns" && funds.length > 0 && (
          <>
            <Panel icon={LineIcon} title="Cumulative growth" description={`Rebased to 100 over the common period ${data?.chart.start ?? ""} to ${data?.chart.end ?? ""}`}>
              <LineChartMulti series={funds.filter((f) => data?.chart.cumulative?.[f.scheme_id]).map((f, i) => ({ key: `f${f.scheme_id}`, name: f.name, data: data!.chart.cumulative![f.scheme_id], color: SERIES[i] }))} />
            </Panel>
            <Panel icon={BarChart3} title="Trailing returns" description="From NAV; 3 years and longer are annualised"><TrailingTable funds={funds} /></Panel>
          </>
        )}
        {tab === "rolling" && funds.length > 0 && <RollingPanel funds={funds} />}
        {tab === "calendar" && funds.length > 0 && <CalendarPanel funds={funds} />}
        {tab === "consistency" && funds.length > 0 && (
          <Panel icon={Activity} title="Consistency" description="How reliably each fund delivered"
            info="Positive months: share of calendar months with a gain. Rolling outperformance: share of 3-year windows in which the fund beat the category average.">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>Positive months</th>
                  <th className={`${TH} text-right`}>3Y rolling windows positive</th><th className={`${TH} text-right`}>3Y windows beating category avg</th>
                  <th className={`${TH} text-right`}>1Y windows beating category avg</th></tr></thead>
                <tbody className="divide-y divide-line/50">
                  {funds.map((f) => (
                    <tr key={f.scheme_id} className="transition-colors hover:bg-hover">
                      <td className="max-w-[260px] truncate px-2 py-2 font-medium text-fg">{f.name}</td>
                      <td className="px-2 py-2 text-right"><Val m={f.positive_months} digits={0} />%</td>
                      <td className="px-2 py-2 text-right">{f.rolling?.["3y"]?.pct_positive == null ? dash : `${f.rolling["3y"].pct_positive!.toFixed(0)}%`}</td>
                      <td className="px-2 py-2 text-right"><Val m={f.rolling?.["3y"]?.pct_outperform_benchmark} digits={0} />%</td>
                      <td className="px-2 py-2 text-right"><Val m={f.rolling?.["1y"]?.pct_outperform_benchmark} digits={0} />%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
        {tab === "benchmark" && funds.length > 0 && (
          <Panel icon={Target} title={`${w}-year comparison with each fund's category average`} description="Beta, alpha and capture are against the equal-weighted average of comparable funds (survivors only)">
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead><tr className="border-b border-line"><th className={TH}>Fund</th><th className={`${TH} text-right`}>CAGR</th><th className={`${TH} text-right`}>Category avg CAGR</th>
                  <th className={`${TH} text-right`}>Alpha</th><th className={`${TH} text-right`}>Beta</th><th className={`${TH} text-right`}>Tracking error</th>
                  <th className={`${TH} text-right`}>Info ratio</th><th className={`${TH} text-right`}>Up capture</th><th className={`${TH} text-right`}>Down capture</th></tr></thead>
                <tbody className="divide-y divide-line/50">
                  {funds.map((f) => {
                    const b = f.windows?.find((x) => x.years === w);
                    return (
                      <tr key={f.scheme_id} className="transition-colors hover:bg-hover">
                        <td className="max-w-[240px] truncate px-2 py-2 font-medium text-fg">{f.name}</td>
                        <td className="px-2 py-2 text-right font-semibold"><Val m={b?.cagr} pct colour /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.benchmark_cagr} pct /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.alpha} pct signed colour /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.beta} /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.tracking_error} pct /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.information_ratio} /></td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.upside_capture} digits={0} />%</td>
                        <td className="px-2 py-2 text-right"><Val m={b?.benchmark?.downside_capture} digits={0} />%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
        {data && funds.length === 0 && null}
      </Shell>
    </>
  );
}
