import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import {
  compareExcel,
  type ReconciliationResult,
} from "../adapters/playwright/reconciliation-client";

const ledgerDir = process.env.LEDGER_DIR;
if (ledgerDir === undefined || ledgerDir.trim() === "") {
  throw new Error("LEDGER_DIR must point at a materialized ledger fixture.");
}

const config = readJson(path.join(ledgerDir, "reconciliation.json"));
const expected = readJson(path.join(ledgerDir, "expected.json"));
const pythonPath = process.env.PYTHON;

test("shared ledger fixture returns the business failure", async () => {
  const result = await compareExcel({
    sourceA: path.join(ledgerDir, String(config.source_a)),
    sourceB: path.join(ledgerDir, String(config.source_b)),
    sheetA: config.sheet_a as string,
    sheetB: config.sheet_b as string,
    keyA: config.key_a as string,
    keyB: config.key_b as string,
    fieldMapping: config.field_mapping as Record<string, string>,
    valueMappings: config.value_mappings as Record<string, Record<string, string>>,
    numericTolerance: config.numeric_tolerance as number,
    generateReport: true,
    outputPath: path.join(ledgerDir, String(config.output_path)),
    pythonPath,
    cwd: ledgerDir,
  });

  expect(result.passed).toBe(false);
  expect(metrics(result)).toEqual(expected.metrics);
  expect(Object.keys(result)).toEqual(expected.result_keys);
  expect(Object.keys(result.details).sort()).toEqual([...expected.detail_keys].sort());
  for (const category of Object.keys(expected.keys as Record<string, string[]>)) {
    expect(recordKeys(result, category)).toEqual((expected.keys as Record<string, string[]>)[category]);
  }
  expect(fieldIssues(result)).toEqual(expected.field_issues);
  expect(result.metadata.schema_version).toBe(expected.schema_version);
  expect(result.metadata.library_version).toBe(expected.library_version);
  expect(result.metadata.numeric_tolerance).toBe("0.01");
  expect(result.report_path).toBe(path.resolve(ledgerDir, String(config.output_path)));
});

test("missing workbook is a technical failure", async () => {
  await expect(
    compareExcel({
      sourceA: path.join(ledgerDir, "missing_a.xlsx"),
      sourceB: path.join(ledgerDir, "missing_b.xlsx"),
      keyA: "Account",
      keyB: "Account ID",
      pythonPath,
      cwd: ledgerDir,
    }),
  ).rejects.toMatchObject({ code: "technical_failure" });
});

function metrics(result: ReconciliationResult): Record<string, boolean | number> {
  return {
    passed: result.passed,
    total_records: result.total_records,
    matched: result.matched,
    mismatched: result.mismatched,
    missing_in_a: result.missing_in_a,
    missing_in_b: result.missing_in_b,
    duplicates: result.duplicates,
    unmapped: result.unmapped,
    invalid_keys: result.invalid_keys,
    exceptions: result.exceptions,
  };
}

function recordKeys(result: ReconciliationResult, category: string): string[] {
  const rows = result.details[category as keyof ReconciliationResult["details"]] as Array<{
    key: string;
  }>;
  return rows.map((row) => row.key);
}

function fieldIssues(result: ReconciliationResult): Array<Record<string, string>> {
  return result.details.field_issues.map((issue) => ({
    key: String(issue.key),
    field_a: String(issue.field_a),
    reason: String(issue.reason),
    value_a: String(issue.value_a),
    value_b: String(issue.value_b),
  }));
}

function readJson(file: string): Record<string, unknown> {
  return JSON.parse(readFileSync(file, "utf8")) as Record<string, unknown>;
}
