"""Optional Excel report formatting and content."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from universal_utils.reconciliation import compare_excel
from tests.conftest import write_excel


def _compare(tmp_path: Path, output: Path | None, *, generate_report: bool):
    source_a = write_excel(
        tmp_path / "a.xlsx",
        {"Data": [["ID", "Name"], ["1", "Ada"], ["2", "Grace"]]},
    )
    source_b = write_excel(
        tmp_path / "b.xlsx",
        {"Data": [["ID", "Name"], ["1", "Ada"], ["3", "Alan"]]},
    )
    return compare_excel(
        str(source_a),
        str(source_b),
        sheet_a="Data",
        sheet_b="Data",
        key_a="ID",
        key_b="ID",
        generate_report=generate_report,
        output_path=None if output is None else str(output),
    )


def test_report_has_required_sheets_formatting_and_rows(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "reconciliation.xlsx"
    result = _compare(tmp_path, output, generate_report=True)
    assert result.passed is False
    assert output.is_file()
    workbook = load_workbook(output)
    assert workbook.sheetnames == [
        "Summary",
        "Detailed Comparison",
        "Exceptions Only",
        "Execution Metadata",
    ]
    for name in workbook.sheetnames:
        worksheet = workbook[name]
        assert worksheet.freeze_panes == "A2"
        assert worksheet.auto_filter.ref is not None
        assert worksheet["A1"].font.bold is True
        assert worksheet["A1"].font.color.rgb == "00FFFFFF"
    summary = workbook["Summary"]
    metrics = {summary.cell(row, 1).value: summary.cell(row, 2).value for row in range(2, 12)}
    assert metrics["passed"] is False
    assert metrics["matched"] == 1
    assert metrics["missing_in_a"] == 1
    assert metrics["missing_in_b"] == 1
    exceptions = workbook["Exceptions Only"]
    exception_keys = {exceptions.cell(row, 3).value for row in range(2, exceptions.max_row + 1)}
    assert exception_keys == {"2", "3"}
    metadata = {
        workbook["Execution Metadata"].cell(row, 1).value: workbook["Execution Metadata"].cell(row, 2).value
        for row in range(2, workbook["Execution Metadata"].max_row + 1)
    }
    assert metadata["schema_version"] == "1"
    assert metadata["generated_at_utc"]
    assert "SUPER-SECRET-VALUE" not in str(metadata)
    workbook.close()


def test_report_can_be_written_for_a_passing_result(tmp_path: Path) -> None:
    output = tmp_path / "pass.xlsx"
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    result = compare_excel(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        generate_report=True,
        output_path=str(output),
    )
    assert result.passed is True
    workbook = load_workbook(output)
    assert workbook["Summary"]["B2"].value is True
    assert workbook["Exceptions Only"].max_row == 1
    workbook.close()
