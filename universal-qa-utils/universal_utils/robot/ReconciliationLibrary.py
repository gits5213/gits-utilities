"""Robot Framework keywords for the shared reconciliation engine.

Robot matches these names without regard to case or underscores:

- Compare Excel Files
- Compare CSV Files
- Get Reconciliation Summary
- Verify Reconciliation Passed

Scalar arguments and JSON strings are accepted. A ``config`` argument may
point at a JSON file. Explicit arguments replace values from that file.
``Compare Excel Files`` returns the full result dictionary and does not fail
when the business comparison has exceptions. ``Verify Reconciliation Passed``
performs that assertion.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from universal_utils.cli import execute_comparison, load_config
from universal_utils.exceptions import ValidationError
from universal_utils.models import LIBRARY_VERSION, METRIC_ORDER

_JSON_OBJECTS = {"field_mapping", "value_mappings", "comparison_rules"}
_BOOLEAN_OPTIONS = {
    "ignore_case",
    "trim_whitespace",
    "ignore_nulls",
    "detect_duplicates",
    "bidirectional",
    "generate_report",
}


class ReconciliationLibrary:
    """Suite-independent keywords. Each test gets its own last result."""

    ROBOT_LIBRARY_SCOPE = "TEST"
    ROBOT_LIBRARY_VERSION = LIBRARY_VERSION

    def __init__(self) -> None:
        self._last_result: dict[str, Any] | None = None

    def compare_excel_files(
        self,
        source_a: str | None = None,
        source_b: str | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Compare two workbooks and return the result dictionary."""
        return self._compare("excel", source_a, source_b, options)

    def compare_csv_files(
        self,
        source_a: str | None = None,
        source_b: str | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Compare two CSV files and return the result dictionary."""
        return self._compare("csv", source_a, source_b, options)

    def get_reconciliation_summary(self, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the metric fields from the last result, or from ``result``."""
        payload = self._require_result(result)
        return {name: payload[name] for name in METRIC_ORDER}

    def verify_reconciliation_passed(self, result: dict[str, Any] | None = None) -> None:
        """Fail the keyword when the reconciliation result is not passing."""
        payload = self._require_result(result)
        if payload.get("passed") is True:
            return
        raise AssertionError(
            "Reconciliation did not pass. "
            f"exceptions={payload.get('exceptions')} "
            f"mismatched={payload.get('mismatched')} "
            f"missing_in_a={payload.get('missing_in_a')} "
            f"missing_in_b={payload.get('missing_in_b')} "
            f"duplicates={payload.get('duplicates')} "
            f"invalid_keys={payload.get('invalid_keys')} "
            f"unmapped={payload.get('unmapped')}"
        )

    def _compare(
        self,
        source_type: str,
        source_a: str | None,
        source_b: str | None,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        config_path = options.get("config")
        if isinstance(config_path, str) and config_path.strip() != "":
            payload.update(load_config(config_path))
        configured_type = payload.get("source_type", source_type)
        if configured_type != source_type:
            raise ValidationError(
                f"Configuration source_type is {configured_type!r}; this keyword compares {source_type}."
            )
        payload["source_type"] = source_type
        if source_a not in (None, ""):
            payload["source_a"] = source_a
        if source_b not in (None, ""):
            payload["source_b"] = source_b
        for key, value in options.items():
            if key == "config" or value is None or value == "":
                continue
            payload[key] = _coerce_robot_value(key, value)
        stored = execute_comparison(payload).to_dict()
        self._last_result = stored
        return stored

    def _require_result(self, result: dict[str, Any] | None) -> dict[str, Any]:
        payload = result if result is not None else self._last_result
        if not isinstance(payload, dict) or "passed" not in payload:
            raise AssertionError("No reconciliation result is available.")
        return payload


def _coerce_robot_value(key: str, value: Any) -> Any:
    if key in _JSON_OBJECTS:
        return _coerce_object(key, value)
    if key in {"key_a", "key_b"}:
        return _coerce_key(value)
    if key in {"sheet_a", "sheet_b"}:
        return _coerce_sheet(value)
    if key in _BOOLEAN_OPTIONS:
        return _coerce_bool(key, value)
    if key == "numeric_tolerance":
        return _coerce_tolerance(value)
    return value


def _coerce_object(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{key} must be a JSON object.") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValidationError(f"{key} must be a JSON object.")


def _coerce_key(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError("A JSON key must be a list of column names.") from exc
        if not isinstance(parsed, list):
            raise ValidationError("A JSON key must be a list of column names.")
        return parsed
    return value


def _coerce_sheet(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"0|[1-9]\d*", stripped):
            return int(stripped)
        return stripped
    return value


def _coerce_bool(key: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValidationError(f"{key} must be true or false.")


def _coerce_tolerance(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "null", "none"}):
        return None
    if isinstance(value, bool):
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ValidationError("numeric_tolerance must be a finite number or null.") from exc
    raise ValidationError("numeric_tolerance must be a finite number or null.")
