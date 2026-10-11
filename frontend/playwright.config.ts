import { defineConfig } from "@playwright/test";

const apiBase = process.env.CIVSIM_API_BASE || "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: apiBase,
    extraHTTPHeaders: { Accept: "application/json" },
  },
  projects: [{ name: "api-smoke", testMatch: /.*\.spec\.ts/ }],
});
