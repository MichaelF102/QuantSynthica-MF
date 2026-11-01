import { defineConfig } from "@playwright/test";

// Requires the API (port 8000) and the built frontend (`npm run start`, port 3000) to be running.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  workers: 1,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", channel: "chrome", headless: true, acceptDownloads: true },
});
