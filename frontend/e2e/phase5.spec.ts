import { expect, test } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;

test("scoring page ranks funds and states the missing Stability factor", async ({ page }) => {
  await page.goto("/quant/scoring");
  await expect(page.getByRole("heading", { name: /Fund Scoring/ })).toBeVisible();
  await expect(page.getByText(/Stability factor \(5%\) cannot be computed/)).toBeVisible();
  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(10);
  await expect(page.getByText("How the score is built")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("fund Quant Score tab shows a factor breakdown that explains the composite", async ({ page }) => {
  await page.goto("/quant/scoring");
  await page.locator("tbody tr").first().getByRole("link").first().click();
  await expect(page).toHaveURL(/tab=score/);
  await expect(page.getByText("Factor breakdown")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Fund stability" })).toBeVisible();
  await expect(page.getByText(/not available/).first()).toBeVisible(); // Stability row
  await expect(page.getByText("Underlying metrics")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("an unscored fund explains why instead of showing a score", async ({ page }) => {
  await page.goto("/funds/3?tab=score"); // IDCW scheme
  await expect(page.getByText(/No Quant Score/)).toBeVisible();
});

test("factor research shows IC with caveats and horizon control", async ({ page }) => {
  await page.goto("/quant/factors");
  await expect(page.getByRole("heading", { name: /Factor Research/ })).toBeVisible();
  await expect(page.getByText(/Read with care/)).toBeVisible();
  await expect(page.getByText("Caveats")).toBeVisible();
  const links = page.getByRole("link", { name: "12M", exact: true });
  if (await links.count()) { await links.click(); await expect(page).toHaveURL(/h=12/); }
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("statistics, clustering and regimes pages render real output", async ({ page }) => {
  await page.goto("/quant/statistics");
  await expect(page.getByText("Factor correlations")).toBeVisible();
  await page.goto("/quant/clustering");
  await expect(page.getByText("Principal components")).toBeVisible();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
  await page.getByRole("link", { name: "Debt", exact: true }).click();
  await expect(page).toHaveURL(/tier=Debt/);
  await page.goto("/quant/regimes");
  await expect(page.getByText("Trend regime now")).toBeVisible();
  await expect(page.getByText(/Market proxy:/)).toBeVisible();
  await expect(page.getByText("Gaussian mixture (descriptive only)")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("backtest runs as a background job, shows warnings and an out-of-sample split, and is reproducible", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/quant/backtesting");
  await page.getByLabel("Strategy").selectOption("momentum_12m");
  await page.getByRole("button", { name: /Run backtest/ }).click();
  await expect(page.getByText(/Running in the background/)).toBeVisible();
  await expect(page.getByText("Growth of 100")).toBeVisible({ timeout: 200_000 });
  await expect(page.getByText(/Survivorship bias/)).toBeVisible();
  await expect(page.getByText("In-sample versus out-of-sample")).toBeVisible();
  const first = await page.getByText("Strategy CAGR").locator("xpath=..").innerText();
  await page.getByRole("button", { name: /Run backtest/ }).click();
  await expect(page.getByText("Growth of 100")).toBeVisible({ timeout: 200_000 });
  expect(await page.getByText("Strategy CAGR").locator("xpath=..").innerText()).toBe(first);
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("backtest errors are shown, not swallowed", async ({ page }) => {
  await page.goto("/quant/backtesting");
  await page.getByLabel("Tier").selectOption("Other");
  await page.getByRole("button", { name: /Run backtest/ }).click();
  await expect(page.locator("[role=alert], [role=status]").filter({ hasText: /./ }).first()).toBeVisible({ timeout: 60_000 });
});

test("Quant Research Lab menu lists the six pages", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("link", { name: /^Quant Research Lab/ }).focus();
  for (const n of ["Fund Scoring", "Factor Research", "Statistical Analysis", "Fund Clustering", "Regime Analysis", "Strategy Backtesting"])
    await expect(page.getByRole("menuitem", { name: new RegExp(n) })).toBeVisible();
});
