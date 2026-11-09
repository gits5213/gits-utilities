"""One synthetic reconciliation shared by every installed-package consumer.

The workbooks are arguments to the engine. Account numbers stay text, including
the leading zeros. The expected counts below are the contract: a consumer
passes only when its process result matches this document.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook

BUSINESS_STATUS_FAIL = "fail"
STRICT_EXIT_CODE = 2
DEFER_EXIT_CODE = 0
TECHNICAL_EXIT_CODE = 1

RESULT_KEYS = (
    "details",
    "duplicates",
    "exceptions",
    "invalid_keys",
    "matched",
    "metadata",
    "mismatched",
    "missing_in_a",
    "missing_in_b",
    "passed",
    "report_path",
    "total_records",
    "unmapped",
)
DETAIL_KEYS = (
    "blocked",
    "compared",
    "duplicates",
    "field_issues",
    "invalid_keys",
    "matched",
    "mismatched",
    "missing_in_a",
    "missing_in_b",
    "not_evaluated",
    "unmapped",
)
TECHNICAL_KEYS = ("error_type", "message", "status")

SHEET_A = "Ledger"
SHEET_B = "Directory"
KEY_A = "Account"
KEY_B = "Account ID"
SOURCE_A_NAME = "ledger_a.xlsx"
SOURCE_B_NAME = "ledger_b.xlsx"
CONFIG_NAME = "reconciliation.json"
EXPECTED_NAME = "expected.json"
REPORT_NAME = "ledger_report.xlsx"

FIELD_MAPPING = {
    "Name": "Full Name",
    "Status": "Status Description",
    "Amount": "Balance",
}
VALUE_MAPPINGS = {
    "Status": {
        "S0011": "Active",
        "S0023": "Closed",
    }
}

_LEDGER_ROWS = [
    ["Account", "Name", "Status", "Amount"],
    ["001", "Ada Lovelace", "S0011", "10"],
    ["002", "Grace Hopper", "S0023", "20"],
    ["003", "Katherine Johnson", "S0099", "30"],
    ["004", "Only In Ledger", "S0011", "40"],
    ["005", "Duplicate", "S0011", "50"],
    ["005", "Duplicate Again", "S0011", "51"],
    ["", "Blank Key", "S0011", "1"],
    ["", "", "", ""],
]
_DIRECTORY_ROWS = [
    ["Account ID", "Full Name", "Status Description", "Balance"],
    ["001", "Ada Lovelace", "Active", "10.00"],
    ["002", "Grace Hopper", "Closed", "25.00"],
    ["003", "Katherine Johnson", "S0099", "30.00"],
    ["006", "Only In Directory", "Active", "1"],
    ["005", "Duplicate Counterpart", "Active", "50.00"],
    ["", "", "", ""],
]


@dataclass(frozen=True)
class MaterializedFixture:
    """Files written for one run of the shared reconciliation."""

    directory: Path
    source_a: Path
    source_b: Path
    config: Path
    expected: Path
    report: Path


def expected_document() -> dict[str, object]:
    """Return the business contract for the shared workbooks."""
    return {
        "fixture": "ledger",
        "business_status": BUSINESS_STATUS_FAIL,
        "strict_exit_code": STRICT_EXIT_CODE,
        "defer_exit_code": DEFER_EXIT_CODE,
        "technical_exit_code": TECHNICAL_EXIT_CODE,
        "metrics": {
            "passed": False,
            "total_records": 12,
            "matched": 1,
            "mismatched": 1,
            "missing_in_a": 1,
            "missing_in_b": 1,
            "duplicates": 2,
            "unmapped": 1,
            "invalid_keys": 1,
            "exceptions": 7,
        },
        "keys": {
            "matched": ["001"],
            "mismatched": ["002"],
            "missing_in_a": ["006"],
            "missing_in_b": ["004"],
            "duplicates": ["005", "005"],
            "unmapped": ["003"],
            "invalid_keys": [""],
            "blocked": ["005"],
        },
        "field_issues": [
            {"key": "002", "field_a": "Amount", "reason": "mismatch", "value_a": "20", "value_b": "25.00"},
            {"key": "003", "field_a": "Status", "reason": "unmapped", "value_a": "S0099", "value_b": "S0099"},
        ],
        "schema_version": "1",
        "library_version": "0.1.0",
        "result_keys": list(RESULT_KEYS),
        "detail_keys": list(DETAIL_KEYS),
    }


def config_document() -> dict[str, object]:
    """Return CLI options whose paths are relative to the fixture directory."""
    return {
        "source_type": "excel",
        "source_a": SOURCE_A_NAME,
        "source_b": SOURCE_B_NAME,
        "sheet_a": SHEET_A,
        "sheet_b": SHEET_B,
        "key_a": KEY_A,
        "key_b": KEY_B,
        "field_mapping": FIELD_MAPPING,
        "value_mappings": VALUE_MAPPINGS,
        "numeric_tolerance": 0.01,
        "generate_report": True,
        "output_path": REPORT_NAME,
    }


def materialize(directory: Path) -> MaterializedFixture:
    """Write the workbooks, CLI config, and expected contract into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    source_a = directory / SOURCE_A_NAME
    source_b = directory / SOURCE_B_NAME
    _write_workbook(source_a, SHEET_A, _LEDGER_ROWS)
    _write_workbook(source_b, SHEET_B, _DIRECTORY_ROWS)
    config = directory / CONFIG_NAME
    expected = directory / EXPECTED_NAME
    _write_json(config, config_document())
    _write_json(expected, expected_document())
    return MaterializedFixture(
        directory=directory,
        source_a=source_a,
        source_b=source_b,
        config=config,
        expected=expected,
        report=directory / REPORT_NAME,
    )


def _write_workbook(path: Path, sheet_name: str, rows: list[list[str]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def main(argv: list[str]) -> int:
    """Write the shared fixture into a directory given on the command line."""
    if len(argv) != 1:
        print("Usage: python -m integration_lab.reconciliation_fixture DIRECTORY", file=sys.stderr)
        return 1
    written = materialize(Path(argv[0]))
    print(written.config)
    print(written.expected)
    return 0


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
