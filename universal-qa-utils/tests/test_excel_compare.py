"""openpyxl workbook comparison. These tests do not describe a Tosca engine."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font

from tests.conftest import write_excel
from universal_utils.excel_compare import compare_workbooks
from universal_utils.excel_compare.robot import ExcelCompareLibrary
from universal_utils.exceptions import DataReadError, ValidationError
from universal_utils.reconciliation import compare_excel
from universal_utils.robot.ReconciliationLibrary import ReconciliationLibrary

CLI = [sys.executable, "-m", "universal_utils.excel_compare"]


def test_identical_workbooks_pass(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    target = _book(tmp_path / "target.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    result = compare_workbooks(reference, target)
    assert result["passed"] is True
    assert result["difference_count"] == 0
    assert result["engine"] == "openpyxl"
    assert result["targets"][0]["differences"] == []


def test_cell_value_difference_is_positional(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    target = _book(tmp_path / "target.xlsx", {"Data": [["ID", "Name"], ["1", "Grace"]]})
    result = compare_workbooks(reference, target)
    assert result["passed"] is False
    difference = result["targets"][0]["differences"][0]
    assert difference["category"] == "cell_value"
    assert difference["worksheet"] == "Data"
    assert difference["cell"] == "B2"
    assert difference["expected"] == "Ada"
    assert difference["actual"] == "Grace"
    assert difference["workbook"] == str(target)


def test_formula_text_is_compared_without_evaluation(tmp_path: Path) -> None:
    reference = _formula_book(tmp_path / "reference.xlsx", "=1+1")
    target = _formula_book(tmp_path / "target.xlsx", "=2")
    result = compare_workbooks(reference, target, include_formulas=True)
    categories = [item["category"] for item in result["targets"][0]["differences"]]
    assert categories == ["formula"]
    difference = result["targets"][0]["differences"][0]
    assert difference["expected"] == "=1+1"
    assert difference["actual"] == "=2"
    assert result["formula_evaluation"] == "not_performed"
    assert result["charts_compared"] is False
    assert result["shapes_compared"] is False
    assert "2" not in {difference["expected"], difference["actual"]}


def test_missing_extra_and_selected_worksheets(tmp_path: Path) -> None:
    reference = _book(
        tmp_path / "reference.xlsx",
        {"Keep": [["ID"], ["1"]], "Drop": [["ID"], ["9"]]},
    )
    missing = _book(tmp_path / "missing.xlsx", {"Keep": [["ID"], ["1"]]})
    extra = _book(
        tmp_path / "extra.xlsx",
        {"Keep": [["ID"], ["1"]], "Drop": [["ID"], ["9"]], "Extra": [["ID"], ["3"]]},
    )
    missing_result = compare_workbooks(reference, missing)
    extra_result = compare_workbooks(reference, extra)
    selected = compare_workbooks(reference, missing, include_sheets=["Keep"])
    assert _categories(missing_result) == ["worksheet"]
    assert missing_result["targets"][0]["differences"][0]["worksheet"] == "Drop"
    assert missing_result["targets"][0]["differences"][0]["actual"] == "missing"
    assert extra_result["targets"][0]["differences"][0]["worksheet"] == "Extra"
    assert extra_result["targets"][0]["differences"][0]["actual"] == "present"
    assert selected["passed"] is True


def test_formatting_difference_uses_a_style_fingerprint(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["Name"], ["Ada"]]})
    target = _book(tmp_path / "target.xlsx", {"Data": [["Name"], ["Ada"]]})
    from openpyxl import load_workbook

    workbook = load_workbook(target)
    workbook["Data"]["A2"].font = Font(bold=True)
    workbook.save(target)
    workbook.close()
    result = compare_workbooks(reference, target, include_formats=True)
    assert _categories(result) == ["formatting"]
    assert result["targets"][0]["differences"][0]["cell"] == "A2"
    assert result["targets"][0]["differences"][0]["actual"]["font_bold"] is True


def test_multiple_targets_and_difference_threshold(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["A", "B"], ["1", "2"]]})
    same = _book(tmp_path / "same.xlsx", {"Data": [["A", "B"], ["1", "2"]]})
    changed = _book(tmp_path / "changed.xlsx", {"Data": [["A", "B"], ["9", "8"]]})
    folder = tmp_path / "targets"
    folder.mkdir()
    (folder / "a-same.xlsx").write_bytes(same.read_bytes())
    (folder / "b-changed.xlsx").write_bytes(changed.read_bytes())
    result = compare_workbooks(reference, folder)
    assert [Path(item["target"]).name for item in result["targets"]] == [
        "a-same.xlsx",
        "b-changed.xlsx",
    ]
    assert result["passed"] is False
    assert result["targets"][0]["passed"] is True
    assert result["targets"][1]["difference_count"] == 2
    limited = compare_workbooks(reference, changed, abort_after_differences=1)
    assert limited["truncated"] is True
    assert limited["difference_count"] == 1
    assert limited["targets"][0]["differences"][0]["cell"] == "A2"


def test_empty_workbooks_and_empty_cells_match(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": []})
    target = _book(tmp_path / "target.xlsx", {"Data": []})
    assert compare_workbooks(reference, target)["passed"] is True
    blank = _book(tmp_path / "blank.xlsx", {"Data": [["Name"], [""]]})
    missing_value = _book(tmp_path / "missing-value.xlsx", {"Data": [["Name"]]})
    assert compare_workbooks(blank, missing_value)["passed"] is True


def test_invalid_corrupt_and_unsupported_files(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["ID"], ["1"]]})
    with pytest.raises(DataReadError, match="not found"):
        compare_workbooks(tmp_path / "missing.xlsx", reference)
    corrupt = tmp_path / "corrupt.xlsx"
    corrupt.write_bytes(b"this is not a workbook")
    with pytest.raises(DataReadError, match="Unable to read Excel file"):
        compare_workbooks(reference, corrupt)
    legacy = tmp_path / "legacy.xls"
    legacy.write_bytes(b"not-xlsx")
    with pytest.raises(DataReadError, match="Unsupported workbook type"):
        compare_workbooks(reference, legacy)
    with pytest.raises(ValidationError, match="Included sheet"):
        compare_workbooks(reference, reference, include_sheets=["Missing"])


def test_json_document_discloses_unsupported_features(tmp_path: Path) -> None:
    reference = _chart_book(tmp_path / "reference.xlsx")
    target = _chart_book(tmp_path / "target.xlsx")
    image_target = _chart_book(tmp_path / "image.xlsx")
    _embed_media(reference, b"reference-image")
    _embed_media(target, b"reference-image")
    _embed_media(image_target, b"different-image")
    result = compare_workbooks(reference, [target, image_target], include_objects=True)
    text = json.dumps(result, sort_keys=True)
    parsed = json.loads(text)
    assert parsed == result
    assert result["excel_compare_schema_version"] == "1"
    assert result["charts_compared"] is False
    assert result["shapes_compared"] is False
    assert result["password_decryption"] == "not_supported"
    assert result["formula_evaluation"] == "not_performed"
    assert any(
        item["feature"] == "charts" and item["status"] == "not_compared" and item.get("count") == 1
        for item in result["unsupported"]
    )
    assert any(item["feature"] == "shapes" and item["status"] == "not_compared" for item in result["unsupported"])
    assert "password" not in inspect.signature(compare_workbooks).parameters
    image_differences = [
        item
        for item in result["targets"][1]["differences"]
        if item["category"] == "object"
    ]
    assert image_differences
    assert result["targets"][0]["passed"] is True


def test_cli_exit_codes_and_qa_utils_help(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["Name"], ["Ada"]]})
    target = _book(tmp_path / "target.xlsx", {"Data": [["Name"], ["Grace"]]})
    strict = _run(
        [
            "--reference",
            str(reference),
            "--target",
            str(target),
            "--report-format",
            "text",
            "--output",
            str(tmp_path / "report.txt"),
        ]
    )
    deferred = _run(
        [
            "--reference",
            str(reference),
            "--target",
            str(target),
            "--exit-code-mode",
            "defer",
        ]
    )
    failed = _run(["--reference", str(tmp_path / "missing.xlsx"), "--target", str(target)])
    report = (tmp_path / "report.txt").read_text(encoding="utf-8")
    assert strict.returncode == 2
    assert "category=cell_value" in strict.stdout
    assert "charts_compared=false" in report
    assert "formula_evaluation=not_performed" in report
    assert deferred.returncode == 0
    assert json.loads(deferred.stdout)["passed"] is False
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["error_type"] == "DataReadError"
    qa_utils = subprocess.run(
        [sys.executable, "-m", "universal_utils.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    excel = _run(["--help"])
    assert qa_utils.returncode == 0
    assert "qa-excel-compare" not in qa_utils.stdout
    assert "--source-a" in qa_utils.stdout
    assert "--exit-code-mode" in qa_utils.stdout
    assert excel.returncode == 0
    assert "qa-excel-compare" in excel.stdout
    assert "openpyxl" in excel.stdout


def test_robot_keywords_keep_reconciliation_keywords(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["Name"], ["Ada"]]})
    same = _book(tmp_path / "same.xlsx", {"Data": [["Name"], ["Ada"]]})
    changed = _book(tmp_path / "changed.xlsx", {"Data": [["Name"], ["Grace"]]})
    library = ExcelCompareLibrary()
    passed = library.compare_excel_workbooks(str(reference), str(same))
    assert passed["passed"] is True
    assert passed["charts_compared"] is False
    library.verify_excel_compare_passed()
    failed = library.compare_excel_workbooks(
        str(reference),
        str(changed),
        include_formulas="false",
    )
    assert failed["passed"] is False
    summary = library.get_excel_compare_summary()
    assert summary["difference_count"] == 1
    assert summary["shapes_compared"] is False
    with pytest.raises(AssertionError, match="difference_count=1"):
        library.verify_excel_compare_passed()
    reconciliation = ReconciliationLibrary()
    left, right = write_excel(tmp_path / "left.xlsx", {"Data": [["ID"], ["1"]]}), write_excel(
        tmp_path / "right.xlsx",
        {"Data": [["ID"], ["1"]]},
    )
    assert reconciliation.compare_excel_files(str(left), str(right), key_a="ID", key_b="ID")["passed"] is True
    assert {
        "compare_excel_files",
        "compare_csv_files",
        "get_reconciliation_summary",
        "verify_reconciliation_passed",
    } <= set(dir(reconciliation))
    assert compare_excel(str(left), str(right), key_a="ID", key_b="ID").passed is True


def test_robot_forwards_limit_and_tolerance(tmp_path: Path) -> None:
    reference = _book(tmp_path / "reference.xlsx", {"Data": [["A", "B", "C"], [1, 1, 1]]})
    changed = _book(tmp_path / "changed.xlsx", {"Data": [["A", "B", "C"], [1.4, 9, 8]]})
    library = ExcelCompareLibrary()

    limited = library.compare_excel_workbooks(
        str(reference),
        str(changed),
        abort_after_differences=1,
    )
    assert limited["truncated"] is True
    assert limited["difference_count"] == 1
    assert limited["targets"][0]["differences"][0]["cell"] == "A2"

    tolerated = library.compare_excel_workbooks(
        str(reference),
        str(changed),
        numeric_tolerance="0.5",
    )
    assert [item["cell"] for item in tolerated["targets"][0]["differences"]] == ["B2", "C2"]
    assert tolerated["truncated"] is False

    both = library.compare_excel_workbooks(
        str(reference),
        str(changed),
        abort_after_differences="1",
        numeric_tolerance=0.5,
        include_sheets="Data",
    )
    assert both["truncated"] is True
    assert both["difference_count"] == 1
    assert both["targets"][0]["differences"][0]["cell"] == "B2"
    assert library.get_excel_compare_summary()["difference_count"] == 1

    fresh = ExcelCompareLibrary()
    with pytest.raises(ValidationError, match="Unknown workbook comparison option 'not_a_real_option'"):
        fresh.compare_excel_workbooks(str(reference), str(changed), not_a_real_option=True)
    with pytest.raises(AssertionError, match="No workbook comparison result"):
        fresh.get_excel_compare_summary()

    with pytest.raises(ValidationError, match="numeric_tolerance"):
        library.compare_excel_workbooks(str(reference), str(changed), numeric_tolerance="nope")
    with pytest.raises(ValidationError, match="numeric_tolerance"):
        library.compare_excel_workbooks(str(reference), str(changed), numeric_tolerance=-1)
    with pytest.raises(ValidationError, match="abort_after_differences"):
        library.compare_excel_workbooks(str(reference), str(changed), abort_after_differences=0)
    with pytest.raises(ValidationError, match="abort_after_differences"):
        library.compare_excel_workbooks(str(reference), str(changed), abort_after_differences="none")
    assert library.get_excel_compare_summary()["difference_count"] == 1


def _book(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    if not sheets:
        workbook = Workbook()
        workbook.active.title = "Data"
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        workbook.close()
        return path
    return write_excel(path, sheets)


def _formula_book(path: Path, formula: str) -> Path:
    workbook = Workbook()
    workbook.active.title = "Data"
    workbook.active["A1"] = formula
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()
    return path


def _chart_book(path: Path) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Data"
    worksheet["A1"] = "Amount"
    worksheet["A2"] = 1
    chart = BarChart()
    chart.add_data(Reference(worksheet, min_col=1, min_row=1, max_row=2), titles_from_data=True)
    worksheet.add_chart(chart, "C2")
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()
    return path


def _embed_media(path: Path, payload: bytes) -> None:
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("xl/media/image1.bin", payload)


def _categories(result: dict) -> list[str]:
    return [item["category"] for item in result["targets"][0]["differences"]]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(CLI + args, check=False, capture_output=True, text=True)
