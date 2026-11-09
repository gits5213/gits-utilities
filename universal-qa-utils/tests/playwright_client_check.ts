/**
 * Exercise the Playwright client without starting Playwright.
 * Node runs this file directly with type stripping.
 */
import { compareCsv, compareExcel, ReconciliationClientError } from "../adapters/playwright/reconciliation-client.ts";

function argument(name: string): string {
  const index = process.argv.indexOf(name);
  const value = index === -1 ? undefined : process.argv[index + 1];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`Missing ${name}`);
  }
  return value;
}

async function expectCode(action: () => Promise<unknown>, code: string): Promise<void> {
  try {
    await action();
  } catch (error) {
    if (error instanceof ReconciliationClientError && error.code === code) {
      return;
    }
    throw error;
  }
  throw new Error(`Expected ${code}.`);
}

const pythonPath = argument("--python");
const matchA = argument("--match-a");
const matchB = argument("--match-b");
const mismatchA = argument("--mismatch-a");
const mismatchB = argument("--mismatch-b");
const csvA = argument("--csv-a");
const csvB = argument("--csv-b");
const missingPython = argument("--missing-python");
const badJsonPython = argument("--bad-json-python");
const sleepPython = argument("--sleep-python");

const matched = await compareExcel({
  sourceA: matchA,
  sourceB: matchB,
  sheetA: "Data",
  sheetB: "Data",
  keyA: "ID",
  keyB: "ID",
  fieldMapping: { Name: "Name" },
  pythonPath,
});
if (matched.passed !== true || matched.exceptions !== 0) {
  throw new Error(`Expected a passing Excel result, got exceptions=${matched.exceptions}.`);
}

const mismatched = await compareExcel({
  sourceA: mismatchA,
  sourceB: mismatchB,
  keyA: "ID",
  keyB: "ID",
  pythonPath,
});
if (mismatched.passed !== false || mismatched.mismatched !== 1 || mismatched.exceptions !== 1) {
  throw new Error("Expected a business mismatch to come back as a result.");
}

const csv = await compareCsv({
  sourceA: csvA,
  sourceB: csvB,
  keyA: "ID",
  keyB: "ID",
  delimiter: ";",
  pythonPath,
});
if (csv.passed !== true || csv.details.matched[0]?.key !== "001") {
  throw new Error("Expected the CSV client call to preserve the key.");
}

await expectCode(
  () =>
    compareExcel({
      sourceA: matchA,
      sourceB: matchB,
      keyA: "ID",
      keyB: "ID",
      pythonPath: missingPython,
    }),
  "python_not_found",
);
await expectCode(
  () =>
    compareExcel({
      sourceA: matchA,
      sourceB: matchB,
      keyA: "ID",
      keyB: "ID",
      pythonPath: badJsonPython,
    }),
  "invalid_json",
);
await expectCode(
  () =>
    compareExcel({
      sourceA: matchA,
      sourceB: "does-not-exist.xlsx",
      keyA: "ID",
      keyB: "ID",
      pythonPath,
    }),
  "technical_failure",
);
await expectCode(
  () =>
    compareExcel({
      sourceA: matchA,
      sourceB: matchB,
      keyA: "ID",
      keyB: "ID",
      pythonPath: sleepPython,
      timeoutMs: 400,
    }),
  "timeout",
);
