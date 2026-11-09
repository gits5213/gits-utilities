/**
 * Invoke the Python reconciliation engine with execFile.
 *
 * Arguments are passed as an array. Nothing is interpolated into a shell
 * command. A business mismatch is a normal result with passed=false.
 * Technical problems reject with ReconciliationClientError.
 */
import { execFile } from "node:child_process";

const DEFAULT_TIMEOUT_MS = 120_000;
const MAX_BUFFER_BYTES = 64 * 1024 * 1024;

export interface FieldComparison {
  field_a: string;
  field_b: string;
  value_a: string | null;
  value_b: string | null;
  status: string;
  reason: string;
  unmapped: boolean;
}

export interface ComparedRecord {
  key: string;
  key_components: string[];
  row_a: number;
  row_b: number;
  status: string;
  fields: FieldComparison[];
}

export interface ReconciliationDetails {
  compared: ComparedRecord[];
  matched: ComparedRecord[];
  mismatched: ComparedRecord[];
  missing_in_a: Array<Record<string, unknown>>;
  missing_in_b: Array<Record<string, unknown>>;
  duplicates: Array<Record<string, unknown>>;
  invalid_keys: Array<Record<string, unknown>>;
  unmapped: Array<Record<string, unknown>>;
  blocked: Array<Record<string, unknown>>;
  not_evaluated: Array<Record<string, unknown>>;
  field_issues: Array<Record<string, unknown>>;
}

export interface ReconciliationResult {
  passed: boolean;
  total_records: number;
  matched: number;
  mismatched: number;
  missing_in_a: number;
  missing_in_b: number;
  duplicates: number;
  unmapped: number;
  invalid_keys: number;
  exceptions: number;
  details: ReconciliationDetails;
  report_path: string | null;
  metadata: Record<string, unknown>;
}

export interface CompareCommonOptions {
  keyA: string | string[];
  keyB: string | string[];
  fieldMapping?: Record<string, string>;
  valueMappings?: Record<string, Record<string, string>>;
  comparisonRules?: Record<string, Record<string, unknown>>;
  ignoreCase?: boolean;
  trimWhitespace?: boolean;
  ignoreNulls?: boolean;
  numericTolerance?: number | null;
  detectDuplicates?: boolean;
  bidirectional?: boolean;
  outputPath?: string;
  generateReport?: boolean;
  pythonPath?: string;
  timeoutMs?: number;
  cwd?: string;
}

export interface CompareExcelOptions extends CompareCommonOptions {
  sourceA: string;
  sourceB: string;
  sheetA?: string | number;
  sheetB?: string | number;
}

export interface CompareCsvOptions extends CompareCommonOptions {
  sourceA: string;
  sourceB: string;
  encoding?: string;
  delimiter?: string;
}

export type ReconciliationClientErrorCode =
  | "python_not_found"
  | "timeout"
  | "invalid_json"
  | "technical_failure";

export class ReconciliationClientError extends Error {
  readonly code: ReconciliationClientErrorCode;
  readonly details: unknown;

  constructor(message: string, code: ReconciliationClientErrorCode, details?: unknown) {
    super(message);
    this.name = "ReconciliationClientError";
    this.code = code;
    this.details = details;
  }
}

export function compareExcel(options: CompareExcelOptions): Promise<ReconciliationResult> {
  const args = ["-m", "universal_utils.cli", "--source-type", "excel"];
  appendSource(args, options);
  appendSheet(args, "--sheet-a", options.sheetA);
  appendSheet(args, "--sheet-b", options.sheetB);
  appendComparison(args, options);
  return runPython(options, args);
}

export function compareCsv(options: CompareCsvOptions): Promise<ReconciliationResult> {
  const args = ["-m", "universal_utils.cli", "--source-type", "csv"];
  appendSource(args, options);
  if (options.encoding !== undefined) {
    args.push("--encoding", options.encoding);
  }
  if (options.delimiter !== undefined) {
    args.push("--delimiter", options.delimiter);
  }
  appendComparison(args, options);
  return runPython(options, args);
}

function appendSource(args: string[], options: { sourceA: string; sourceB: string }): void {
  args.push("--source-a", options.sourceA, "--source-b", options.sourceB);
}

function appendSheet(args: string[], flag: string, sheet: string | number | undefined): void {
  if (sheet !== undefined) {
    args.push(flag, String(sheet));
  }
}

