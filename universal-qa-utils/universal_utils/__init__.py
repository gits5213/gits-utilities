"""Parameter-driven reconciliation utilities for test automation."""

from universal_utils.exceptions import (
    DataReadError,
    DuplicateKeyError,
    ReportGenerationError,
    UniversalUtilsError,
    ValidationError,
)
from universal_utils.models import LIBRARY_VERSION, ReconciliationResult
from universal_utils.normalization import normalize_value
from universal_utils.reconciliation import (
    compare_csv,
    compare_excel,
    compare_values,
    generate_reconciliation_report,
    reconcile_data,
)

__version__ = LIBRARY_VERSION

__all__ = [
    "DataReadError",
    "DuplicateKeyError",
    "ReconciliationResult",
    "ReportGenerationError",
    "UniversalUtilsError",
    "ValidationError",
    "compare_csv",
    "compare_excel",
    "compare_values",
    "generate_reconciliation_report",
    "normalize_value",
    "reconcile_data",
]
