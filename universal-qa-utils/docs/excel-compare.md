# openpyxl-based workbook comparison

This comparison reads `.xlsx` and `.xlsm` files with openpyxl and compares them by worksheet name and cell address. It is not a Tricentis Tosca Excel Engine, and it does not use Excel to calculate, render, or decrypt workbooks.

The key-based reconciliation API remains `compare_excel`, `compare_csv`, and `qa-utils`. Workbook comparison is a separate module and a separate command.

## Supported capabilities

- One reference workbook and one or more target workbooks.
- A target path may be a folder. The folder contributes its `.xlsx` and `.xlsm` files, non-recursively, in file-name order.
- Literal cell values, including numbers, text, booleans, and dates stored in the workbook.
- Formula text when `include_formulas` is true. The text is compared. The formula is not calculated.
- Worksheet presence, worksheet order, and sheet visibility.
- A sheet list. Only those reference sheets are compared. A selected sheet that is missing from the reference is a technical error. A selected sheet that is missing from the target is a difference. Sheets outside the list are not value differences.
- Formatting fingerprints when `include_formats` is true: number format, font name, size, bold, italic, color token, fill, alignment, and border style.
- Embedded media file names and SHA-256 byte hashes when `include_objects` is true. Reading those bytes does not require Pillow.
- A difference limit. After that many differences are recorded for a target, later differences are omitted and `truncated` is true.
- JSON and text reports.

Empty stored cells and missing cells match. The default comparison does not trim or ignore case. Those options are explicit.

## Unsupported capabilities

The result always carries these disclosures:

| Field | Value | Meaning |
| --- | --- | --- |
| `engine` | `openpyxl` | The reader is openpyxl |
| `formula_evaluation` | `not_performed` | Formulas are not calculated |
| `charts_compared` | `false` | Charts are not compared |
| `shapes_compared` | `false` | Shapes are not compared |
| `password_decryption` | `not_supported` | Encrypted workbooks are rejected |

Charts found in a workbook are listed under `unsupported` with status `not_compared`. Their presence does not by itself fail the comparison, and it is not evidence that the chart was validated. Shapes, SmartArt, form controls, and Excel object models are outside this comparison. `.xls` files are rejected. Password decryption is not implemented, and the API has no password argument.

A formula cell does not contribute a calculated value. Two formulas that Excel would display as the same number remain different when their formula text differs and formula comparison is enabled. With formula comparison disabled, formula text is not a cell-value difference.

## Python API

```python
from universal_utils.excel_compare import compare_workbooks

result = compare_workbooks(
    "reference.xlsx",
    ["target-a.xlsx", "incoming"],
    include_formulas=True,
    include_formats=False,
    include_sheets=["Summary", "Detail"],
    abort_after_differences=10,
)
```

`result["passed"]` is true only when every target has no recorded differences. Each difference has `category`, `workbook`, `worksheet`, `cell`, `expected`, and `actual`.

## CLI

`qa-excel-compare` is separate from `qa-utils`.

```bash
qa-excel-compare \
  --reference reference.xlsx \
  --target target-a.xlsx \
  --target incoming \
  --include-sheets Summary \
  --include-formulas \
  --abort-after 10 \
  --report-format text \
  --output comparison.txt
```

| Exit code | Strict mode |
| --- | --- |
| 0 | Every target passed |
| 2 | The comparison finished with differences |
| 1 | Technical failure, such as a missing or unreadable file |

`--exit-code-mode defer` returns 0 for a completed comparison that found differences. Technical failures still return 1. Stdout is JSON unless `--report-format text` is set. The text report repeats the unsupported-capability lines.

## Robot Framework

```robot
*** Settings ***
Library    universal_utils.excel_compare.robot.ExcelCompareLibrary

*** Test Cases ***
Workbooks Match
    ${result}=    Compare Excel Workbooks    ${REFERENCE}    ${TARGET}
    Verify Excel Compare Passed    ${result}
```

`Compare Excel Workbooks` returns the result and does not fail when the workbooks differ. `Verify Excel Compare Passed` performs that check. `Get Excel Compare Summary` returns the counts and the unsupported-capability flags. These keywords do not replace `Compare Excel Files` or `Verify Reconciliation Passed`.

## Difference schema

`excel_compare_schema_version` is `"1"`.

```json
{
  "category": "cell_value",
  "workbook": "/work/target.xlsx",
  "worksheet": "Data",
  "cell": "B2",
  "expected": "Ada",
  "actual": "Grace"
}
```

Categories are `worksheet`, `worksheet_order`, `cell_value`, `formula`, `formatting`, and `object`. `worksheet` and `cell` are null when they do not apply. JSON objects use sorted keys.

## Limitations

- openpyxl reads the stored file. It does not ask Excel for a calculated cache, a rendered chart, or a decrypted package.
- Theme colors are recorded as theme tokens, not as the color Excel displays.
- Merged cells are not expanded.
- Image comparison uses the embedded media parts and their SHA-256 hashes. It does not compare anchors or rendered pictures.
- Reports contain the compared cell values. Logs contain counts only.
- The comparison runs in memory.

## Security

There is no password parameter. Do not put a password in a path, a sheet name, or a cell that will be written to a report. An encrypted workbook fails with `DataReadError`, and the message says that decryption is not implemented. Reports and logs do not receive a password because the command never accepts one.

## Relationship to reconciliation

`compare_excel` pairs data rows by keys, mappings, and comparison rules. `compare_workbooks` pairs cells by address. A passing reconciliation does not imply a passing workbook comparison, and the reverse is also true. `qa-utils` is unchanged.
