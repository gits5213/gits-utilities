"""Run compare_excel on synthetic workbooks.

Install the package first, from the universal-qa-utils directory:

    pip install -e .

Then run:

    python examples/python_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

from universal_utils.reconciliation import compare_excel

OUTPUT_DIR = Path(__file__).resolve().parent / "demo-output"


def _write(path: Path, sheet_name: str, rows: list[list[object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    for row in rows:
        worksheet.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()


def main() -> int:
    source_a = OUTPUT_DIR / "accounts.xlsx"
    source_b = OUTPUT_DIR / "directory.xlsx"
    _write(
        source_a,
        "Accounts",
        [
            ["Customer ID", "Customer Name", "Status Code", "Amount"],
            ["001", "Ada Lovelace", "S0011", 10],
            ["002", "Grace Hopper", "S0023", 20],
        ],
    )
    _write(
        source_b,
        "Directory",
        [
            ["Cust ID", "Name", "Status", "Amount"],
            ["001", "Ada Lovelace", "Active", "10.00"],
            ["002", "Grace Hopper", "Closed", "19.995"],
        ],
    )

    result = compare_excel(
        source_a=str(source_a),
        source_b=str(source_b),
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
            "Status Code": {
                "S0011": "Active",
                "S0023": "Closed",
            }
        },
        numeric_tolerance=0.01,
        generate_report=False,
    )
    print(result.passed)
    print(result.exceptions)
    print(result.to_json())
    matched_keys = {item["key"] for item in result.details["matched"]}
    if result.passed is not True or result.exceptions != 0 or matched_keys != {"001", "002"}:
        print("Synthetic comparison did not match the expected result.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
