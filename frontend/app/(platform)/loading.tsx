import { SkeletonPanel } from "@/components/ui/ui";

export default function Loading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="h-24 animate-pulse rounded-xl bg-line/40" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-line/40" />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8"><SkeletonPanel rows={6} /></div>
        <div className="lg:col-span-4"><SkeletonPanel rows={4} /></div>
      </div>
    </div>
  );
}
