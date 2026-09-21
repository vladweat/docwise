/**
 * Optional: automated PNG capture for docs/portfolio/screenshots/ (Playwright + Chromium).
 * Canonical path for portfolio B is manual capture — see docs/portfolio/screenshots/README.md.
 *
 * Usage: node scripts/capture-portfolio-screenshots.mjs
 * Prereq: make up && make demo; OPENAI_API_KEY in .env; playwright installed under scripts/.
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE = process.env.DOCWISE_SCREENSHOT_BASE ?? "http://localhost:3001";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "..", "docs", "portfolio", "screenshots");

const HOURS_Q = "What are the core working hours at Docwise?";
const SALARY_Q = "What is the individual contributor L3 salary band in USD?";
const NO_CONTEXT =
  "В предоставленных документах нет информации по данному вопросу.";

async function demoLogin(page, shortLabel) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: shortLabel, exact: true }).click();
  await page.waitForURL(/\/(chat)?(\?.*)?$/, { timeout: 60_000 });
  await page.waitForLoadState("networkidle");
}

async function askSuggestion(page, question) {
  // Session sidebar delete buttons include the title in aria-label — use exact match on chips only.
  const btn = page.getByRole("button", { name: question, exact: true });
  await btn.waitFor({ state: "visible", timeout: 30_000 });
  await btn.click();
}

async function waitForAssistantDone(page, expectText) {
  const locator = page.locator("text=Docwise").last();
  await locator.waitFor({ state: "visible", timeout: 120_000 });
  if (expectText) {
    await page.getByText(expectText, { exact: false }).last().waitFor({
      state: "visible",
      timeout: 120_000,
    });
  }
  await page.waitForTimeout(800);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  // 1 — chat + citation (employee, working hours)
  await demoLogin(page, "Сотрудник");
  await askSuggestion(page, HOURS_Q);
  await waitForAssistantDone(page, "working hours");
  await page.screenshot({ path: path.join(OUT, "01-chat-citation.png"), fullPage: false });

  // 2 — PDF highlight (click first citation chip)
  const citation = page.getByRole("button").filter({ hasText: /стр\./ }).first();
  await citation.click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(OUT, "02-pdf-highlight.png"), fullPage: false });

  // 3 — ACL refuse (salary as employee) — new chat session
  await page.getByRole("button", { name: /Новая/ }).click();
  await page.waitForURL(/\/(\?.*)?$/, { timeout: 30_000 });
  await askSuggestion(page, SALARY_Q);
  await waitForAssistantDone(page, NO_CONTEXT);
  await page.screenshot({ path: path.join(OUT, "03-acl-refuse.png"), fullPage: false });

  // 4 — inspect (admin). Default UI query is salary; demo admin has no `hr` → empty reranked, no table.
  await page.getByRole("button", { name: "Выйти" }).click();
  await page.waitForURL(/\/login/, { timeout: 30_000 });
  await demoLogin(page, "Admin");
  await page.goto(`${BASE}/inspect`, { waitUntil: "networkidle" });
  await page.locator("#inspect-query").fill(HOURS_Q);
  await page.getByRole("button", { name: "Прогнать" }).click();
  await page.getByRole("tab", { name: /dense \(\d+\)/ }).waitFor({ timeout: 120_000 });
  const denseTab = page.getByRole("tab", { name: /dense \((\d+)\)/ });
  const denseCount = Number((await denseTab.textContent())?.match(/\((\d+)\)/)?.[1] ?? "0");
  const rerankedTab = page.getByRole("tab", { name: /reranked \((\d+)\)/ });
  const rerankedCount = Number((await rerankedTab.textContent())?.match(/\((\d+)\)/)?.[1] ?? "0");
  if (rerankedCount > 0) {
    await rerankedTab.click();
    await page.waitForSelector("table tbody tr", { timeout: 30_000 });
  } else if (denseCount > 0) {
    await denseTab.click();
    await page.waitForSelector("table tbody tr", { timeout: 30_000 });
  } else {
    throw new Error("Inspect returned no hits on dense/reranked for handbook query");
  }
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "04-inspect-pipeline.png"), fullPage: false });

  await browser.close();
  console.log(`Wrote PNGs to ${OUT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
