import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // Platform pages read live data and the URL on every request. The default dev-time check for instant navigations would flag every one of them
  // on each page load; only segments that opt in with `export const instant` are validated.
  experimental: { instantInsights: { validationLevel: "manual-warning" } },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
