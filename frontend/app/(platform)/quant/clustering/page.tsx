import { Boxes, Shapes } from "lucide-react";
import { Banner, EmptyState, PageHeader, Panel, PillTabs } from "@/components/ui/ui";
import { ClusterScatter, SERIES } from "@/components/charts/ChartKit";
import { Caveats, LabKicker, TH } from "@/components/quant/QuantUi";
import { api } from "@/lib/api";

type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const TIERS = ["Equity", "Debt", "Hybrid", "Other"];
const METHODS = ["kmeans", "hierarchical", "gmm", "dbscan"];
const MLABEL: Record<string, string> = { kmeans: "K-Means", hierarchical: "Hierarchical", gmm: "Gaussian mixture", dbscan: "DBSCAN" };
const FEAT: Record<string, string> = { ret_3y: "3Y return", vol_3y: "3Y vol", sharpe_3y: "Sharpe", max_dd_3y: "Max DD", mom_12m: "12M mom.", downside_capture_3y: "Down capture", info_ratio_3y: "Info ratio" };

export default async function ClusteringPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const tier = TIERS.includes(first(sp.tier) ?? "") ? (first(sp.tier) as string) : "Equity";
  const method = METHODS.includes(first(sp.method) ?? "") ? (first(sp.method) as string) : "kmeans";
  const all = await api.quantClusters().catch(() => null);
  const t = all?.clusters[tier];
  const m = t?.methods?.find((x) => x.method === method);
  const points = t?.pca && m ? Object.entries(t.pca.points).map(([code, [x, y]]) => ({ x, y, cluster: m.assignments[code] ?? 0, name: t.names?.[code] ?? code })) : [];
  return (
    <>
      <PageHeader title="Fund" accent="Clustering" subtitle="QUANT RESEARCH LAB"
        description="Groups of funds that behave alike, found without using their categories. Run separately inside each asset tier so the result is not just 'equity versus debt'." />
      <LabKicker />
      <PillTabs active={tier} items={TIERS.map((x) => ({ key: x, label: x, href: `/quant/clustering?tier=${x}&method=${method}` }))} />
      {!all ? <Panel><EmptyState icon={Boxes} title="Not built yet" hint="Run `python -m app.cli.pipeline quant`." /></Panel>
        : !t?.available ? <Banner tone="warn">{tier}: {t?.reason ?? "no result"} ({t?.funds ?? 0} funds with every feature).</Banner> : (
          <>
            <PillTabs active={method} items={METHODS.map((x) => ({ key: x, label: MLABEL[x], href: `/quant/clustering?tier=${tier}&method=${x}` }))} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
              <div className="lg:col-span-7">
                <Panel icon={Shapes} tone="ai" title="Principal components" description={`${t.funds} Direct-plan funds; PC1 ${((t.pca?.explained_variance[0] ?? 0) * 100).toFixed(0)}% and PC2 ${((t.pca?.explained_variance[1] ?? 0) * 100).toFixed(0)}% of variance`}
                  info="Each dot is a fund, placed by the two directions that capture most of the variation in its risk and return features.">
                  <ClusterScatter points={points} />
                </Panel>
              </div>
              <div className="lg:col-span-5">
                <Panel icon={Boxes} tone="ai" title={`${MLABEL[method]} result`} description={m ? `${m.clusters} clusters · silhouette ${m.silhouette === null ? "n/a" : m.silhouette.toFixed(2)}${m.noise_points ? ` · ${m.noise_points} outliers` : ""}` : undefined}
                  info="Silhouette is between -1 and 1; above 0.5 is clear structure, around 0.25 weak. Labels are generated from measured traits relative to the tier.">
                  <div className="space-y-2">
                    {m?.centroids.map((c, i) => (
                      <div key={c.cluster} className="rounded-lg border border-line bg-raised p-2.5 text-xs">
                        <div className="flex items-center justify-between"><span className="font-semibold text-strong"><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: SERIES[i % SERIES.length] }} />Cluster {c.cluster + 1}</span><span className="font-mono text-muted">{c.size} funds</span></div>
                        <div className="mt-0.5 text-fg">{c.label}</div>
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>
            </div>
            <Panel title="Cluster profiles" description="Average of each feature inside the cluster (original units)">
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Cluster</th><th className={`${TH} text-right`}>Funds</th>{t.features?.map((f) => <th key={f} className={`${TH} text-right`}>{FEAT[f] ?? f}</th>)}</tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {m?.centroids.map((c) => (
                      <tr key={c.cluster} className="transition-colors hover:bg-hover"><td className="px-2 py-2 font-medium text-fg">{c.cluster + 1}</td><td className="px-2 py-2 text-right">{c.size}</td>
                        {t.features?.map((f) => <td key={f} className="px-2 py-2 text-right">{Number(c[f]).toFixed(2)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
            <Caveats items={t.notes ?? []} />
          </>
        )}
    </>
  );
}
