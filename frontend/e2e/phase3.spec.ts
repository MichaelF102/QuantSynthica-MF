import { expect, test } from "@playwright/test";

const BAD = /NaN|undefined|Infinity|\[object Object\]/;

test("coverage page shows mapping status, NAV history and the estimated snapshot date", async ({ page }) => {
  await page.goto("/coverage");
  await expect(page.getByRole("heading", { name: /Data Coverage/ })).toBeVisible();
  await expect(page.getByText("Mapping status")).toBeVisible();
  await expect(page.getByText("Confirmed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Snapshot date (estimated)")).toBeVisible();
  await expect(page.getByText("NAV history", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Report generated/)).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(BAD);
});

test("coverage is reachable from the navigation", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("link", { name: "Data Coverage" }).click();
  await expect(page).toHaveURL(/\/coverage/);
});
