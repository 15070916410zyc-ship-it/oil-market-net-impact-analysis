import { expect, test } from "@playwright/test";

test("professional controls and English dates are fully localized", async ({ page }) => {
  await page.goto("http://localhost:4174/professional");
  await expect(page.getByRole("heading", { name: "多尺度净影响分析" })).toBeVisible();
  await page.locator(".utility button").click();
  await expect(page.getByRole("heading", { name: "Multi-scale net-impact analysis" })).toBeVisible();
  await expect(page.locator("input[type=date]")).toHaveCount(0);
  await expect(page.locator(".date-field input").first()).toHaveAttribute("placeholder", "YYYY-MM-DD");
  await expect(page.locator(".date-field em").first()).toHaveText("YYYY-MM-DD");
});

test("number steppers and mode switching respond immediately", async ({ page }) => {
  await page.goto("http://localhost:4174/professional");
  const componentField = page.locator(".field").filter({ hasText: "分量数量" });
  await expect(componentField.locator("input")).toHaveValue("5");
  await componentField.locator(".stepper button").last().click();
  await expect(componentField.locator("input")).toHaveValue("6");
  await page.getByRole("button", { name: "决策模式" }).click();
  await expect(page).toHaveURL(/\/decision$/);
  await page.getByRole("button", { name: "专业模式" }).click();
  await expect(page).toHaveURL(/\/professional$/);
});
