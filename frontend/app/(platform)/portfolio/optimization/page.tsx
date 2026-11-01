import { Layers } from "lucide-react";
import { EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { PortfolioPicker } from "@/components/portfolio/PortfolioPicker";
import { OptimizerLab } from "@/components/portfolio/OptimizerLab";
import { loadPicks, type SP } from "@/components/portfolio/server";

export default async function OptimizationPage({ searchParams }: { searchParams: SP }) {
  const { picks } = await loadPicks(await searchParams);
  return (
    <>
      <PageHeader title="Portfolio" accent="Optimization" subtitle="PORTFOLIOS"
        description="Find weights for the funds you choose: minimum variance, maximum Sharpe, risk parity, minimum CVaR or Black-Litterman, within your limits, with an honest out-of-sample check." />
      <PortfolioPicker initial={picks} basePath="/portfolio/optimization" showWeights={false} minFunds={2} note="Select 2 to 40 funds. Weights are computed for you, so none are entered here." />
      {picks.length < 2 ? <Panel><EmptyState icon={Layers} title="Select at least two funds" hint="Then choose a method and constraints." /></Panel> : <OptimizerLab key={picks.map((p) => p.scheme_id).join("-")} funds={picks.map((p) => ({ scheme_id: p.scheme_id, name: p.name }))} />}
    </>
  );
}
