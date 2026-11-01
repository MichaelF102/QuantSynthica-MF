import { Layers } from "lucide-react";
import { EmptyState, PageHeader, Panel } from "@/components/ui/ui";
import { PortfolioPicker } from "@/components/portfolio/PortfolioPicker";
import { SimulatorLab } from "@/components/portfolio/SimulatorLab";
import { loadPicks, type SP } from "@/components/portfolio/server";

export default async function SipSwpPage({ searchParams }: { searchParams: SP }) {
  const { picks, holdings } = await loadPicks(await searchParams);
  const target = holdings.length === 1 ? { scheme_id: holdings[0].scheme_id } : { holdings };
  return (
    <>
      <PageHeader title="SIP / SWP" accent="Simulators" subtitle="PORTFOLIOS"
        description="Replay a monthly investment or withdrawal plan on real NAV history, see the spread of outcomes across start dates, or run a clearly labelled hypothetical projection." />
      <PortfolioPicker initial={picks} basePath="/portfolio/sip-swp" note="Choose one fund, or several to simulate a portfolio rebalanced monthly." />
      {!holdings.length ? <Panel><EmptyState icon={Layers} title="No fund selected" hint="Pick a fund or portfolio to simulate." /></Panel>
        : <SimulatorLab key={holdings.map((h) => `${h.scheme_id}:${h.weight}`).join(",")} target={target} />}
    </>
  );
}
