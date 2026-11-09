"""Robot Framework keywords for openpyxl workbook comparison.

These keywords are separate from ReconciliationLibrary.

- Compare Excel Workbooks
- Get Excel Compare Summary
- Verify Excel Compare Passed

Compare Excel Workbooks returns the result and does not fail when workbooks
differ. Verify Excel Compare Passed performs that assertion. The result states
that formula calculation, charts, and shapes were not validated.
"""

from __future__ import annotations

from typing import Any

from universal_utils.exceptions import ValidationError
from universal_utils.excel_compare.engine import compare_workbooks
from universal_utils.normalization import parse_number

_SUMMARY_FIELDS = (
    "passed",
    "difference_count",
    "truncated",
    "formula_evaluation",
    "charts_compared",
    "shapes_compared",
    "password_decryption",
)


class ExcelCompareLibrary:
    """Suite-independent keywords. Each test gets its own last result."""

    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(self) -> None:
        self._last_result: dict[str, Any] | None = None

    def compare_excel_workbooks(
        self,
        reference: str,
        *targets: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Compare a reference workbook with one or more targets."""
        selected = options.pop("include_sheets", None)
        limit = _option_limit(options.pop("abort_after_differences", None))
        tolerance = _option_tolerance(options.pop("numeric_tolerance", None))
        include_cells = _option_bool(options, "include_cells", True)
        include_formulas = _option_bool(options, "include_formulas", False)
        include_formats = _option_bool(options, "include_formats", False)
        include_objects = _option_bool(options, "include_objects", False)
        ignore_case = _option_bool(options, "ignore_case", False)
        trim_whitespace = _option_bool(options, "trim_whitespace", False)
        unknown = sorted(options)
        if unknown:
            raise ValidationError(f"Unknown workbook comparison option {unknown[0]!r}.")
        result = compare_workbooks(
            reference,
            list(targets),
            include_cells=include_cells,
            include_formulas=include_formulas,
            include_formats=include_formats,
            include_objects=include_objects,
            include_sheets=_sheets(selected),
            abort_after_differences=limit,
            ignore_case=ignore_case,
            trim_whitespace=trim_whitespace,
            numeric_tolerance=tolerance,
        )
        self._last_result = result
        return result

    def get_excel_compare_summary(self, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the summary fields from the last result, or from ``result``."""
        payload = self._require_result(result)
        return {name: payload[name] for name in _SUMMARY_FIELDS}

    def verify_excel_compare_passed(self, result: dict[str, Any] | None = None) -> None:
        """Fail the keyword when the workbook comparison did not pass."""
        payload = self._require_result(result)
        if payload.get("passed") is True:
            return
        raise AssertionError(
            "Workbook comparison did not pass. "
            f"difference_count={payload.get('difference_count')} "
            f"truncated={payload.get('truncated')}"
        )

    def _require_result(self, result: dict[str, Any] | None) -> dict[str, Any]:
        payload = result if result is not None else self._last_result
        if not isinstance(payload, dict):
            raise AssertionError("No workbook comparison result is available.")
        return payload


def _sheets(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        names = [item.strip() for item in value.split(";") if item.strip()]
        if not names:
            raise ValidationError("include_sheets must name at least one worksheet.")
        return names
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    raise ValidationError("include_sheets must be a list of names or a semicolon-separated string.")


def _option_bool(options: dict[str, Any], name: str, default: bool) -> bool:
    if name not in options:
        return default
    value = options.pop(name)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValidationError(f"{name} must be true or false.")


def _option_limit(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValidationError("abort_after_differences must be an integer of 1 or greater.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        raise ValidationError("abort_after_differences must be an integer of 1 or greater.")
    if number < 1:
        raise ValidationError("abort_after_differences must be an integer of 1 or greater.")
    return number


def _option_tolerance(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError as exc:
            raise ValidationError("numeric_tolerance must be a finite number or null.") from exc
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    parsed = parse_number(str(number))
    if parsed is None or parsed < 0:
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    return number
