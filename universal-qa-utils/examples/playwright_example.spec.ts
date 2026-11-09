import { execFile } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

import { compareExcel } from "../adapters/playwright/reconciliation-client";

const run = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));

test.beforeAll(async () => {
  const python = process.env.PYTHON ?? "python3";
  await run(python, [path.join(here, "cam_mdg_example.py"), "--write-only"]);
});

test("synthetic workbooks reconcile through the Python engine", async () => {
  const result = await compareExcel({
    sourceA: path.join(here, "demo-output", "CAM.xlsx"),
    sourceB: path.join(here, "demo-output", "MDG.xlsx"),
    sheetA: "CAM",
    sheetB: "MDG",
    keyA: "PCID",
    keyB: "ID",
    fieldMapping: {
      "PCID Name": "Name",
      "PCID Description": "Program Description",
      "Status Code": "Status Description",
    },
    valueMappings: {
      "Status Code": {
        S0011: "Abandoned",
        S0023: "Approved",
      },
    },
    pythonPath: process.env.PYTHON,
  });

  expect(result.passed).toBe(true);
  expect(result.exceptions).toBe(0);
});
