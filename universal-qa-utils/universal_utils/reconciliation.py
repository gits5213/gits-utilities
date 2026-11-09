"""Public reconciliation entry points.

``compare_excel``, ``compare_csv``, and ``reconcile_data`` validate their
parameters, load a table, and call the same comparison engine.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from universal_utils.comparison import parse_request, reconcile_tables
from universal_utils.data_reader import read_csv_table, read_excel_table, table_from_dataframe
from universal_utils.exceptions import UniversalUtilsError, ValidationError
from universal_utils.models import ReconciliationResult
from universal_utils.reporting import generate_reconciliation_report

logger = logging.getLogger(__name__)


def compare_excel(
    source_a: str,
    source_b: str,
    sheet_a: str | int = 0,
    sheet_b: str | int = 0,
    key_a: str | list[str] = "",
    key_b: str | list[str] = "",
    field_mapping: dict[str, str] | None = None,
    value_mappings: dict | None = None,
    comparison_rules: dict | None = None,
    ignore_case: bool = False,
    trim_whitespace: bool = True,
    ignore_nulls: bool = False,
    numeric_tolerance: float | None = None,
    detect_duplicates: bool = True,
    bidirectional: bool = True,
    output_path: str | None = None,
    generate_report: bool = False,
) -> ReconciliationResult:
    """Compare two Excel worksheets.

    Column names, sheets, keys, mappings, and comparison behavior all come from
    the arguments. The engine does not assume an application-specific layout.
    ``generate_report=False`` returns the result without writing a file.
    """
    request = _request(
        key_a=key_a,
        key_b=key_b,
        field_mapping=field_mapping,
        value_mappings=value_mappings,
        comparison_rules=comparison_rules,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=numeric_tolerance,
        detect_duplicates=detect_duplicates,
        bidirectional=bidirectional,
        generate_report=generate_report,
        output_path=output_path,
    )
    _validate_sheet(sheet_a, "sheet_a")
    _validate_sheet(sheet_b, "sheet_b")
    path_a = _coerce_path(source_a, "source_a")
    path_b = _coerce_path(source_b, "source_b")
    return _finish(
        read_excel_table(path_a, sheet_a),
        read_excel_table(path_b, sheet_b),
        request,
        _metadata(
            source_a=str(path_a),
            source_b=str(path_b),
            sheet_a=sheet_a,
            sheet_b=sheet_b,
        ),
        generate_report=generate_report,
        output_path=output_path,
    )


def compare_csv(
    source_a: str,
    source_b: str,
    key_a: str | list[str] = "",
    key_b: str | list[str] = "",
    field_mapping: dict[str, str] | None = None,
    value_mappings: dict | None = None,
    comparison_rules: dict | None = None,
    ignore_case: bool = False,
    trim_whitespace: bool = True,
    ignore_nulls: bool = False,
    numeric_tolerance: float | None = None,
    detect_duplicates: bool = True,
    bidirectional: bool = True,
    output_path: str | None = None,
    generate_report: bool = False,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
) -> ReconciliationResult:
    """Compare two CSV files with the same engine used for Excel and DataFrames."""
    request = _request(
        key_a=key_a,
        key_b=key_b,
        field_mapping=field_mapping,
        value_mappings=value_mappings,
        comparison_rules=comparison_rules,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=numeric_tolerance,
        detect_duplicates=detect_duplicates,
        bidirectional=bidirectional,
        generate_report=generate_report,
        output_path=output_path,
    )
    path_a = _coerce_path(source_a, "source_a")
    path_b = _coerce_path(source_b, "source_b")
    return _finish(
        read_csv_table(path_a, encoding=encoding, delimiter=delimiter),
        read_csv_table(path_b, encoding=encoding, delimiter=delimiter),
        request,
        _metadata(
            source_a=str(path_a),
            source_b=str(path_b),
            encoding=encoding,
            delimiter=delimiter,
        ),
        generate_report=generate_report,
        output_path=output_path,
    )


def reconcile_data(
    source_a: pd.DataFrame,
    source_b: pd.DataFrame,
    key_a: str | list[str] = "",
    key_b: str | list[str] = "",
    field_mapping: dict[str, str] | None = None,
    value_mappings: dict | None = None,
    comparison_rules: dict | None = None,
    ignore_case: bool = False,
    trim_whitespace: bool = True,
    ignore_nulls: bool = False,
    numeric_tolerance: float | None = None,
    detect_duplicates: bool = True,
    bidirectional: bool = True,
    output_path: str | None = None,
    generate_report: bool = False,
) -> ReconciliationResult:
    """Compare two DataFrames with the same engine used for Excel and CSV."""
    request = _request(
        key_a=key_a,
        key_b=key_b,
        field_mapping=field_mapping,
        value_mappings=value_mappings,
        comparison_rules=comparison_rules,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=numeric_tolerance,
        detect_duplicates=detect_duplicates,
        bidirectional=bidirectional,
        generate_report=generate_report,
        output_path=output_path,
    )
    if not isinstance(source_a, pd.DataFrame) or not isinstance(source_b, pd.DataFrame):
        raise ValidationError(
            "reconcile_data sources must be pandas DataFrames. "
            "Use compare_excel or compare_csv for files."
        )
    return _finish(
        table_from_dataframe(source_a),
        table_from_dataframe(source_b),
        request,
        _metadata(source_a="dataframe", source_b="dataframe"),
        generate_report=generate_report,
        output_path=output_path,
    )


def compare_values(
    value_a: Any,
    value_b: Any,
    *,
    ignore_case: bool = False,
    trim_whitespace: bool = True,
    ignore_nulls: bool = False,
    numeric_tolerance: float | None = None,
    comparison_rule: dict | None = None,
    value_mapping: dict[str, str] | None = None,
) -> bool:
    """Compare two scalar values with the reconciliation engine.

    ``value_mapping`` is applied to ``value_a``. An unmapped non-null value does
    not match, even when the text is otherwise equal. The result is True only
    when the comparison has no exception.
    """
    rules = None if comparison_rule is None else {"value": comparison_rule}
    mappings = None if value_mapping is None else {"value": value_mapping}
    result = reconcile_data(
        pd.DataFrame([{"__key": "1", "value": value_a}]),
        pd.DataFrame([{"__key": "1", "value": value_b}]),
        key_a="__key",
        key_b="__key",
        field_mapping={"value": "value"},
        value_mappings=mappings,
        comparison_rules=rules,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=numeric_tolerance,
        detect_duplicates=True,
        bidirectional=True,
        generate_report=False,
    )
    return result.passed


def _request(
    *,
    key_a: str | list[str],
    key_b: str | list[str],
    field_mapping: dict[str, str] | None,
    value_mappings: dict | None,
    comparison_rules: dict | None,
    ignore_case: bool,
    trim_whitespace: bool,
    ignore_nulls: bool,
    numeric_tolerance: float | None,
    detect_duplicates: bool,
    bidirectional: bool,
    generate_report: bool,
    output_path: str | None,
) -> Any:
    if not isinstance(generate_report, bool):
        raise ValidationError("generate_report must be true or false.")
    if output_path is not None and not isinstance(output_path, (str, Path)):
        raise ValidationError("output_path must be a file path or None.")
    return parse_request(
        key_a=key_a,
        key_b=key_b,
        field_mapping=field_mapping,
        value_mappings=value_mappings,
        comparison_rules=comparison_rules,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=numeric_tolerance,
        detect_duplicates=detect_duplicates,
        bidirectional=bidirectional,
    )


def _finish(
    table_a: Any,
    table_b: Any,
    request: Any,
    metadata: dict[str, Any],
    *,
    generate_report: bool,
    output_path: str | None,
) -> ReconciliationResult:
    try:
        result = reconcile_tables(table_a, table_b, request, metadata)
        if generate_report:
            generate_reconciliation_report(result, output_path)
        elif output_path is not None:
            logger.info("generate_report is False; output_path was not used.")
        return result
    except UniversalUtilsError as exc:
        logger.error("Reconciliation error: %s", exc.__class__.__name__)
        raise


def _metadata(
    *,
    source_a: str,
    source_b: str,
    sheet_a: str | int | None = None,
    sheet_b: str | int | None = None,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> dict[str, Any]:
    return {
        "source_a": source_a,
        "source_b": source_b,
        "sheet_a": sheet_a,
        "sheet_b": sheet_b,
        "encoding": encoding,
        "delimiter": delimiter,
    }


def _validate_sheet(sheet: str | int, label: str) -> None:
    if isinstance(sheet, bool) or not isinstance(sheet, (str, int)):
        raise ValidationError(f"{label} must be a sheet name or a zero-based sheet index.")
    if isinstance(sheet, int) and sheet < 0:
        raise ValidationError(f"{label} must be zero or greater.")
    if isinstance(sheet, str) and sheet.strip() == "":
        raise ValidationError(f"{label} must not be empty.")


def _coerce_path(value: str, label: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip() != "":
        return Path(value)
    raise ValidationError(f"{label} must be a file path.")
