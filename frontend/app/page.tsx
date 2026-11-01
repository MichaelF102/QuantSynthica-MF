import type { Metadata } from "next";
import { Suspense } from "react";
import { AIAssistantSection } from "@/components/landing/AIAssistantSection";
import { Ecosystem } from "@/components/landing/Ecosystem";
import { ExplorePlatform } from "@/components/landing/ExplorePlatform";
import { FinalCTA } from "@/components/landing/FinalCTA";
import { Hero } from "@/components/landing/Hero";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingNav } from "@/components/landing/LandingNav";
import { MarketRegimeSection, MarketRegimeSkeleton } from "@/components/landing/MarketRegimeSection";
import { MethodologySection } from "@/components/landing/MethodologySection";
import { PlatformStats, PlatformStatsSkeleton } from "@/components/landing/PlatformStats";
import { PortfolioEngineeringSection } from "@/components/landing/PortfolioEngineeringSection";
import { QuantEngineSection, QuantEngineSkeleton } from "@/components/landing/QuantEngineSection";
import { RiskPerformanceSection } from "@/components/landing/RiskPerformanceSection";

export const metadata: Metadata = {
  title: "QuantSynthica Mutual Funds: Beyond Returns. Into Intelligence.",
  description: "Quantitative research for Indian mutual funds: risk and performance analytics, peer-relative scoring, portfolio engineering and a sourced AI assistant.",
};

/** Landing page: the entry point. The research platform itself lives under /overview and the routes in the (platform) group. */
export default function Landing() {
  return (
    <div className="flex min-h-screen flex-col">
      <LandingNav />
      <main className="flex-1">
        <Hero />
        <Suspense fallback={<PlatformStatsSkeleton />}><PlatformStats /></Suspense>
        <Ecosystem />
        <ExplorePlatform />
        <Suspense fallback={<QuantEngineSkeleton />}><QuantEngineSection /></Suspense>
        <RiskPerformanceSection />
        <PortfolioEngineeringSection />
        <Suspense fallback={<MarketRegimeSkeleton />}><MarketRegimeSection /></Suspense>
        <AIAssistantSection />
        <MethodologySection />
        <FinalCTA />
      </main>
      <LandingFooter />
    </div>
  );
}
