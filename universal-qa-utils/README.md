# universal-qa-utils

Parameter-driven reconciliation for Python test automation. Comparison rules live in the function arguments, so the same engine can check any two Excel files, CSV files, or pandas DataFrames.

The comparison engine and the Robot Framework library ship in the Python wheel. The Playwright client and the Tosca PowerShell script stay in this repository. They call that same engine. They do not reimplement the comparison.

```bash
pip install -e ".[dev]"
```

Python 3.11 or newer is required. Version 0.1.0 is the production release:

```bash
python -m pip install "universal-qa-utils==0.1.0"
```

Project page: https://pypi.org/project/universal-qa-utils/0.1.0/

Version 0.1.1 is in development on `development/v0.1.1` and is not on PyPI. Install a wheel built from this branch, including its dependencies, with:

```bash
python -m pip install dist/universal_qa_utils-0.1.1-py3-none-any.whl
```

Robot Framework is optional. It is not required for the comparison engine or the command-line interface:

```bash
python -m pip install "dist/universal_qa_utils-0.1.1-py3-none-any.whl[robot]"
```

Another project can import the installed package without copying these files:

```python
from universal_utils.reconciliation import compare_excel
```

## Quick start

`examples/python_example.py` builds two synthetic workbooks and compares them. The workbooks use different sheet names, key names, and column names. A status code is translated through `value_mappings`, and amounts that look different as text match within `numeric_tolerance`.

```bash
python examples/python_example.py
```

The example prints `result.passed`, `result.exceptions`, and `result.to_json()`.

```python
result = compare_excel(
    source_a="accounts.xlsx",
    source_b="directory.xlsx",
    sheet_a="Accounts",
    sheet_b="Directory",
    key_a="Customer ID",
    key_b="Cust ID",
    field_mapping={
        "Customer Name": "Name",
        "Status Code": "Status",
        "Amount": "Amount",
    },
    value_mappings={
        "Status Code": {"S0011": "Active", "S0023": "Closed"}
    },
    numeric_tolerance=0.01,
)
```

`compare_csv` reads CSV files. `reconcile_data` reads pandas DataFrames. All three call `reconcile_tables`.

```bash
qa-utils --source-type csv --source-a left.csv --source-b right.csv --key-a ID --key-b ID
```

An empty `key_a` or `key_b` raises `ValidationError` before either source is read. Missing files, unknown sheets, and missing columns also raise. A field mismatch, a missing key, or a duplicate key does not raise. Those outcomes are on the result, and `result.passed` is `False`.

## Result

`ReconciliationResult` exposes:

| Attribute | Meaning |
| --- | --- |
| `passed` | `True` only when `exceptions` is 0. |
| `total_records` | Non-blank data rows from both sources. A row is blank when every cell is empty after the trim setting. |
| `matched` | Keys present once on each side whose compared fields match and whose mapped codes were all recognized. |
| `mismatched` | Keys present once on each side with at least one field difference. |
| `missing_in_a` | Keys present once in source B and absent from source A. This is 0 when `bidirectional` is `False`. |
| `missing_in_b` | Keys present once in source A and absent from source B. |
| `duplicates` | In-scope rows whose key occurs more than once in that source. |
| `unmapped` | Compared keys with at least one source A code that has a mapping but is not in it. A key can be both mismatched and unmapped. |
| `invalid_keys` | Non-blank rows with an empty key or an empty composite-key component. They are not also counted as missing. |
| `exceptions` | Distinct failing rows and keys. A key that is both mismatched and unmapped counts once. |
| `details` | Record lists plus `field_issues`, which stores every field-level problem separately. |
| `report_path` | Absolute report path after `generate_report=True`; otherwise `None`. |

`details` also contains `blocked` and `not_evaluated`. Those lists explain rows that were not paired. They do not have their own top-level counts.

- `blocked`: a unique row whose key is duplicated on the other side. The duplicate rows hold the exception.
- `not_evaluated`: source B rows left out because `bidirectional` is `False` and the key is not in source A.

`result.to_dict()` and `result.to_json()` are deterministic for the same inputs. JSON objects are serialized with sorted keys. The report timestamp is written only into the workbook, not into the result.

Category lists line up with their metrics: `len(result.details["matched"]) == result.matched`, and the same is true for the other counted categories. `field_issues` is the field-level list and is not itself a metric.

## Comparison behavior

