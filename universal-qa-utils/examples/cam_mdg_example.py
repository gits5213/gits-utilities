"""Show the generic comparison call with one synthetic accounts pairing.

The names in this file are arguments to compare_excel. They are not part of
the comparison engine. Use --write-only to create the workbooks without
comparing them.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

from universal_utils.reconciliation import compare_excel

OUTPUT_DIR = Path(__file__).resolve().parent / "demo-output"


def write_sources(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    source_a = directory / "CAM.xlsx"
    source_b = directory / "MDG.xlsx"
    _write(
        source_a,
        "CAM",
        [
            ["PCID", "PCID Name", "PCID Description", "Status Code"],
            ["001", "Ada Lovelace", "First program", "S0011"],
            ["002", "Grace Hopper", "Second program", "S0023"],
        ],
    )
    _write(
        source_b,
        "MDG",
        [
            ["ID", "Name", "Program Description", "Status Description"],
            ["001", "Ada Lovelace", "First program", "Abandoned"],
            ["002", "Grace Hopper", "Second program", "Approved"],
        ],
    )
    return source_a, source_b


def main(argv: list[str]) -> int:
    source_a, source_b = write_sources(OUTPUT_DIR)
    if "--write-only" in argv:
        print(source_a)
        print(source_b)
        return 0
    result = compare_excel(
        source_a=str(source_a),
        source_b=str(source_b),
        sheet_a="CAM",
        sheet_b="MDG",
        key_a="PCID",
        key_b="ID",
        field_mapping={
            "PCID Name": "Name",
            "PCID Description": "Program Description",
            "Status Code": "Status Description",
        },
        value_mappings={
            "Status Code": {
                "S0011": "Abandoned",
                "S0023": "Approved",
            }
        },
        generate_report=True,
        output_path=str(OUTPUT_DIR / "cam_mdg.xlsx"),
    )
    print(result.passed)
    print(result.exceptions)
    print(result.to_json())
    matched = {item["key"] for item in result.details["matched"]}
    if result.passed is not True or result.exceptions != 0 or matched != {"001", "002"}:
        print("Synthetic comparison did not match the expected result.", file=sys.stderr)
        return 1
    return 0


def _write(path: Path, sheet_name: str, rows: list[list[object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
