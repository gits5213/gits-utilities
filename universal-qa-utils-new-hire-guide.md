# New-hire guide: universal-qa-utils

Use this guide on your first day when you need to install and run [universal-qa-utils](https://pypi.org/project/universal-qa-utils/) from your own terminal. You do not need to copy the library source into your project. Install the published package and call its commands.

The production release is `0.2.0`. It requires Python 3.11 or newer.

The package does two different jobs:

| Job | Command | What it compares |
| --- | --- | --- |
| Reconciliation | `qa-utils` | Rows matched by a key, even when the column names differ |
| Workbook comparison | `qa-excel-compare` | Cells matched by worksheet name and cell address |

A passing reconciliation does not mean the workbooks are identical cell by cell. A passing workbook comparison does not mean the business keys match.

## 1. Check Python

```bash
python3 --version
```

You need `3.11` or newer. If that command prints `3.9` or `3.10`, install Python 3.11 and use it explicitly in every command below. On this kind of machine the command is often:

```bash
python3.11 --version
```

Check which Python `pip` belongs to before you install:

```bash
python3.11 -m pip --version
```

The output must say `(python 3.11)`. A bare `pip` command sometimes belongs to an older Python. That older pip cannot install this package and reports that version `0.2.0` requires Python `>=3.11`.

## 2. Create a project virtual environment

Work inside a virtual environment so the install does not change your system Python.

```bash
mkdir -p ~/qa-work
cd ~/qa-work
python3.11 -m venv .venv
```

Activate it:

```bash
# macOS or Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Your prompt should now show `(.venv)`. After activation, `python` and `pip` are the environment you just created.

## 3. Install the package

Install the production release from PyPI:

```bash
python -m pip install "universal-qa-utils==0.2.0"
```

Install Robot Framework only when you will run Robot tests:

```bash
python -m pip install "universal-qa-utils[robot]==0.2.0"
```

Confirm the install:

```bash
python -m pip check
python -c "import universal_utils; print(universal_utils.__version__)"
qa-utils --help
qa-excel-compare --help
```

`pip check` should report no broken requirements. The version command should print `0.2.0`. Both help commands should run.

If `qa-utils` is not found, the environment is not active or its `bin` directory is not on your `PATH`. Run the command through Python instead:

```bash
python -m universal_utils.cli --help
python -m universal_utils.excel_compare --help
```

## 4. Choose the right comparison

Use `qa-utils` when the files are two lists of records. The sheets and column names may differ. You name the key columns and the columns that should be compared. Example: a customer ID in one file is called `Cust ID` in the other file.

Use `qa-excel-compare` when you want to know whether the same cell address changed. Cell `B2` in the reference is compared with cell `B2` in the target. Both workbooks must use the same worksheet name for that comparison. The tool does not pair `Data` with `report` just because both sheets hold similar columns.

## 5. Reconcile two Excel files

This command compares rows by key. Replace the file names, sheet names, and column names with the names in your files.

```bash
qa-utils \
  --source-type excel \
  --source-a reference.xlsx \
  --source-b target.xlsx \
  --sheet-a Accounts \
  --sheet-b Directory \
  --key-a "Customer ID" \
  --key-b "Cust ID" \
  --field-mapping '{"Customer Name":"Name","Status Code":"Status","Amount":"Amount"}' \
  --value-mappings '{"Status Code":{"S0011":"Active","S0023":"Closed"}}' \
  --numeric-tolerance 0.01 \
  --generate-report \
  --output-path reconciliation-report.xlsx
```

Stdout is one JSON result. Logs go to stderr.

| Exit code | Meaning |
| --- | --- |
| 0 | The command finished and the reconciliation passed. |
| 2 | The command finished and found business differences. |
| 1 | The command could not read or accept the input. |

A missing key or a different amount is a business result, not a crash. Read `passed` and `exceptions` in the JSON. The Excel report has Summary, Detailed Comparison, Exceptions Only, and Execution Metadata sheets.

Add `--exit-code-mode defer` when another tool must read the JSON even though the business result failed. Technical failures still return exit code `1`.

The same engine can compare CSV files:

```bash
qa-utils \
  --source-type csv \
  --source-a left.csv \
  --source-b right.csv \
  --key-a ID \
  --key-b ID
```

## 6. Compare two workbooks by cell address

Put the expected workbook first. That file is the reference. Put the file you want to check second. That file is the target.

```bash
qa-excel-compare \
  --reference reference.xlsx \
  --target target.xlsx \
  --ignore-case \
  --trim-whitespace \
  --report-format text \
  --output workbook-comparison.txt
```

Open `workbook-comparison.txt` after the command finishes. The report contains the compared cell values.

| Exit code | Meaning |
| --- | --- |
| 0 | The enabled checks found no differences. |
| 2 | The comparison finished and found differences. |
| 1 | A file is missing, unreadable, or encrypted. |

Before you trust a result, check the worksheet names:

```bash
python - <<'PY'
from openpyxl import load_workbook
for path in ("reference.xlsx", "target.xlsx"):
    book = load_workbook(path, read_only=True)
    print(path, book.sheetnames)
    book.close()
PY
```

If one workbook has a sheet named `Data` and the other has a sheet named `report`, rename one sheet so the names match, then run the command again. Until the names match, the result is a worksheet difference, not a cell-by-cell comparison.

Useful options:

```bash
qa-excel-compare \
  --reference reference.xlsx \
  --target target.xlsx \
  --include-sheets Data \
  --include-formulas \
  --include-formats \
  --numeric-tolerance 0.01 \
  --abort-after 50 \
  --report-format text \
  --output workbook-comparison.txt
```

- `--include-formulas` compares the stored formula text, such as `=1+1` and `=2`. It does not ask Excel to calculate either formula.
- `--include-formats` compares number format, font, fill, alignment, and borders.
- `--include-objects` compares embedded media by file name and SHA-256 hash. A matching hash does not mean the picture looks the same or sits in the same place.
- `--numeric-tolerance 0.01` allows a numeric difference up to that amount.
- `--abort-after 50` records at most 50 differences for a target.

You can pass `--target` more than once when one reference must be checked against several workbooks.

## 7. Use the Python API

Reconciliation:

```python
from universal_utils.reconciliation import compare_excel

result = compare_excel(
    source_a="reference.xlsx",
    source_b="target.xlsx",
    sheet_a="Accounts",
    sheet_b="Directory",
    key_a="Customer ID",
    key_b="Cust ID",
    field_mapping={"Customer Name": "Name", "Amount": "Amount"},
    numeric_tolerance=0.01,
    generate_report=False,
)
print(result.passed, result.exceptions)
```

Workbook comparison:

```python
from universal_utils.excel_compare import compare_workbooks

result = compare_workbooks(
    "reference.xlsx",
    ["target.xlsx"],
    include_formulas=False,
    ignore_case=True,
    trim_whitespace=True,
)
print(result["passed"], result["difference_count"])
print(result["formula_evaluation"], result["charts_compared"], result["shapes_compared"])
```

`result["passed"]` is true only for the checks you enabled. These fields stay the same on every result:

| Field | Value | Meaning |
| --- | --- | --- |
| `formula_evaluation` | `not_performed` | Formulas were not calculated. |
| `charts_compared` | `false` | Charts were not compared. |
| `shapes_compared` | `false` | Shapes were not compared. |
| `password_decryption` | `not_supported` | An encrypted workbook is rejected. |

## 8. Run the Robot Framework keywords

Install the Robot extra from step 3, then list the keywords that ship inside the package:

```bash
python -m robot.libdoc universal_utils.robot.ReconciliationLibrary list
python -m robot.libdoc universal_utils.excel_compare.robot.ExcelCompareLibrary list
```

Reconciliation keywords:

- `Compare Excel Files`
- `Compare CSV Files`
- `Get Reconciliation Summary`
- `Verify Reconciliation Passed`

Workbook keywords:

- `Compare Excel Workbooks`
- `Get Excel Compare Summary`
- `Verify Excel Compare Passed`

The compare keywords return a result and do not fail the test when the files differ. The `Verify` keywords perform that check.

Save this as `workbook_check.robot` and change the two paths:

```robot
*** Settings ***
Library    universal_utils.excel_compare.robot.ExcelCompareLibrary

*** Test Cases ***
Workbooks Match For Enabled Checks
    ${result}=    Compare Excel Workbooks    ${CURDIR}/reference.xlsx    ${CURDIR}/target.xlsx
    Verify Excel Compare Passed    ${result}
```

Run it with the same interpreter that has the package installed:

```bash
python -m robot workbook_check.robot
```

## 9. Clone the repository when you need the examples

The PyPI package does not include the example files. Clone the repository when you want the synthetic examples or the adapter scripts:

```bash
git clone https://github.com/gits5213/gits-utilities.git
cd gits-utilities/universal-qa-utils
```

Run an example with the environment from step 2, not with a second copy of the source:

```bash
python examples/python_example.py
python examples/cam_mdg_example.py
python -m robot --variable PYTHON:python examples/robot_example.robot
```

The Playwright client and the PowerShell script live in this repository. They are not inside the installed wheel. Windows Tosca Commander has not been validated. A passing local command is not Tosca validation.

## 10. Know the limits before you report a result

- Reconciliation reads cached formula values. A formula Excel has never calculated can arrive empty.
- Workbook comparison does not calculate formulas. It compares formula text only when you ask for it.
- Charts, shapes, comments, sheet protection, pivot tables, defined names, and VBA are not compared.
- Media comparison uses a byte hash. It does not check appearance, size, or position.
- Encrypted workbooks fail. The command has no password argument. Do not put a password in a file name, sheet name, or cell.
- Merged cells are not expanded.
- A number stored as an Excel number has already lost any leading zeros.
- Comparison runs in memory.
- `passed` means the enabled checks found nothing to report. It does not mean the entire workbook is equivalent.
- Reports contain the compared values. Do not commit reports or source workbooks that hold private data.

## 11. Where to look next

- Package page: https://pypi.org/project/universal-qa-utils/0.2.0/
- Source and issues: https://github.com/gits5213/gits-utilities
- Workbook comparison details: `universal-qa-utils/docs/excel-compare.md`
- License: MIT, Copyright (c) 2026 Global iTech Solutions Inc.
