"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import type { PlatformStats } from "@/lib/api";
import { buildMarkup } from "./markup";
import { initLanding } from "./script";
import "./landing.css";

/** The landing page. The markup is static (only the statistics vary) and the script wires up the interactive parts after mount. */
export function Landing({ stats }: { stats: PlatformStats | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const html = useMemo(() => buildMarkup(stats), [stats]);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    return initLanding(root, (href) => router.push(href));
  }, [router, html]);
  return <div ref={ref} className="qsl" dangerouslySetInnerHTML={{ __html: html }} />;
}
