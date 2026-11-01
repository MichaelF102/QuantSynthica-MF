import type { Metadata } from "next";
import { Suspense } from "react";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { Footer } from "@/components/layout/Footer";
import { TopNav } from "@/components/layout/TopNav";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] });
const plexMono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "QuantSynthica Mutual Funds",
  description: "Quantitative research platform for Indian mutual funds",
};

// Applies the saved theme (else the OS preference) before first paint so the page never flashes the wrong theme.
const THEME_INIT = `try{var t=localStorage.getItem('theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){document.documentElement.classList.add('dark')}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT }} /></head>
      <body className="flex min-h-screen flex-col bg-base font-sans text-fg antialiased">
        {/* usePathname() needs a Suspense boundary under Cache Components */}
        <Suspense fallback={<div className="sticky top-0 z-50 h-16 border-b border-line/80 bg-base/95" />}>
          <TopNav />
        </Suspense>
        <main className="app-container min-h-screen flex-1 space-y-6 py-6">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
