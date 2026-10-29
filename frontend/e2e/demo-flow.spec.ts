import { expect, test } from "@playwright/test";

test("login shows a new session before the answer, then opens its PDF citation", async ({ page }) => {
  await page.goto("/login?mode=demo");
  await page.getByRole("button", { name: "Employee" }).click();
  await expect(page).toHaveURL("/");

  await page.getByPlaceholder("Question about corporate documents…").fill("What are the core working hours?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page).toHaveURL(/\/chat\/22222222-2222-4222-8222-222222222222$/);
  await expect(page.getByRole("link", { name: /What are the core working hours/ })).toBeVisible();
  await expect(page.getByText("Core working hours are 09:00 to 18:00.")).toHaveCount(0);

  await page.getByRole("button", { name: /Employee Handbook\.pdf/ }).click();
  await expect(page.getByText("Employee Handbook.pdf", { exact: true })).toBeVisible();
  await expect(page.getByText("p. 1 · snippet highlighted", { exact: true })).toBeVisible();
  await expect(page.getByText("Core working hours are 09:00 to 18:00.")).toBeVisible();
});

test("admin can upload a PDF and see indexing finish", async ({ page }) => {
  await page.goto("/login?mode=demo");
  await page.getByRole("tab", { name: "Email and password" }).click();
  await page.getByLabel("Email").fill("admin@docwise.example.com");
  await page.getByLabel("Password").fill("demo-admin-pass");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/documents");

  await page.getByRole("button", { name: "Upload PDF" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "Interview-demo.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 fixture"),
  });
  await page.getByRole("button", { name: "Upload", exact: true }).click();

  const uploadedDocument = page.getByRole("row", { name: /Interview-demo\.pdf/ });
  await expect(uploadedDocument).toBeVisible();
  await expect(uploadedDocument.getByRole("cell", { name: "ready", exact: true })).toBeVisible({ timeout: 8_000 });
});
