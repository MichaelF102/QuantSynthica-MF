import { expect, test } from "@playwright/test";

// DESIGN.md checks: no vendor names, design fonts, mono numbers, no page-level horizontal scroll.
const PAGES = ["/overview", "/funds", "/screener", "/funds/1", "/comparison?ids=1,2", "/coverage", "/performance?ids=1214,1213", "/risk?ids=1214,1213&tab=tail", "/funds/1214?tab=risk", "/quant/scoring", "/quant/factors", "/quant/statistics", "/quant/clustering", "/quant/regimes", "/quant/backtesting"];
const VENDORS = /yahoo|tradingview|gemini|morningstar|value research/i;

for (const path of PAGES) {
  test(`design rules: ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(VENDORS);

    const body = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(body).toMatch(/inter/i);
    const mono = page.locator("td.text-right").first();
    if (await mono.count()) expect(await mono.evaluate((e) => getComputedStyle(e).fontFamily)).toMatch(/plex|mono/i);

    for (const w of [375, 1280, 1920]) {
      // load at the target width (charts re-measure asynchronously after a live resize)
      await page.setViewportSize({ width: w, height: 900 });
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over, `horizontal overflow at ${w}px`).toBeLessThanOrEqual(1);
    }
  });
}

test("theme toggle switches palette and persists", async ({ page }) => {
  await page.goto("/overview");
  const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  const dark = await bg();
  await page.getByRole("button", { name: /Switch to light theme/ }).click();
  expect(await bg()).not.toBe(dark);
  await page.reload();
  await expect(page.getByRole("button", { name: /Switch to dark theme/ })).toBeVisible();
});

test("nav: active item marked, menu opens and closes with Escape", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("link", { name: "Market Overview", exact: true }).first()).toHaveAttribute("aria-current", "page");
  const explorer = page.getByRole("link", { name: /Fund Explorer/ }).first();
  await explorer.focus();
  await expect(page.getByRole("menuitem", { name: /Comparison/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: /Comparison/ })).toHaveCount(0);
});
