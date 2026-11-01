import { expect, test } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;
const FUND = 1214; // Parag Parikh Flexi Cap Direct Growth: mapped, 6+ years of NAV
const REG = 1213;
const IDCW = 3; // an IDCW scheme: NAV analytics must be refused, with a reason

test("fund performance tab shows NAV-derived returns and charts", async ({ page }) => {
  await page.goto(`/funds/${FUND}?tab=performance`);
  await expect(page.getByText("Trailing returns (from NAV)")).toBeVisible();
  await expect(page.getByText("Cumulative growth")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calendar-year returns" })).toBeVisible();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
  await expect(page.getByText("Reported returns vs category peers")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("fund risk tab shows ratios, drawdown and provenance; period control works", async ({ page }) => {
  await page.goto(`/funds/${FUND}?tab=risk`);
  await expect(page.getByText("Risk and return by window")).toBeVisible();
  for (const label of ["Sharpe ratio", "Sortino ratio", "Maximum drawdown", "1-day CVaR 95%"]) await expect(page.getByRole("cell", { name: label })).toBeVisible();
  await expect(page.getByText(/Methodology perf-risk-1\.0\.0/)).toBeVisible();
  await expect(page.getByText(/risk-free proxy|Risk-free: Median daily return/i).first()).toBeVisible();
  await page.getByRole("link", { name: "5Y", exact: true }).click();
  await expect(page).toHaveURL(/years=5/);
  await expect(page.getByText("Largest drawdown")).toBeVisible();
});

test("benchmark tab labels the category average honestly", async ({ page }) => {
  await page.goto(`/funds/${FUND}?tab=benchmark`);
  await expect(page.getByText(/survivorship bias/)).toBeVisible();
  await expect(page.getByText("3-year vs category average")).toBeVisible();
  await expect(page.getByText("Upside capture").first()).toBeVisible();
});

test("IDCW fund: NAV analytics refused with a reason, no numbers invented", async ({ page }) => {
  await page.goto(`/funds/${IDCW}?tab=risk`);
  await expect(page.getByText(/NAV analytics are not available/)).toBeVisible();
  await expect(page.getByText(/IDCW NAVs exclude distributions/)).toBeVisible();
  await expect(page.getByText("Risk and return by window")).toHaveCount(0);
});

test("performance analytics: tabs, comparison and picker", async ({ page }) => {
  await page.goto(`/performance?ids=${FUND},${REG}`);
  await expect(page.getByRole("heading", { name: /Performance Analytics/ })).toBeVisible();
  await expect(page.getByText("Trailing returns").first()).toBeVisible();
  await page.getByRole("link", { name: "Rolling Returns" }).click();
  await expect(page.getByText("3-year rolling (p.a.)")).toBeVisible();
  await page.getByRole("link", { name: "Calendar Returns" }).click();
  await expect(page.getByRole("heading", { name: "Calendar-year returns" })).toBeVisible();
  await page.getByRole("link", { name: "Consistency" }).click();
  await expect(page.getByRole("columnheader", { name: /Positive months/ })).toBeVisible();
  await page.getByLabel(/Add a fund/).fill("hdfc flexi cap");
  await page.getByRole("button", { name: /HDFC Flexi Cap/i }).first().click();
  await expect(page).toHaveURL(/ids=1214,1213,\d+/);
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("risk analytics: overview, drawdown, tail and correlation", async ({ page }) => {
  await page.goto(`/risk?ids=${FUND},${REG}`);
  await expect(page.getByText(/Risk overview, 3-year window/)).toBeVisible();
  await page.getByRole("link", { name: "Drawdown", exact: true }).click();
  await expect(page.getByText("Drawdown comparison")).toBeVisible();
  await page.getByRole("link", { name: "Tail Risk" }).click();
  await expect(page.getByRole("cell", { name: "1-day VaR 95% (historical)" })).toBeVisible();
  await page.getByRole("link", { name: "Correlation" }).click();
  await expect(page.getByText(/common daily observations/)).toBeVisible();
  const diag = await page.locator("tbody td.font-mono").first().innerText();
  expect(diag).toBe("1.00");
});

test("screener can filter on NAV-derived Sharpe and shows the columns", async ({ page }) => {
  await page.goto("/screener");
  await page.getByRole("button", { name: "Add condition" }).click();
  await page.getByLabel("Field").selectOption("sharpe_3y");
  await page.getByLabel("Value", { exact: true }).fill("1");
  const count = page.getByText(/fund(s)? match/);
  await expect(count).toContainText(/^\d/); // wait for the search to finish ("Searching…" has no number)
  await expect(count).not.toContainText("3,351");
  await expect(page.locator("tbody tr td:nth-child(12)").first()).toBeVisible();
  const sharpe = await page.locator("tbody tr td:nth-child(12)").allInnerTexts();
  expect(sharpe.length).toBeGreaterThan(0);
  for (const t of sharpe) expect(Number(t)).toBeGreaterThan(1);
  await expect(page.getByRole("button", { name: /Sharpe 3Y/ })).toBeVisible();
});

test("analysis menu links to both pages", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("link", { name: /^Analysis/ }).focus();
  await expect(page.getByRole("menuitem", { name: /Risk Analytics/ })).toBeVisible();
});
