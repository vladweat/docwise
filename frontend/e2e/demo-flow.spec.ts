import { expect, test } from "@playwright/test";

test("browser tab uses page-specific titles and a favicon", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("dw_locale", "ru"));
  await page.goto("/");
  await expect.poll(() => page.title()).toBe("Чат — Docwise");
  const iconHref = await page.locator('link[rel="icon"]').first().getAttribute("href");
  expect(iconHref).toMatch(/icon\.svg/);

  await page.getByRole("button", { name: "en", exact: true }).click();
  await expect.poll(() => page.title()).toBe("Chat — Docwise");
  await page.locator("header").getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/login");
  await expect.poll(() => page.title()).toBe("Sign in — Docwise");
});

test("mobile chat empty state omits the extra bottom section", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login?mode=demo");
  await page.getByRole("button", { name: "Employee" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Ask about your documents" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New", exact: true })).toHaveCount(0);
  await expect(page.getByText("On mobile, a citation opens the document in full screen.")).toHaveCount(0);
});

test("login shows a new session before the answer, then opens its PDF citation", async ({ page }) => {
  await page.goto("/login?mode=demo");
  await page.getByRole("button", { name: "Employee" }).click();
  await expect(page).toHaveURL("/");

  await page.getByPlaceholder("Ask about documents…").fill("What are the core working hours?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page).toHaveURL(/\/chat\/22222222-2222-4222-8222-222222222222$/);
  await page.getByRole("button", { name: "Sessions" }).click();
  await expect(page.getByRole("link", { name: /What are the core working hours/ })).toBeVisible();
  await expect(page.getByText("Core working hours are 09:00 to 18:00.")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByText("Core working hours are 09:00 to 18:00.")).toBeVisible();

  await page.getByRole("button", { name: /Employee Handbook\.pdf/ }).click();
  await expect(page.getByText("Employee Handbook.pdf", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Hide document pane" })).toHaveCount(1);
  await expect(page.getByText("p. 1 · snippet highlighted", { exact: true })).toBeVisible();
  await expect(page.getByText("Core working hours are 09:00 to 18:00.")).toBeVisible();
});

test("mobile document cards follow the selected locale and keep title metadata compact", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login?mode=demo");
  await page.getByRole("button", { name: "Employee" }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/documents");

  const row = page.locator("tr").filter({ hasText: "Employee Handbook.pdf" }).first();
  await expect(row).toBeVisible();
  await page.getByLabel("employee@docwise.example.com").first().click();
  await page.getByRole("button", { name: "ru", exact: true }).first().click();
  const russianDate = await page.evaluate(() =>
    new Date("2026-01-01T00:00:00Z").toLocaleString("ru-RU", {
      dateStyle: "short",
      timeStyle: "short",
    }),
  );
  const date = row.getByText(russianDate, { exact: true });
  await expect(date).toBeVisible();

  const titleBox = await row.getByText("Employee Handbook.pdf", { exact: true }).boundingBox();
  const dateBox = await date.boundingBox();
  expect(titleBox).not.toBeNull();
  expect(dateBox).not.toBeNull();
  expect(Math.abs((titleBox!.y + titleBox!.height / 2) - (dateBox!.y + dateBox!.height / 2))).toBeLessThan(8);

  await page.getByRole("button", { name: "en", exact: true }).first().click();
  const englishDate = await page.evaluate(() =>
    new Date("2026-01-01T00:00:00Z").toLocaleString("en-US", {
      dateStyle: "short",
      timeStyle: "short",
    }),
  );
  await expect(row.getByText(englishDate, { exact: true })).toBeVisible();
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
  await page.getByRole("checkbox", { name: "General" }).check();
  await page.getByRole("button", { name: "Upload", exact: true }).click();

  const uploadedDocument = page.getByRole("row", { name: /Interview-demo\.pdf/ });
  await expect(uploadedDocument).toBeVisible();
  await expect(uploadedDocument.getByRole("cell", { name: "ready", exact: true })).toBeVisible({ timeout: 8_000 });
});