Keys may be one column or a list of columns. Composite values are joined with `||` for display and compared as a tuple, so a value that contains `||` cannot make two different keys look like one key to the engine. Key text keeps leading zeros. Store identifiers as text in Excel; a numeric cell has already lost those zeros before this library reads it.

`ignore_case` applies to key identity and to string fields. It does not apply to numeric or date comparisons. `trim_whitespace` applies to keys and values and is `True` by default. Headers are always stripped, even when value trimming is off. The strings `null`, `None`, and `N/A` stay literal text. Only empty cells, pandas missing values, and whitespace (when trimming) become null.

`ignore_nulls` controls null against a real value. Null against null matches either way. `ignore_nulls` does not turn an empty key into a valid key.

`field_mapping` maps a source A column to a source B column. `None` compares columns that share a name, excluding the source A key columns. `{}` compares keys only. `value_mappings` translates source A values before the comparison. Mapping codes and descriptions are strings so leading zeros are not coerced. Lookup follows that field's case setting. Codes that differ only by case while `ignore_case` is true are a configuration error.

`comparison_rules` is keyed by the source A field. A field rule replaces the global setting for that field. Explicit conflicts are rejected, including a string field with its own numeric tolerance, a date field with a numeric tolerance, and `ignore_case=True` on a number or date field. A global `ignore_case` or `numeric_tolerance` does not make a date or string rule invalid; the field type wins.

Numeric comparison is exact when a field's type is `number` and no tolerance is set. Setting `numeric_tolerance` also compares values that are plain numbers, within that tolerance. Text such as `00123` is not treated as a number in that automatic mode. Set the field type to `number` when that coercion is intentional.

Date comparison uses the calendar date. Reader output is ISO `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`. Those forms are recognized by default. Add `date_formats` for other layouts, such as `%m/%d/%Y`. Ambiguous month/day formats are not guessed.

Duplicate keys are never silently dropped and never crossed into a many-to-many comparison. With `detect_duplicates=True` (the default), every in-scope duplicate row is reported and removed from field comparison. With `detect_duplicates=False`, in-scope duplicates raise `DuplicateKeyError` and no result is returned. Source B duplicates whose key is absent from source A are in scope only when `bidirectional` is true. Otherwise those rows are listed in `not_evaluated`.

`bidirectional=False` still compares keys that exist on both sides and still reports keys missing from source B. It does not report keys that exist only in source B.

## Reporting

Leave `generate_report` false to get the result without writing a file. `output_path` is not used in that case.

`generate_report=True` writes an `.xlsx` workbook with Summary, Detailed Comparison, Exceptions Only, and Execution Metadata. Headers are frozen and filtered. Pass a file path ending in `.xlsx`, or a directory. Parent directories are created. The default file name is `reconciliation_report.xlsx` in the current working directory.

## Logging

The library logs counts and outcome class names. It does not log cell values. The result object does contain the compared values, because that is what a test needs to inspect.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The tests build synthetic workbooks, CSV files, and DataFrames. They cover the comparison rules, JSON, the Excel report, the Robot library, the process CLI, and the Playwright client.

## Release lab

`integration_lab/` runs one ledger fixture through the installed `qa-utils` command, Robot Framework, Playwright, and the PowerShell process wrapper. The same counts, JSON shape, business failure, and exit codes are required from each consumer.

```bash
pip install -e ".[dev]"
pytest integration_lab
python integration_lab/verify_wheel.py
```

`verify_wheel.py` runs `python -m build`, installs that wheel into `.release-venv`, and reruns the lab with `QA_UTILS_REQUIRE_WHEEL=1`. The import must come from that environment's `site-packages`.

Tosca Commander is not part of the automated lab. The command it should run, and the result it should record, are in `docs/tosca-execution.md`. The publish gate is `docs/release-readiness.md`.

## Adapters

Create the synthetic workbooks used by the examples:

```bash
python examples/cam_mdg_example.py
```

That example is only a caller. The column names and status codes are arguments, not behavior inside the engine.

### Process CLI

```bash
qa-utils --config examples/config/cam_mdg.json
python -m universal_utils.cli --config examples/config/cam_mdg.json
python adapters/tosca/reconciliation_cli.py --source-type excel --source-a a.xlsx --source-b b.xlsx --key-a ID --key-b ID
```

`pip install -e ".[dev]"` installs the `qa-utils` command. `universal-qa-utils` is the same entry point. Both call `python -m universal_utils.cli`.

