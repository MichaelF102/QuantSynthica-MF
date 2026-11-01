import { expect, test, type Page } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;
const stamp = Date.now();

async function register(page: Page) {
  await page.goto("/account");
  await page.getByRole("button", { name: /New here/ }).click();
  await page.getByLabel("Email").fill(`e2e-${stamp}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel(/^Password/).fill("correct-horse-battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Saved items" })).toBeVisible({ timeout: 15_000 });
}

test("AMC page ranks fund houses with the survivorship caveat and links to detail", async ({ page }) => {
  await page.goto("/amc");
  await expect(page.getByRole("heading", { name: /AMC\s*Intelligence/ })).toBeVisible();
  await expect(page.getByText(/not shown a net-of-cost selection edge|has not shown/)).toBeVisible();
  expect(await page.locator("tbody tr").count()).toBeGreaterThan(5);
  await page.locator("tbody tr").first().getByRole("link").click();
  await expect(page.getByRole("heading", { name: "By category" })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("AMC report downloads as Excel and PDF", async ({ page }) => {
  await page.goto("/amc");
  for (const [label, ext] of [["Excel report", "xlsx"], ["PDF report", "pdf"]] as const) {
    const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 30_000 }), page.getByRole("button", { name: label }).click()]);
    expect(dl.suggestedFilename()).toBe(`qsmf-amc-report.${ext}`);
  }
});

test("fund page offers reports and a watch prompt when signed out", async ({ page }) => {
  await page.goto("/funds/352");
  await expect(page.getByRole("button", { name: "PDF report" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Sign in to watch/ })).toBeVisible();
});

test("assistant needs sign-in", async ({ page }) => {
  await page.goto("/assistant");
  await expect(page.getByText("Sign in to use the assistant")).toBeVisible();
});

test("account: register, watch a fund, see it saved, sign out, bad login is explained", async ({ page }) => {
  await register(page);
  await page.goto("/funds/352");
  await page.getByRole("button", { name: "Watch", exact: true }).click();
  await expect(page.getByRole("button", { name: "Watching" })).toBeVisible();
  await page.goto("/account");
  await expect(page.getByText("Watchlist", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel(/^Password/).fill("wrong-password-1");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/incorrect email or password/)).toBeVisible();
});

test("assistant: sourced facts, refusal of advice, unknown fund not guessed", async ({ page }) => {
  await register(page);
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How risky is Tata India Consumer?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("3Y volatility").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/official NAV records/).first()).toBeVisible();
  await expect(page.getByText(/not investment advice/).first()).toBeVisible();
  await page.getByLabel("Your question").fill("Should I buy Tata India Consumer?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/can't recommend what to buy or sell/)).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Your question").fill("How risky is Zzyzx Quantum?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/won't guess/)).toBeVisible({ timeout: 30_000 });
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

for (const w of [375, 1280, 1920]) {
  test(`no horizontal overflow on phase 7 pages at ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 900 });
    const id = (await (await page.request.get("http://localhost:8000/api/v1/amcs")).json()).amcs[0].amc_id;
    for (const path of ["/amc", `/amc/${id}`, "/account", "/assistant", "/funds/352"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over, `${path} at ${w}`).toBeLessThanOrEqual(1);
    }
  });
}
