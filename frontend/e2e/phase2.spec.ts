import { expect, test } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;

test("overview renders real aggregates with no broken values", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: /Market Overview/ })).toBeVisible();
  await expect(page.getByText("Schemes in universe")).toBeVisible();
  await expect(page.getByText("Category returns heatmap")).toBeVisible();
  await expect(page.getByText("AMC leaderboard")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
  // horizon switch changes the top-performers table
  await page.getByRole("link", { name: "3Y", exact: true }).click();
  await expect(page).toHaveURL(/horizon=3y/);
  await expect(page.getByText("Top performers (3Y)")).toBeVisible();
});

test("screener: tabs, AND/OR conditions, URL persistence, saved screens", async ({ page }) => {
  await page.goto("/screener");
  const count = page.getByText(/fund(s)? match/);
  await expect(count).toContainText("3,351");

  await page.getByRole("button", { name: "Equity", exact: true }).click();
  await expect(count).toContainText("1,276");

  await page.getByRole("button", { name: "Add condition" }).click();
  await page.getByLabel("Field").selectOption("cat_pct_3y");
  await page.getByLabel("Value", { exact: true }).fill("80");
  await expect(count).not.toContainText("1,276");
  const n = Number((await count.innerText()).replace(/[^\d]/g, ""));
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThan(1276);

  // every visible 3Y percentile must be > 80 (shown rounded to an integer, so >= 80)
  const pctiles = await page.locator("tbody tr td:nth-child(15)").allInnerTexts();
  expect(pctiles.length).toBeGreaterThan(0);
  for (const t of pctiles) expect(Number(t)).toBeGreaterThanOrEqual(80);

  // state survives a reload through the URL
  await expect(page).toHaveURL(/s=/);
  await page.reload();
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue("80");
  await expect(count).toContainText(String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","));

  // saved screens (browser storage)
  page.once("dialog", (d) => d.accept("My test screen"));
  await page.getByRole("button", { name: "Save screen" }).click();
  await expect(page.getByRole("button", { name: "My test screen", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reset all" }).click();
  await expect(count).toContainText("3,351");
  await page.getByRole("button", { name: "My test screen", exact: true }).click();
  await expect(count).toContainText(String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","));
});

test("screener: missing values never match, empty state, incomplete condition ignored", async ({ page }) => {
  await page.goto("/screener");
  const count = page.getByText(/fund(s)? match/);
  await page.getByRole("button", { name: "Add condition" }).click();
  await expect(page.getByText("1 incomplete condition ignored")).toBeVisible();
  await expect(count).toContainText("3,351");
  await page.getByLabel("Field").selectOption("net_assets");
  await page.getByLabel("Value", { exact: true }).fill("0");
  await expect(count).toContainText("2,284"); // 1,067 funds without net assets never match
  await page.getByLabel("Value", { exact: true }).fill("99999999");
  await expect(page.getByText(/No funds match these conditions/)).toBeVisible();
});

test("screener: CSV export downloads a file", async ({ page }) => {
  await page.goto("/screener");
  await page.getByRole("button", { name: "Equity", exact: true }).click();
  await expect(page.getByText(/1,276 funds match/)).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export CSV" }).click()]);
  expect(dl.suggestedFilename()).toBe("quantsynthica-screen.csv");
});

test("screener -> comparison flow, max 5 enforced", async ({ page }) => {
  await page.goto("/screener");
  const boxes = page.locator("tbody input[type=checkbox]");
  await expect(boxes.first()).toBeVisible();
  for (let i = 0; i < 5; i++) await boxes.nth(i).check();
  await expect(page.getByText("5/5 selected")).toBeVisible();
  await expect(boxes.nth(5)).toBeDisabled();
  await page.getByRole("link", { name: "Compare selected" }).click();
  await expect(page).toHaveURL(/\/comparison\?ids=/);
  await expect(page.getByRole("heading", { name: /Comparison/ })).toBeVisible();
  await expect(page.locator("thead th:visible")).toHaveCount(6); // metric + 5 funds
  await expect(page.getByPlaceholder(/Maximum reached/)).toBeDisabled();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("comparison: add via search, warnings for mixed categories", async ({ page }) => {
  await page.goto("/comparison?ids=1,2");
  await expect(page.getByText(/different categories|asset tiers/).first()).toBeVisible();
  await page.getByLabel(/Add a fund/).fill("parag parikh");
  await page.getByRole("button", { name: /Parag Parikh/i }).first().click();
  await expect(page).toHaveURL(/ids=1,2,\d+/);
});

test("fund page tabs: live tabs show data, gated tabs say why", async ({ page }) => {
  await page.goto("/funds/1?tab=performance");
  await expect(page.getByText("Returns vs category peers")).toBeVisible();
  await page.getByRole("link", { name: /NAV Analysis/ }).click();
  await expect(page.getByText("52-week range")).toBeVisible();
  await page.getByRole("link", { name: /Portfolio Holdings/ }).click();
  await expect(page.getByText(/is not available yet/)).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("unknown fund shows not-found page", async ({ page }) => {
  await page.goto("/funds/99999999");
  await expect(page.getByText("Not found")).toBeVisible();
});