Stdout is one JSON result. Logs go to stderr.

| Exit code | Meaning in `strict` mode |
| --- | --- |
| 0 | The process finished and the reconciliation passed. |
| 2 | The process finished and the reconciliation found business exceptions. |
| 1 | Technical failure. The JSON describes the error instead of a reconciliation result. |

`--exit-code-mode defer` returns 0 for both passing and failing business results. The caller reads `passed` from the JSON, or from the optional `--result-file`, and makes its own assertion. Technical failures still return 1.

```text
status=completed
passed=false
exceptions=1
```

`adapters/tosca/run_reconciliation.ps1` calls Python with an argument array. It is not a Tosca module. PowerShell 7 (`pwsh`) is required. On Windows, point the approved Tosca process module at:

```powershell
pwsh -NoProfile -File adapters\tosca\run_reconciliation.ps1 -Python C:\path\to\python.exe -Config C:\path\to\reconciliation.json -ResultFile C:\path\to\metrics.txt -ExitCodeMode defer
```

Use `defer` when Tosca must read `metrics.txt` before judging the business result. `strict` returns 2 when the reconciliation has business exceptions. A missing file or invalid configuration returns 1 and JSON `status=technical_failure`. The exact host steps are in `docs/tosca-execution.md`.

Tosca Commander on Windows has not been executed. A passing PowerShell wrapper test is not Tosca validation.

### Robot Framework

Install the optional Robot extra, then import the library that ships inside the package:

```bash
pip install -e ".[robot]"
python -m robot.libdoc universal_utils.robot.ReconciliationLibrary list
python -m robot --variable PYTHON:python examples/robot_example.robot
```

The keywords are `Compare Excel Files`, `Compare CSV Files`, `Get Reconciliation Summary`, and `Verify Reconciliation Passed`. Mappings may be dictionaries, JSON strings, or a `config` path. The compare keywords return a dictionary and do not fail when records differ. `Verify Reconciliation Passed` performs that check. A passing reconciliation and a business failure are both successful Robot keywords until `Verify Reconciliation Passed` makes the assertion.

### Playwright

`adapters/playwright/reconciliation-client.ts` starts Python with `child_process.execFile`. A business mismatch resolves to the result object. A missing Python executable, a timeout, invalid JSON, or a technical failure rejects with `ReconciliationClientError`.

```typescript
const result = await compareExcel({
  sourceA: "examples/demo-output/CAM.xlsx",
  sourceB: "examples/demo-output/MDG.xlsx",
  sheetA: "CAM",
  sheetB: "MDG",
  keyA: "PCID",
  keyB: "ID",
  fieldMapping: { "PCID Name": "Name" },
  pythonPath: process.env.PYTHON,
});
```

`examples/playwright_example.spec.ts` shows the same call inside a Playwright test. The client itself does not import Playwright. The spec creates the synthetic workbooks first, then compares them. Point `PYTHON` at the interpreter where this package is installed:

```bash
npm install
PYTHON=.venv/bin/python npm run test:playwright
```

## Workbook comparison

`universal_utils.excel_compare` is an openpyxl-based workbook comparison. It compares cells by worksheet and address. It does not calculate formulas, compare charts or shapes, or decrypt workbooks. The command is `qa-excel-compare`. The Robot library is `universal_utils.excel_compare.robot.ExcelCompareLibrary`.

This is separate from `qa-utils` and from `Compare Excel Files`. The supported behavior, the result schema, and the limits are in [docs/excel-compare.md](docs/excel-compare.md).

## License

Universal QA Utils is licensed under the MIT License.

Copyright (c) 2026 Global iTech Solutions Inc.

See [LICENSE](LICENSE).

## Limits

- Reconciliation reads formula cells from Excel's cached values (`data_only=True`). A formula that Excel has not calculated comes through empty.
- Workbook comparison does not use those cached values. It compares formula text only when requested, and it does not calculate formulas.
- Merged cells are not expanded.
- Numeric Excel cells cannot preserve leading zeros.
- Comparison is in memory.
- A numeric CLI sheet argument is a zero-based index. A sheet whose name is numeric should be given as a string in the JSON config.
- Tosca integration stops at the process boundary. The installed Tosca environment has to supply the approved way to run the command. Windows Tosca Commander execution has not been validated.
- Playwright and the Tosca PowerShell script are repository adapters. They are not files inside the wheel. The Robot library is `universal_utils.robot` and is inside the wheel.