function appendComparison(args: string[], options: CompareCommonOptions): void {
  appendKey(args, "--key-a", options.keyA);
  appendKey(args, "--key-b", options.keyB);
  appendJson(args, "--field-mapping", options.fieldMapping);
  appendJson(args, "--value-mappings", options.valueMappings);
  appendJson(args, "--comparison-rules", options.comparisonRules);
  appendBoolean(args, "ignore-case", options.ignoreCase);
  appendBoolean(args, "trim-whitespace", options.trimWhitespace);
  appendBoolean(args, "ignore-nulls", options.ignoreNulls);
  appendBoolean(args, "detect-duplicates", options.detectDuplicates);
  appendBoolean(args, "bidirectional", options.bidirectional);
  appendBoolean(args, "generate-report", options.generateReport);
  if (options.numericTolerance !== undefined && options.numericTolerance !== null) {
    args.push("--numeric-tolerance", String(options.numericTolerance));
  }
  if (options.outputPath !== undefined) {
    args.push("--output-path", options.outputPath);
  }
}

function appendKey(args: string[], flag: string, key: string | string[]): void {
  const columns = Array.isArray(key) ? key : [key];
  if (columns.length === 0 || columns.some((column) => column.trim() === "")) {
    throw new ReconciliationClientError(`${flag} must name at least one column.`, "technical_failure");
  }
  for (const column of columns) {
    args.push(flag, column);
  }
}

function appendJson(args: string[], flag: string, value: unknown): void {
  if (value !== undefined) {
    args.push(flag, JSON.stringify(value));
  }
}

function appendBoolean(args: string[], name: string, value: boolean | undefined): void {
  if (value === undefined) {
    return;
  }
  args.push(value ? `--${name}` : `--no-${name}`);
}

function pythonCommand(options: { pythonPath?: string }): string {
  if (options.pythonPath !== undefined && options.pythonPath.trim() !== "") {
    return options.pythonPath;
  }
  if (process.env.PYTHON !== undefined && process.env.PYTHON.trim() !== "") {
    return process.env.PYTHON;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function runPython(options: CompareCommonOptions, args: string[]): Promise<ReconciliationResult> {
  const command = pythonCommand(options);
  const timeout = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  return new Promise((resolve, reject) => {
    execFile(
      command,
      args,
      {
        cwd: options.cwd,
        timeout,
        windowsHide: true,
        maxBuffer: MAX_BUFFER_BYTES,
        encoding: "utf8",
      },
      (error, stdout, stderr) => {
        const stdoutText = textOf(stdout);
        const stderrText = textOf(stderr);
        if (error) {
          const errno = error as { code?: unknown; killed?: boolean };
          if (errno.code === "ENOENT") {
            reject(
              new ReconciliationClientError(
                `Python executable was not found: ${command}`,
                "python_not_found",
              ),
            );
            return;
          }
          if (errno.killed || errno.code === "ETIMEDOUT") {
            reject(
              new ReconciliationClientError(
                `Python comparison timed out after ${timeout} ms.`,
                "timeout",
              ),
            );
            return;
          }
        }
        const exitCode = typeof error?.code === "number" ? error.code : error ? 1 : 0;
        if (exitCode === 0 || exitCode === 2) {
          try {
            resolve(parseResult(stdoutText));
          } catch (parseError) {
            reject(parseError);
          }
          return;
        }
        reject(technicalFailure(exitCode, stdoutText, stderrText));
      },
    );
  });
}

function parseResult(stdout: string): ReconciliationResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new ReconciliationClientError("Python returned invalid JSON.", "invalid_json", {
      stdout: stdout.slice(0, 500),
    });
  }
  if (!isResult(parsed)) {
    throw new ReconciliationClientError(
      "Python returned JSON that is not a reconciliation result.",
      "invalid_json",
      { stdout: stdout.slice(0, 500) },
    );
  }
  return parsed;
}

function isResult(value: unknown): value is ReconciliationResult {
  if (value === null || typeof value !== "object") {
    return false;
  }
  return typeof (value as { passed?: unknown }).passed === "boolean";
}

function technicalFailure(exitCode: number, stdout: string, stderr: string): ReconciliationClientError {
  let message = `Python comparison failed with exit code ${exitCode}.`;
  try {
    const parsed = JSON.parse(stdout) as { message?: unknown; error_type?: unknown };
    if (typeof parsed.message === "string" && parsed.message.trim() !== "") {
      const errorType = typeof parsed.error_type === "string" ? parsed.error_type : "Error";
      message = `${errorType}: ${parsed.message}`;
    }
  } catch {
    if (stderr.trim() !== "") {
      message = stderr.trim().slice(0, 2000);
    }
  }
  return new ReconciliationClientError(message, "technical_failure", {
    exitCode,
    stdout: stdout.slice(0, 2000),
    stderr: stderr.slice(0, 2000),
  });
}

function textOf(value: string | Buffer | undefined): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined) {
    return "";
  }
  return value.toString("utf8");
}
