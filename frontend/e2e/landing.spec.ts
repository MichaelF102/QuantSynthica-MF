import { expect, test } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;

test("the landing page is the first page and has every section in order", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Beyond Returns.");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Into Intelligence.");
  await page.waitForLoadState("networkidle");
  const ids = ["kpiScroll", "ecosystem", "explore", "engine", "risk", "portfolios", "regimes", "assistant", "methodology", "cta"];
  let last = -1;
  for (const id of ids) {
    const y = await page.locator(`section#${id}`).evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
    expect(y, `${id} appears after the previous section`).toBeGreaterThan(last);
    last = y;
  }
  await expect(page.getByRole("heading", { name: /evidence, not headlines/ })).toBeAttached();
  await expect(page.getByRole("contentinfo")).toContainText("not investment advice");
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("platform statistics are real numbers from the API (or dashes), never invented", async ({ page, request }) => {
  const api = await (await request.get("http://localhost:8000/api/v1/platform-stats")).json();
  await page.goto("/");
  const list = page.locator("section#kpiScroll .kl-list");
  await expect(list).toContainText("Funds covered");
  await expect(list).toContainText(api.funds.toLocaleString("en-IN"));
  await expect(list).toContainText(api.funds_scored.toLocaleString("en-IN"));
});

test("launching the platform leads into the application with its own navigation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Launch platform" }).first().click();
  await expect(page).toHaveURL(/\/overview/);
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
});

test("explore tiles open working pages", async ({ page }) => {
  await page.goto("/");
  await page.locator("section#explore").getByRole("link", { name: /Screener/ }).click();
  await expect(page).toHaveURL(/\/screener/);
});

test("mobile menu opens, closes with Escape and links to sections", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.getByRole("navigation", { name: "Landing sections (mobile)" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: "Landing sections (mobile)" })).toBeHidden();
});

test("theme toggle switches the landing page between dark and light", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch colour theme" }).click();
  await expect(page.locator(".qsl")).toHaveAttribute("data-theme", "light");
});

for (const w of [375, 1280, 1920]) {
  test(`no horizontal overflow on the landing page at ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 900 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  });
}
