import { defineConfig, devices } from "@playwright/test";

const baseURL = "http://localhost:13000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "node e2e/mock-api.mjs",
      url: "http://localhost:18081/health",
      reuseExistingServer: false,
      timeout: 10_000,
    },
    {
      command: "npm run start:e2e",
      url: baseURL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_SHOW_DEMO_LOGINS: "true",
        API_BASE_URL: "http://localhost:18081",
      },
    },
  ],
});
