import { PageHeader } from "@/components/ui/ui";
import { BacktestLab } from "@/components/quant/BacktestLab";
import { LabKicker } from "@/components/quant/QuantUi";
import { api } from "@/lib/api";

export default async function BacktestingPage() {
  const m = await api.quantMethodology();
  return (
    <>
      <PageHeader title="Strategy" accent="Backtesting" subtitle="QUANT RESEARCH LAB"
        description="Does picking funds by a rule beat simply holding every comparable fund? Point-in-time selection, execution delay, transaction costs, exit loads and an out-of-sample split." />
      <LabKicker />
      <BacktestLab strategies={m.strategies} />
    </>
  );
}
