"""Typed results and internal source tables."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from universal_utils.exceptions import ValidationError

LIBRARY_VERSION = "0.1.0"
SCHEMA_VERSION = "1"

DETAIL_KEYS: tuple[str, ...] = (
    "compared",
    "matched",
    "mismatched",
    "missing_in_a",
    "missing_in_b",
    "duplicates",
    "invalid_keys",
    "unmapped",
    "blocked",
    "not_evaluated",
    "field_issues",
)

METRIC_ORDER: tuple[str, ...] = (
    "passed",
    "total_records",
    "matched",
    "mismatched",
    "missing_in_a",
    "missing_in_b",
    "duplicates",
    "unmapped",
    "invalid_keys",
    "exceptions",
)

METRIC_DEFINITIONS: dict[str, str] = {
    "passed": (
        "True only when exceptions is 0. Business differences are returned on "
        "this result and are not raised as technical errors."
    ),
    "total_records": (
        "Non-blank data rows read from both sources. A row is blank when every "
        "cell is empty after the trim setting is applied. Blank rows are omitted."
    ),
    "matched": (
        "Unique business keys that occur once in each source and whose compared "
        "fields all match, with no unmapped values."
    ),
    "mismatched": (
        "Unique business keys that occur once in each source and differ in at "
        "least one compared field."
    ),
    "missing_in_a": (
        "Unique valid keys present once in source B and absent from source A. "
        "The count is 0 when bidirectional is False."
    ),
    "missing_in_b": (
        "Unique valid keys present once in source A and absent from source B."
    ),
    "duplicates": (
        "Rows whose business key occurs more than once in that same source and "
        "which are in scope for this comparison. Those rows are not field-compared "
        "and are not expanded into many-to-many pairs."
    ),
    "unmapped": (
        "Compared keys with at least one source A value whose field has a value "
        "mapping but whose code is not in that mapping. A key can be both "
        "mismatched and unmapped."
    ),
    "invalid_keys": (
        "Non-blank rows with an empty key, or a composite key with an empty "
        "component. These rows are not also counted as missing."
    ),
    "exceptions": (
        "Distinct failing rows and keys. Each invalid row, in-scope duplicate row, "
        "missing key, and compared key that is mismatched or unmapped counts once. "
        "A key that is both mismatched and unmapped still counts once. Field issues "
        "are stored separately in details.field_issues."
    ),
}

_COUNT_FIELDS: tuple[str, ...] = (
    "total_records",
    "matched",
    "mismatched",
    "missing_in_a",
    "missing_in_b",
    "duplicates",
    "unmapped",
    "invalid_keys",
    "exceptions",
)


@dataclass(frozen=True)
class SourceRecord:
    """One data row after cell canonicalization."""

    row_number: int
    values: dict[str, str | None]


@dataclass(frozen=True)
class DataTable:
    """Tabular input shared by the Excel, CSV, and DataFrame readers."""

    columns: tuple[str, ...]
    records: tuple[SourceRecord, ...]
    origin: str


@dataclass(frozen=True)
class ReconciliationResult:
    """Structured outcome of one reconciliation run.

    Category counts describe why rows failed. ``exceptions`` counts each failing
    record once. ``details['field_issues']`` lists every field-level problem,
    including more than one problem on the same record.
    """

    passed: bool
    total_records: int
    matched: int
    mismatched: int
    missing_in_a: int
    missing_in_b: int
    duplicates: int
    unmapped: int
    invalid_keys: int
    exceptions: int
    details: dict[str, list[dict[str, Any]]]
    report_path: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be a boolean.")
        for name in _COUNT_FIELDS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"{name} must be a non-negative integer.")
        if self.passed != (self.exceptions == 0):
            raise ValidationError("passed must be True only when exceptions is 0.")
        if self.exceptions > self.total_records:
            raise ValidationError("exceptions cannot exceed total_records.")
        if not isinstance(self.details, dict) or set(self.details) != set(DETAIL_KEYS):
            raise ValidationError("details must contain the documented reconciliation keys.")
        for key in DETAIL_KEYS:
            if not isinstance(self.details[key], list):
                raise ValidationError(f"details[{key!r}] must be a list.")
        if self.metadata is None:
            object_metadata: dict[str, Any] = {}
        elif isinstance(self.metadata, dict):
            object_metadata = self.metadata
        else:
            raise ValidationError("metadata must be a dictionary.")
        object.__setattr__(self, "details", copy.deepcopy(self.details))
        object.__setattr__(self, "metadata", copy.deepcopy(object_metadata))
        if self.report_path is not None and not isinstance(self.report_path, str):
            raise ValidationError("report_path must be a string or None.")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the result in a stable field order."""
        return {
            "passed": self.passed,
            "total_records": self.total_records,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "missing_in_a": self.missing_in_a,
            "missing_in_b": self.missing_in_b,
            "duplicates": self.duplicates,
            "unmapped": self.unmapped,
            "invalid_keys": self.invalid_keys,
            "exceptions": self.exceptions,
            "details": copy.deepcopy(self.details),
            "report_path": self.report_path,
            "metadata": copy.deepcopy(self.metadata),
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the result. The same inputs always produce the same text."""
        return (
            json.dumps(
                self.to_dict(),
                indent=indent,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )

    def __str__(self) -> str:
        return (
            f"ReconciliationResult(passed={self.passed}, total_records={self.total_records}, "
            f"matched={self.matched}, mismatched={self.mismatched}, "
            f"missing_in_a={self.missing_in_a}, missing_in_b={self.missing_in_b}, "
            f"duplicates={self.duplicates}, unmapped={self.unmapped}, "
            f"invalid_keys={self.invalid_keys}, exceptions={self.exceptions})"
        )
