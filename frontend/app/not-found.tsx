import Link from "next/link";
import { SearchX } from "lucide-react";
import { EmptyState, Panel } from "@/components/ui/ui";

export default function NotFound() {
  return (
    <Panel>
      <EmptyState icon={SearchX} title="Not found" hint="That page or fund does not exist in the current data." />
      <div className="pb-6 text-center"><Link href="/funds" className="text-[11px] font-medium text-accent hover:underline">Back to Fund Explorer</Link></div>
    </Panel>
  );
}
