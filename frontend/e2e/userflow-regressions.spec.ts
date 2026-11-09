import { expect, test, type Page } from "@playwright/test";

const sessionAlpha = "66666666-6666-4666-8666-666666666666";
const sessionBeta = "77777777-7777-4777-8777-777777777777";

async function signInQaUser(page: Page) {
  await page.goto("/login?mode=demo");
  await page.getByRole("tab", { name: "Email and password" }).click();
  await page.getByLabel("Email").fill("qa@docwise.example.com");
  await page.getByLabel("Password").fill("qa-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");
}

test("failed history load never leaves the previous session visible or sendable", async ({ page }) => {
  await signInQaUser(page);
  await page.goto(`/chat/${sessionAlpha}`);
  await expect(page.getByText("History from session Alpha")).toBeVisible();

  await page.getByRole("button", { name: "Sessions" }).click();
  await page.getByRole("link", { name: "Session Beta" }).click();

  await expect(page).toHaveURL(`/chat/${sessionBeta}`);
  await expect(page.getByText("Could not load chat history")).toBeVisible();
  await expect(page.getByText("History from session Alpha")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("History from session Beta")).toBeVisible();
  await page.getByPlaceholder("Ask about documents…").fill("Question after retry");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
});

test("switching organizations leaves the old chat route before the next question", async ({ page }) => {
  await signInQaUser(page);
  await page.goto(`/chat/${sessionAlpha}`);
  await expect(page.getByText("History from session Alpha")).toBeVisible();

  await page.getByLabel("qa@docwise.example.com").last().click();
  await page.getByRole("combobox", { name: "Organization" }).first().click();
  await page.getByRole("option", { name: "Workspace Two" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Ask about your documents" })).toBeVisible();
  await expect(page.getByText("History from session Alpha")).toHaveCount(0);

  const streamRequestPromise = page.waitForRequest((request) =>
    request.url().endsWith("/api/v1/chat/stream"),
  );
  await page.getByPlaceholder("Ask about documents…").fill("Question in workspace two");
  await page.getByRole("button", { name: "Send" }).click();
  const streamRequest = await streamRequestPromise;
  expect(streamRequest.postDataJSON().session_id).toBeNull();
});

test("a partial answer followed by an SSE error is visibly marked as incomplete", async ({ page }) => {
  await signInQaUser(page);
  await page.getByPlaceholder("Ask about documents…").fill("Trigger the broken stream");
  await page.getByRole("button", { name: "Send" }).click();

  const partialAnswer = page.getByText("Partial answer before stream failure", { exact: true });
  await expect(partialAnswer).toBeVisible();
  await expect(page.locator('[class*="border-red-500/40"]')).toContainText(
    "Partial answer before stream failure",
  );
});

test("rejecting a new upload clears the previously selected file", async ({ page }) => {
  await page.goto("/login?mode=demo");
  await page.getByRole("tab", { name: "Email and password" }).click();
  await page.getByLabel("Email").fill("admin@docwise.example.com");
  await page.getByLabel("Password").fill("demo-admin-pass");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/documents");
  await page.getByRole("button", { name: "Upload PDF" }).click();

  const input = page.locator('input[type="file"]');
  await input.setInputFiles({
    name: "accepted.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 fixture"),
  });
  await page.getByRole("checkbox", { name: "General" }).check();
  await input.setInputFiles({ name: "rejected.txt", mimeType: "text/plain", buffer: Buffer.from("not a document") });

  await expect(page.getByText("PDF or DOCX only")).toBeVisible();
  await expect(page.getByText("accepted.pdf", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Upload", exact: true })).toBeDisabled();
});
