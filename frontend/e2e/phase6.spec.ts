import { expect, test, type Page } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;
const IDS = "352:1,258:1,2613:1,328:1"; // Growth equity funds with long histories

async function noBad(page: Page) { expect(await page.locator("body").innerText()).not.toMatch(BAD); }

test("builder: search, add funds, analyse; weights and risk shares are shown", async ({ page }) => {
  await page.goto("/portfolio/builder");
  await expect(page.getByRole("heading", { name: /Portfolio\s*Builder/ })).toBeVisible();
  await expect(page.getByText("No funds selected")).toBeVisible();
  await page.getByLabel(/Add a fund/).fill("Tata India Consumer");
  await page.getByRole("button", { name: /Tata India Consumer/ }).first().click();
  await page.getByLabel(/Add a fund/).fill("HDFC Flexi");
  await page.getByRole("button", { name: /HDFC Flexi/ }).first().click();
  await page.getByRole("button", { name: "Analyse portfolio" }).click();
  await expect(page).toHaveURL(/p=\d+:/);
  await expect(page.getByText("Where the risk comes from")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByText("Allocation", { exact: true })).toBeVisible();
  await expect(page.getByText("Correlation of daily returns")).toBeVisible();
  await noBad(page);
});

test("builder: unusable IDCW fund in the link is dropped with a message", async ({ page }) => {
  await page.goto(`/portfolio/builder?p=${IDS},3:1`);
  await expect(page.getByText(/cannot be used and was left out/)).toBeVisible({ timeout: 25_000 });
});

test("optimization: runs a method, shows weights, frontier, hold-out and assumptions", async ({ page }) => {
  await page.goto(`/portfolio/optimization?p=${IDS}`);
  await page.getByLabel("Method").selectOption("min_variance");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByRole("heading", { name: "Efficient frontier" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Out-of-sample check" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Assumptions" })).toBeVisible();
  await expect(page.getByText(/not forecasts/).first()).toBeVisible();
  await noBad(page);
});

test("optimization: infeasible limits explain themselves", async ({ page }) => {
  await page.goto(`/portfolio/optimization?p=${IDS}`);
  await page.getByText("Max weight %").locator("..").locator("input").fill("10");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText(/cannot reach 100%/)).toBeVisible({ timeout: 30_000 });
});

test("optimization: Black-Litterman requires a view", async ({ page }) => {
  await page.goto(`/portfolio/optimization?p=${IDS}`);
  await page.getByLabel("Method").selectOption("black_litterman");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText(/at least one view/)).toBeVisible({ timeout: 30_000 });
});

test("simulators: historical SIP is labelled, projection is labelled hypothetical", async ({ page }) => {
  await page.goto("/portfolio/sip-swp?p=352:1");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("Historical simulation: uses the actual NAV history.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("XIRR", { exact: true })).toBeVisible();
  await page.getByLabel("Simulation").selectOption("projection");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText(/Hypothetical projection/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/not a forecast/).first()).toBeVisible();
  await noBad(page);
});

test("simulators: unavailable rolling SWP states its reason", async ({ page }) => {
  await page.goto("/portfolio/sip-swp?p=352:1");
  await page.getByLabel("Simulation").selectOption("rolling_swp");
  await page.getByText("Horizon (years)").locator("..").locator("input").fill("25");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText(/start dates have a full|only \d+ start dates/)).toBeVisible({ timeout: 30_000 });
});

test("rebalancing: plans trades that include new cash", async ({ page }) => {
  await page.goto("/portfolio/rebalancing?p=352:50,258:50");
  await page.getByLabel(/^value for /).first().fill("80000");
  await page.getByLabel(/^value for /).nth(1).fill("20000");
  await page.getByRole("button", { name: "Plan trades" }).click();
  await expect(page.getByText(/rebalancing is suggested/)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("SELL", { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/Capital gains tax is not modelled/)).toBeVisible();
  await noBad(page);
});

test("stress testing: historical episodes and labelled hypothetical shocks", async ({ page }) => {
  await page.goto(`/portfolio/stress-testing?p=${IDS}`);
  await expect(page.getByText("Worst historical episodes")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Hypothetical market shocks")).toBeVisible();
  await expect(page.getByText(/not from an external event list/)).toBeVisible();
  await noBad(page);
});

test("Portfolios menu links to all five pages", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("link", { name: /^Portfolios/ }).focus();
  for (const n of ["Portfolio Builder", "Optimization", "SIP / SWP Simulators", "Rebalancing", "Stress Testing"]) await expect(page.getByRole("menuitem", { name: new RegExp(n) })).toBeVisible();
});

for (const w of [375, 1280, 1920]) {
  test(`no horizontal overflow on portfolio pages at ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 900 });
    for (const path of ["builder", "optimization", "sip-swp", "rebalancing", "stress-testing"]) {
      await page.goto(`/portfolio/${path}?p=${IDS}`);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over, `${path} at ${w}`).toBeLessThanOrEqual(1);
    }
  });
}
