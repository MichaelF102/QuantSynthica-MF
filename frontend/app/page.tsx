import type { Metadata } from "next";
import { Suspense } from "react";
import { Landing } from "@/components/landing2/Landing";
import { api, type PlatformStats } from "@/lib/api";

export const metadata: Metadata = {
  title: "QuantSynthica Mutual Funds: Beyond Returns. Into Intelligence.",
  description: "Quantitative research for Indian mutual funds: risk and performance analytics, peer-relative scoring, portfolio engineering and a sourced AI assistant.",
};

/** Landing page: the entry point. The research platform itself lives under /overview and the routes in the (platform) group. */
async function LandingWithStats() {
  let stats: PlatformStats | null = null;
  // A sleeping free-tier API can take a minute to wake; show dashes after 8 s instead of holding the page.
  try { stats = await Promise.race([api.platformStats(), new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 8000))]); } catch { stats = null; }
  return <Landing stats={stats} />;
}

export default function Home() {
  // The statistics come from the API at request time; until they arrive the page shows an empty dark canvas (no placeholder figures).
  return <Suspense fallback={<div aria-hidden className="min-h-screen bg-[#07090c]" />}><LandingWithStats /></Suspense>;
}
