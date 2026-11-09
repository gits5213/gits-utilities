"""Contracts preserved by the 0.1.1 maintenance release.

These tests lock behavior that the 0.1.0 suite covered only indirectly:
empty files, CSV encoding, value whitespace, tolerance boundaries, composite
key identity, sheet indexes, and CLI encoding.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from openpyxl import Workbook

from tests.conftest import write_csv, write_excel
from universal_utils import __version__
from universal_utils.data_reader import read_excel_table
from universal_utils.exceptions import DataReadError, ValidationError
from universal_utils.models import LIBRARY_VERSION, SCHEMA_VERSION
from universal_utils.reconciliation import compare_csv, compare_excel

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "universal_utils.cli"]


def test_package_version_fields_match() -> None:
    project = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == LIBRARY_VERSION == __version__
    assert SCHEMA_VERSION == "1"


def test_empty_files_fail_before_a_result_is_returned(tmp_path: Path) -> None:
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_bytes(b"")
    header_only = write_csv(tmp_path / "header.csv", [["ID", "Name"]])
    with pytest.raises(DataReadError, match="no header row"):
        compare_csv(str(empty_csv), str(header_only), key_a="ID", key_b="ID")

    empty_sheet = tmp_path / "empty.xlsx"
    workbook = Workbook()
    workbook.active.title = "Data"
    workbook.save(empty_sheet)
    workbook.close()
    with pytest.raises(DataReadError, match="no header row"):
        read_excel_table(empty_sheet, "Data")

    zero_byte = tmp_path / "zero.xlsx"
    zero_byte.write_bytes(b"")
    with pytest.raises(DataReadError, match="Unable to read Excel file"):
        read_excel_table(zero_byte, "Data")


def test_csv_latin1_round_trip_and_utf8_failure(tmp_path: Path) -> None:
    payload = "ID,Name\n1,Café\n".encode("latin-1")
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    source_a.write_bytes(payload)
    source_b.write_bytes(payload)
    with pytest.raises(DataReadError, match="encoding"):
        compare_csv(str(source_a), str(source_b), key_a="ID", key_b="ID")
    result = compare_csv(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        encoding="latin-1",
    )
    assert result.passed is True
    assert result.details["matched"][0]["fields"][0]["value_a"] == "Café"


def test_unknown_encoding_and_delimiter_are_rejected(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "a.csv", [["ID", "Name"], ["1", "Ada"]])
    with pytest.raises(ValidationError, match="Unknown encoding"):
        compare_csv(str(source), str(source), key_a="ID", key_b="ID", encoding="not-an-encoding")
    with pytest.raises(ValidationError, match="delimiter"):
        compare_csv(str(source), str(source), key_a="ID", key_b="ID", delimiter="::")


def test_value_whitespace_follows_the_trim_setting(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Name"], ["1", " Ada "]]})
    trimmed = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        trim_whitespace=True,
    )
    raw = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        trim_whitespace=False,
    )
    assert trimmed.passed is True
    assert raw.mismatched == 1
    assert raw.details["field_issues"][0]["reason"] == "mismatch"


def test_whitespace_only_key_is_invalid(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Name"], ["   ", "Ada"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    trimmed = compare_excel(str(source_a), str(source_b), key_a="ID", key_b="ID")
    assert trimmed.invalid_keys == 1
    assert trimmed.missing_in_b == 0
    raw = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        trim_whitespace=False,
    )
    assert raw.invalid_keys == 0
    assert raw.missing_in_a == 1
    assert raw.missing_in_b == 1


def test_numeric_tolerance_boundary_is_inclusive(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Amount"], ["1", "10.00"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Amount"], ["1", "10.05"]]})
    on_boundary = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.05,
    )
    outside = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.049,
    )
    assert on_boundary.passed is True
    assert outside.mismatched == 1


def test_unformatted_dates_are_not_guessed(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Start"], ["1", "01/02/2024"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Start"], ["1", "2024-01-02"]]})
    result = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        comparison_rules={"Start": {"type": "date"}},
    )
    assert result.passed is False
    assert result.details["field_issues"][0]["reason"] == "date_parse_failure"


def test_composite_key_display_separator_does_not_merge_keys(tmp_path: Path) -> None:
    source_a = write_excel(
        tmp_path / "a.xlsx",
        {"Data": [["Region", "Code", "Name"], ["A||B", "C", "Ada"]]},
    )
    source_b = write_excel(
        tmp_path / "b.xlsx",
        {"Data": [["Region", "Code", "Name"], ["A", "B||C", "Ada"]]},
    )
    result = compare_excel(
        str(source_a),
        str(source_b),
        key_a=["Region", "Code"],
        key_b=["Region", "Code"],
    )
    assert result.matched == 0
    assert result.missing_in_a == 1
    assert result.missing_in_b == 1
    assert result.details["missing_in_b"][0]["key"] == "A||B||C"


def test_sheet_index_outside_the_workbook_is_a_read_error(tmp_path: Path) -> None:
    source = write_excel(
        tmp_path / "book.xlsx",
        {"First": [["ID", "Name"], ["1", "Ada"]], "Second": [["ID", "Name"], ["1", "Ada"]]},
    )
    result = compare_excel(str(source), str(source), sheet_a=1, sheet_b=0, key_a="ID", key_b="ID")
    assert result.passed is True
    with pytest.raises(DataReadError, match="Sheet index 2"):
        compare_excel(str(source), str(source), sheet_a=2, key_a="ID", key_b="ID")


def test_cli_encoding_delimiter_and_empty_file(tmp_path: Path) -> None:
    payload = "ID;Name\n1;Café\n".encode("latin-1")
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    source_a.write_bytes(payload)
    source_b.write_bytes(payload)
    completed = subprocess.run(
        [
            *CLI,
            "--source-type",
            "csv",
            "--source-a",
            str(source_a),
            "--source-b",
            str(source_b),
            "--key-a",
            "ID",
            "--key-b",
            "ID",
            "--encoding",
            "latin-1",
            "--delimiter",
            ";",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["passed"] is True

    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    failed = subprocess.run(
        [
            *CLI,
            "--source-type",
            "csv",
            "--source-a",
            str(empty),
            "--source-b",
            str(source_b),
            "--key-a",
            "ID",
            "--key-b",
            "ID",
            "--encoding",
            "latin-1",
            "--delimiter",
            ";",
            "--exit-code-mode",
            "defer",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload_json = json.loads(failed.stdout)
    assert failed.returncode == 1
    assert payload_json["status"] == "technical_failure"
    assert payload_json["error_type"] == "DataReadError"
