"""Optional Excel report. The comparison result is complete without this module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from universal_utils.exceptions import ReportGenerationError, ValidationError
from universal_utils.models import METRIC_DEFINITIONS, METRIC_ORDER, ReconciliationResult

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
_PASS_FILL = PatternFill("solid", fgColor="C6EFCE")
_PASS_FONT = Font(bold=True, color="006100", name="Calibri", size=11)
_FAIL_FILL = PatternFill("solid", fgColor="FFC7CE")
_FAIL_FONT = Font(bold=True, color="9C0006", name="Calibri", size=11)
_BODY_FONT = Font(name="Calibri", size=11)
_THIN = Border(
    left=Side(style="thin", color="D9E2F3"),
    right=Side(style="thin", color="D9E2F3"),
    top=Side(style="thin", color="D9E2F3"),
    bottom=Side(style="thin", color="D9E2F3"),
)
_DETAIL_HEADERS = (
    "Key",
    "Status",
    "Source A Row",
    "Source B Row",
    "Field A",
    "Field B",
    "Value A",
    "Value B",
    "Field Status",
    "Reason",
)
_EXCEPTION_HEADERS = (
    "Category",
    "Source",
    "Key",
    "Row Number",
    "Field",
    "Value A",
    "Value B",
    "Reason",
)


def generate_reconciliation_report(
    result: ReconciliationResult,
    output_path: str | Path | None = None,
) -> str:
    """Write the Excel report and return its absolute path.

    This also sets ``result.report_path``. Metrics on the result are not changed.
    """
    if not isinstance(result, ReconciliationResult):
        raise ValidationError("generate_reconciliation_report requires a ReconciliationResult.")
    path = _resolve_output_path(output_path)
    previous_path = result.report_path
    object.__setattr__(result, "report_path", str(path))
    try:
        _write_workbook(result, path)
    except ReportGenerationError:
        object.__setattr__(result, "report_path", previous_path)
        raise
    except OSError as exc:
        object.__setattr__(result, "report_path", previous_path)
        raise ReportGenerationError(f"Unable to write reconciliation report to {path}.") from exc
    return str(path)


def _resolve_output_path(output_path: str | Path | None) -> Path:
    if output_path is None or (isinstance(output_path, str) and output_path.strip() == ""):
        path = Path("reconciliation_report.xlsx")
    elif isinstance(output_path, (str, Path)):
        path = Path(output_path)
    else:
        raise ValidationError("output_path must be a file path or None.")
    if str(path).strip() == "":
        path = Path("reconciliation_report.xlsx")
    if path.exists() and path.is_dir():
        path = path / "reconciliation_report.xlsx"
    elif path.suffix == "":
        path = path.with_suffix(".xlsx")
    elif path.suffix.lower() != ".xlsx":
        raise ReportGenerationError("Report output_path must be an .xlsx file or a directory.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReportGenerationError(f"Unable to create report directory {path.parent}.") from exc
    return path.resolve()


def _write_workbook(result: ReconciliationResult, path: Path) -> None:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    _write_summary(summary, result)
    _write_rows(
        workbook.create_sheet("Detailed Comparison"),
        _DETAIL_HEADERS,
        _detailed_rows(result),
    )
    _write_rows(
        workbook.create_sheet("Exceptions Only"),
        _EXCEPTION_HEADERS,
        _exception_rows(result),
    )
    _write_metadata(workbook.create_sheet("Execution Metadata"), result)
    workbook.properties.title = "Reconciliation report"
    workbook.properties.creator = "universal-qa-utils"
    workbook.save(path)


def _write_summary(worksheet: Worksheet, result: ReconciliationResult) -> None:
    _write_header(worksheet, ("Metric", "Value", "Definition"))
    for row_index, metric in enumerate(METRIC_ORDER, start=2):
        value = getattr(result, metric)
        worksheet.cell(row_index, 1, metric)
        cell = worksheet.cell(row_index, 2, value)
        worksheet.cell(row_index, 3, METRIC_DEFINITIONS[metric])
    _format_sheet(worksheet)
    passed_cell = worksheet.cell(2, 2)
    passed = bool(passed_cell.value)
    passed_cell.fill = _PASS_FILL if passed else _FAIL_FILL
    passed_cell.font = _PASS_FONT if passed else _FAIL_FONT


def _write_metadata(worksheet: Worksheet, result: ReconciliationResult) -> None:
    _write_header(worksheet, ("Item", "Value"))
    metadata = result.metadata or {}
    rows = [
        ("schema_version", metadata.get("schema_version")),
        ("library_version", metadata.get("library_version")),
        ("generated_at_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("source_a", metadata.get("source_a")),
        ("source_b", metadata.get("source_b")),
        ("origin_a", metadata.get("origin_a")),
        ("origin_b", metadata.get("origin_b")),
        ("sheet_a", metadata.get("sheet_a")),
        ("sheet_b", metadata.get("sheet_b")),
        ("encoding", metadata.get("encoding")),
        ("delimiter", metadata.get("delimiter")),
        ("key_a", metadata.get("key_a")),
        ("key_b", metadata.get("key_b")),
        ("compared_fields", metadata.get("compared_fields")),
        ("ignore_case", metadata.get("ignore_case")),
        ("trim_whitespace", metadata.get("trim_whitespace")),
        ("ignore_nulls", metadata.get("ignore_nulls")),
        ("numeric_tolerance", metadata.get("numeric_tolerance")),
        ("detect_duplicates", metadata.get("detect_duplicates")),
        ("bidirectional", metadata.get("bidirectional")),
        ("blank_rows_skipped", metadata.get("blank_rows_skipped")),
        ("value_mappings", metadata.get("value_mappings")),
        ("comparison_rules", metadata.get("comparison_rules")),
        ("report_path", str(result.report_path) if result.report_path else None),
    ]
    for row_index, (item, value) in enumerate(rows, start=2):
        worksheet.cell(row_index, 1, item)
        worksheet.cell(row_index, 2, _metadata_text(value))
    _format_sheet(worksheet)


def _write_rows(worksheet: Worksheet, headers: tuple[str, ...], rows: list[list[Any]]) -> None:
    _write_header(worksheet, headers)
    for row_index, values in enumerate(rows, start=2):
        for column_index, value in enumerate(values, start=1):
            worksheet.cell(row_index, column_index, _cell_value(value))
    _format_sheet(worksheet)


def _write_header(worksheet: Worksheet, headers: tuple[str, ...]) -> None:
    for column_index, header in enumerate(headers, start=1):
        cell = worksheet.cell(1, column_index, header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center")


def _format_sheet(worksheet: Worksheet) -> None:
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = (
        f"A1:{get_column_letter(worksheet.max_column)}{max(worksheet.max_row, 1)}"
    )
    worksheet.row_dimensions[1].height = 22
    for row in worksheet.iter_rows(
        min_row=2,
        max_row=worksheet.max_row,
        max_col=worksheet.max_column,
    ):
        for cell in row:
            cell.font = _BODY_FONT
            cell.border = _THIN
            cell.alignment = Alignment(vertical="center")
    for column_index in range(1, worksheet.max_column + 1):
        letter = get_column_letter(column_index)
        width = 12
        for cell in worksheet[letter]:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 48))
        worksheet.column_dimensions[letter].width = width


def _detailed_rows(result: ReconciliationResult) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in result.details["compared"]:
        fields = item["fields"]
        if not fields:
            rows.append([item["key"], item["status"], item["row_a"], item["row_b"], None, None, None, None, None, None])
            continue
        for field in fields:
            rows.append(
                [
                    item["key"],
                    item["status"],
                    item["row_a"],
                    item["row_b"],
                    field["field_a"],
                    field["field_b"],
                    field["value_a"],
                    field["value_b"],
                    field["status"],
                    field["reason"],
                ]
            )
            if field["unmapped"]:
                rows.append(
                    [
                        item["key"],
                        item["status"],
                        item["row_a"],
                        item["row_b"],
                        field["field_a"],
                        field["field_b"],
                        field["value_a"],
                        field["value_b"],
                        "unmapped",
                        "unmapped",
                    ]
                )
    for item in result.details["missing_in_b"]:
        rows.append([item["key"], "missing_in_b", item["row"], None, None, None, None, None, None, None])
    for item in result.details["missing_in_a"]:
        rows.append([item["key"], "missing_in_a", None, item["row"], None, None, None, None, None, None])
    for item in result.details["duplicates"]:
        rows.append([item["key"], "duplicate", _side_row(item, "A"), _side_row(item, "B"), None, None, None, None, None, "duplicate"])
    for item in result.details["invalid_keys"]:
        rows.append(
            [
                item["key"],
                "invalid_key",
                _side_row(item, "A"),
                _side_row(item, "B"),
                None,
                None,
                None,
                None,
                None,
                item["reason"],
            ]
        )
    for item in result.details["blocked"]:
        rows.append(
            [
                item["key"],
                "blocked",
                _side_row(item, "A"),
                _side_row(item, "B"),
                None,
                None,
                None,
                None,
                None,
                item["reason"],
            ]
        )
    for item in result.details["not_evaluated"]:
        rows.append(
            [
                item["key"],
                "not_evaluated",
                _side_row(item, "A"),
                _side_row(item, "B"),
                None,
                None,
                None,
                None,
                None,
                item.get("reason"),
            ]
        )
    return rows


def _exception_rows(result: ReconciliationResult) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in result.details["field_issues"]:
        rows.append(
            [
                item["reason"],
                "A/B",
                item["key"],
                item["row_a"],
                item["field_a"],
                item["value_a"],
                item["value_b"],
                item["reason"],
            ]
        )
    for item in result.details["missing_in_a"]:
        rows.append(["missing_in_a", "B", item["key"], item["row"], None, None, None, "missing_in_a"])
    for item in result.details["missing_in_b"]:
        rows.append(["missing_in_b", "A", item["key"], item["row"], None, None, None, "missing_in_b"])
    for item in result.details["duplicates"]:
        rows.append(["duplicate", item["source"], item["key"], item["row"], None, None, None, "duplicate"])
    for item in result.details["invalid_keys"]:
        rows.append(["invalid_key", item["source"], item["key"], item["row"], None, None, None, item["reason"]])
    rows.sort(key=lambda row: tuple("" if value is None else str(value) for value in row))
    return rows


def _side_row(item: dict[str, Any], source: str) -> int | None:
    if item.get("source") != source:
        return None
    return item.get("row")


def _cell_value(value: Any) -> Any:
    if value is None:
        return None
    return value


def _metadata_text(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value
