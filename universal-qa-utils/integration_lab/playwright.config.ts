import { defineConfig } from "@playwright/test";

const reportFile = process.env.LEDGER_PLAYWRIGHT_REPORT ?? "ledger-playwright.json";

export default defineConfig({
  testDir: ".",
  testMatch: "playwright_ledger.spec.ts",
  timeout: 120_000,
  reporter: [["line"], ["json", { outputFile: reportFile }]],
});
