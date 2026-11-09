"""Scalar normalization and the shared compare_values path."""

from __future__ import annotations

from datetime import datetime

from universal_utils.normalization import is_auto_numeric, normalize_value
from universal_utils.reconciliation import compare_values


def test_normalize_value_preserves_identifiers_and_applies_options() -> None:
    assert normalize_value("00123") == "00123"
    assert normalize_value(10) == "10"
    assert normalize_value(10.0) == "10"
    assert normalize_value(None) is None
    assert normalize_value("   ") is None
    assert normalize_value("  Ada  ", ignore_case=True) == "ada"
    assert normalize_value("  Ada  ", trim_whitespace=False) == "  Ada  "
    assert normalize_value(datetime(2024, 1, 2, 15, 30), as_date=True) == "2024-01-02"
    assert normalize_value("01/02/2024", as_date=True, date_formats=["%m/%d/%Y"]) == "2024-01-02"
    assert normalize_value("not-a-date", as_date=True) == "not-a-date"


def test_auto_numeric_rejects_leading_zero_identifiers() -> None:
    assert is_auto_numeric("10.00") is True
    assert is_auto_numeric("0.5") is True
    assert is_auto_numeric("0") is True
    assert is_auto_numeric("00123") is False
    assert is_auto_numeric("00.10") is False


def test_compare_values_uses_reconciliation_rules() -> None:
    assert compare_values("Ada", "ada", ignore_case=True) is True
    assert compare_values("Ada", "ada") is False
    assert compare_values(None, None) is True
    assert compare_values(None, "Ada", ignore_nulls=True) is True
    assert compare_values(None, "Ada") is False
    assert compare_values("10.00", "10.05", numeric_tolerance=0.05) is True
    assert compare_values("10.00", "10.06", numeric_tolerance=0.05) is False
    assert compare_values("10.00", "10", numeric_tolerance=0) is True
    assert compare_values("10.00", "10") is False
    assert compare_values("001", "1", numeric_tolerance=0.1) is False
    assert compare_values("001", "1", comparison_rule={"type": "number"}) is True
    assert compare_values("S0011", "Abandoned", value_mapping={"S0011": "Abandoned"}) is True
    assert compare_values("S9999", "S9999", value_mapping={"S0011": "Abandoned"}) is False
    assert compare_values(
        "01/02/2024",
        "2024-01-02",
        comparison_rule={"type": "date", "date_formats": ["%m/%d/%Y"]},
    ) is True
