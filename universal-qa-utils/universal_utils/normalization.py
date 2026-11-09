"""Shared canonicalization and value normalization.

Text is preserved exactly, including leading zeros. Numbers and dates are
converted to a stable form only when their original cell type is numeric or
temporal, or when a comparison rule explicitly asks for that comparison.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

DEFAULT_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d",
    "%Y%m%d",
)


def canonicalize_cell(value: Any) -> str | None:
    """Convert one raw cell to text without trimming, mapping, or case folding."""
    if _is_missing(value):
        return None
    if isinstance(value, str):
        return None if value == "" else value
    if _is_bool(value):
        return "True" if bool(value) else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, float):
        return format_float(value)
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if _is_numpy_integer(value):
        return str(int(value))
    if _is_numpy_float(value):
        return format_float(float(value))
    return str(value)


def normalize_value(
    value: Any,
    *,
    trim_whitespace: bool = True,
    ignore_case: bool = False,
    as_date: bool = False,
    date_formats: list[str] | tuple[str, ...] | None = None,
    empty_as_null: bool = True,
) -> str | None:
    """Normalize one value.

    Leading zeros in text are preserved. When ``as_date`` is true and the text
    does not match a supported date format, the trimmed text is returned unchanged.
    """
    text = apply_trim(
        canonicalize_cell(value),
        trim=trim_whitespace,
        empty_as_null=empty_as_null,
    )
    if text is None:
        return None
    if as_date:
        parsed = parse_date(text, date_formats)
        if parsed is not None:
            return parsed.isoformat()
        return text
    if ignore_case:
        return text.casefold()
    return text


def apply_trim(
    text: str | None,
    *,
    trim: bool,
    empty_as_null: bool = True,
) -> str | None:
    """Trim one already-canonical string. Non-breaking spaces are ordinary spaces."""
    if text is None:
        return None
    if not trim:
        return None if text == "" else text
    cleaned = text.replace("\u00a0", " ").strip()
    if empty_as_null and cleaned == "":
        return None
    return cleaned


def parse_date(
    text: str,
    date_formats: list[str] | tuple[str, ...] | None = None,
) -> date | None:
    """Parse a calendar date. ISO forms are tried before caller-supplied formats."""
    formats: list[str] = list(DEFAULT_DATE_FORMATS)
    if date_formats:
        for item in date_formats:
            if item not in formats:
                formats.append(item)
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(text: str) -> Decimal | None:
    """Parse a decimal. Leading zeros are accepted; callers decide whether to use them."""
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def is_auto_numeric(text: str) -> bool:
    """Return True for plain decimals that are not leading-zero identifiers.

    ``00123`` and ``00.10`` stay text so identifier zeros are not discarded.
    ``0``, ``0.5``, ``10``, and ``10.00`` are numeric.
    """
    if text == "" or any(token in text for token in ("e", "E", "+", " ")):
        return False
    unsigned = text[1:] if text.startswith("-") else text
    if len(unsigned) > 1 and unsigned.startswith("0") and not unsigned.startswith("0."):
        return False
    if "." in unsigned:
        whole, fractional = unsigned.split(".", 1)
        if fractional == "" or not whole.isdigit() or not fractional.isdigit():
            return False
    elif not unsigned.isdigit():
        return False
    return parse_number(text) is not None


def lookup_mapped_value(
    mapping: dict[str, str],
    value: str,
    *,
    ignore_case: bool,
) -> str | None:
    """Return the mapped text, or None when the code is not configured."""
    if value in mapping:
        return mapping[value]
    if not ignore_case:
        return None
    folded = value.casefold()
    for code, mapped in mapping.items():
        if code.casefold() == folded:
            return mapped
    return None


def format_decimal(value: Decimal) -> str:
    """Render a finite decimal without exponent notation or trailing zeros."""
    if not value.is_finite():
        if value.is_nan():
            return "NaN"
        return "inf" if value > 0 else "-inf"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"", "-", "-0"}:
        return "0"
    return rendered


def format_float(value: float) -> str | None:
    """Render an Excel or Python float, collapsing binary noise to 12 significant digits."""
    if math.isnan(value):
        return None
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    try:
        return format_decimal(Decimal(format(value, ".12g")))
    except InvalidOperation:
        return format(value, ".12g")


def format_datetime(value: datetime) -> str:
    """Render a datetime in UTC as a calendar date or a stable timestamp."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value.microsecond:
        return value.strftime("%Y-%m-%d %H:%M:%S.%f").rstrip("0").rstrip(".")
    if value.time() == time.min:
        return value.date().isoformat()
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) or isinstance(value, (bytes, bytearray)):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    if type(missing).__name__ == "bool_":
        return bool(missing)
    return False


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool) or type(value).__name__ == "bool_"


def _is_numpy_integer(value: Any) -> bool:
    return type(value).__module__ == "numpy" and type(value).__name__.startswith("int")


def _is_numpy_float(value: Any) -> bool:
    return type(value).__module__ == "numpy" and type(value).__name__.startswith("float")
