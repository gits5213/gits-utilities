import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "examples",
  testMatch: "playwright_example.spec.ts",
  timeout: 120_000,
  reporter: "line",
});
