import { Suspense } from "react";
import { Footer } from "@/components/layout/Footer";
import { TopNav } from "@/components/layout/TopNav";

// Shell for the research platform. The landing page (app/page.tsx) has its own navigation bar and footer instead.
export default function PlatformLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-screen flex-col">
      {/* usePathname() needs a Suspense boundary under Cache Components */}
      <Suspense fallback={<div className="sticky top-0 z-50 h-16 border-b border-line/80 bg-base/95" />}>
        <TopNav />
      </Suspense>
      <main className="app-container min-h-screen flex-1 space-y-6 py-6">{children}</main>
      <Footer />
    </div>
  );
}
