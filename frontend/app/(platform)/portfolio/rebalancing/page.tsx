import { Layers } from "lucide-react";
import { EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { PortfolioPicker } from "@/components/portfolio/PortfolioPicker";
import { RebalanceLab } from "@/components/portfolio/RebalanceLab";
import { loadPicks, type SP } from "@/components/portfolio/server";

export default async function RebalancingPage({ searchParams }: { searchParams: SP }) {
  const { picks } = await loadPicks(await searchParams);
  return (
    <>
      <PageHeader title="Portfolio" accent="Rebalancing" subtitle="PORTFOLIOS"
        description="Enter what you hold, set target weights and a drift threshold, and get the buys and sells that bring you back, with estimated costs and exit loads." />
      <PortfolioPicker initial={picks} basePath="/portfolio/rebalancing" note="Weights here are your targets. Costs and exit loads are estimates; capital gains tax is not modelled." />
      {picks.length < 1 ? <Panel><EmptyState icon={Layers} title="No funds selected" hint="Choose the funds you hold." /></Panel>
        : <RebalanceLab key={picks.map((p) => p.scheme_id).join("-")} funds={picks} />}
    </>
  );
}
