"use client";

import { Banner } from "@/components/ui/ui";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="py-6">
      <Banner tone="down" action={<button onClick={reset} className="text-[11px] font-medium text-accent hover:underline">Retry</button>}>
        Could not load this page. The data service may be unavailable. {error.message}
      </Banner>
    </div>
  );
}
