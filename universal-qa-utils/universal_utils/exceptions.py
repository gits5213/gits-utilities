"""Technical errors raised by the reconciliation library.

Business differences, such as mismatched fields or missing keys, are not errors.
They are reported on ReconciliationResult.
"""

from __future__ import annotations

from typing import Any


class UniversalUtilsError(Exception):
    """Base class for technical failures in universal_utils."""


class ValidationError(UniversalUtilsError):
    """Raised when a parameter or configuration value is invalid."""


class DataReadError(UniversalUtilsError):
    """Raised when a source file or table cannot be read."""


class DuplicateKeyError(UniversalUtilsError):
    """Raised when duplicate keys exist and detect_duplicates is False.

    The comparison does not guess which row to keep and does not expand the
    duplicates into a many-to-many comparison.
    """

    def __init__(self, message: str, duplicates: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.duplicates = duplicates


class ReportGenerationError(UniversalUtilsError):
    """Raised when an optional Excel report cannot be written."""
