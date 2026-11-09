"""Parameter-driven reconciliation of two already-loaded tables.

Excel, CSV, and DataFrame entry points all call ``reconcile_tables``. Nothing
in this module knows about a particular application, workbook, or column layout.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from universal_utils.exceptions import DuplicateKeyError, ValidationError
from universal_utils.models import (
    DETAIL_KEYS,
    LIBRARY_VERSION,
    SCHEMA_VERSION,
    DataTable,
    ReconciliationResult,
    SourceRecord,
)
from universal_utils.normalization import (
    apply_trim,
    format_decimal,
    is_auto_numeric,
    lookup_mapped_value,
    parse_date,
    parse_number,
)

logger = logging.getLogger(__name__)

KEY_DELIMITER = "||"
_RULE_KEYS = {
    "type",
    "numeric_tolerance",
    "ignore_case",
    "trim_whitespace",
    "ignore_nulls",
    "date_formats",
}
_TYPE_ALIASES = {
    "auto": "auto",
    "string": "string",
    "text": "string",
    "str": "string",
    "number": "number",
    "numeric": "number",
    "date": "date",
    "datetime": "date",
}


@dataclass(frozen=True)
class FieldRule:
    """Effective comparison rule for one source A field."""

    field_type: str
    ignore_case: bool
    trim_whitespace: bool
    ignore_nulls: bool
    numeric_tolerance: Decimal | None
    date_formats: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonRequest:
    """Validated caller options that do not yet depend on header names."""

    key_a: tuple[str, ...]
    key_b: tuple[str, ...]
    field_mapping: dict[str, str] | None
    value_mappings: dict[str, dict[str, str]]
    comparison_rules: dict[str, dict[str, Any]]
    ignore_case: bool
    trim_whitespace: bool
    ignore_nulls: bool
    numeric_tolerance: Decimal | None
    detect_duplicates: bool
    bidirectional: bool


def parse_request(
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
) -> ComparisonRequest:
    """Validate parameter shapes. Column existence is checked after the sources are read."""
    _require_bool(ignore_case, "ignore_case")
    _require_bool(trim_whitespace, "trim_whitespace")
    _require_bool(ignore_nulls, "ignore_nulls")
    _require_bool(detect_duplicates, "detect_duplicates")
    _require_bool(bidirectional, "bidirectional")
    return ComparisonRequest(
        key_a=_coerce_key_columns(key_a, "key_a"),
        key_b=_coerce_key_columns(key_b, "key_b"),
        field_mapping=_coerce_field_mapping(field_mapping),
        value_mappings=_coerce_value_mappings(value_mappings),
        comparison_rules=_coerce_comparison_rules(comparison_rules),
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=_parse_tolerance(numeric_tolerance, "numeric_tolerance"),
        detect_duplicates=detect_duplicates,
        bidirectional=bidirectional,
    )


def reconcile_tables(
    table_a: DataTable,
    table_b: DataTable,
    request: ComparisonRequest,
    metadata_base: dict[str, Any],
) -> ReconciliationResult:
    """Compare two tables and return a deterministic result."""
    _require_columns(table_a, request.key_a, "key_a")
    _require_columns(table_b, request.key_b, "key_b")
    mapping = _resolve_mapping(table_a, table_b, request)
    rules = {field: _effective_rule(field, request) for field in mapping}
    normalized_maps = _normalize_value_mappings(request, rules)

    rows_a, blank_a = _nonblank_rows(table_a, request.trim_whitespace)
    rows_b, blank_b = _nonblank_rows(table_b, request.trim_whitespace)
    invalid_a, groups_a = _classify(rows_a, request.key_a, request)
    invalid_b, groups_b = _classify(rows_b, request.key_b, request)

    unique_a, duplicates_a = _split_groups(groups_a)
    unique_b, duplicates_b, ignored_b = _split_source_b(groups_b, groups_a, request.bidirectional)
    if not request.detect_duplicates and (duplicates_a or duplicates_b):
        _raise_duplicate_keys(duplicates_a, duplicates_b)

    both = sorted(set(unique_a) & set(unique_b))
    blocked_a = sorted(key for key in unique_a if key in duplicates_b)
    blocked_b = sorted(key for key in unique_b if key in duplicates_a)
    only_a = sorted(set(unique_a) - set(groups_b))
    only_b = sorted(set(unique_b) - set(groups_a))

    compared: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    mismatched: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    field_issues: list[dict[str, Any]] = []

    for identity in both:
        components_a, record_a = unique_a[identity]
        _, record_b = unique_b[identity]
        record_detail, record_issues, unmapped_fields, status = _compare_key(
            identity_display=components_a,
            record_a=record_a,
            record_b=record_b,
            mapping=mapping,
            rules=rules,
            normalized_maps=normalized_maps,
        )
        compared.append(record_detail)
        field_issues.extend(record_issues)
        if status == "matched":
            matched.append(record_detail)
        elif status == "mismatched":
            mismatched.append(record_detail)
        if unmapped_fields:
            unmapped.append(
                {
                    "key": record_detail["key"],
                    "key_components": list(record_detail["key_components"]),
                    "row_a": record_a.row_number,
                    "row_b": record_b.row_number,
                    "fields": unmapped_fields,
                }
            )

    missing_in_b = [_one_sided("A", unique_a[key]) for key in only_a]
    missing_in_a = [_one_sided("B", unique_b[key]) for key in only_b] if request.bidirectional else []
    not_evaluated = []
    if not request.bidirectional:
        not_evaluated.extend(_one_sided("B", unique_b[key], reason="bidirectional_disabled") for key in only_b)
        for identity in sorted(ignored_b):
            for components, record in ignored_b[identity]:
                not_evaluated.append(
                    _row_detail("B", components, record, reason="bidirectional_disabled")
                )
    not_evaluated.sort(key=lambda item: (item["source"], item["row"], tuple(item["key_components"])))

    duplicate_details = _duplicate_details(duplicates_a, groups_b, "A")
    duplicate_details.extend(_duplicate_details(duplicates_b, groups_a, "B"))
    invalid_details = _invalid_details(invalid_a, request.key_a, "A")
    invalid_details.extend(_invalid_details(invalid_b, request.key_b, "B"))
    blocked = [_blocked("A", unique_a[key]) for key in blocked_a]
    blocked.extend(_blocked("B", unique_b[key]) for key in blocked_b)

    details = {
        "compared": compared,
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_a": missing_in_a,
        "missing_in_b": missing_in_b,
        "duplicates": duplicate_details,
        "invalid_keys": invalid_details,
        "unmapped": unmapped,
        "blocked": blocked,
        "not_evaluated": not_evaluated,
        "field_issues": field_issues,
    }
    total_records = len(rows_a) + len(rows_b)
    exception_count = _exception_count(details)
    _assert_row_accounting(details, total_records)

    result = ReconciliationResult(
        passed=exception_count == 0,
        total_records=total_records,
        matched=len(matched),
        mismatched=len(mismatched),
        missing_in_a=len(missing_in_a),
        missing_in_b=len(missing_in_b),
        duplicates=len(duplicate_details),
        unmapped=len(unmapped),
        invalid_keys=len(invalid_details),
        exceptions=exception_count,
        details=details,
        report_path=None,
        metadata=_metadata(
            table_a,
            table_b,
            request,
            metadata_base,
            mapping,
            rules,
            normalized_maps,
            blank_a,
            blank_b,
        ),
    )
    logger.info(
        "Reconciliation finished origin_a=%s origin_b=%s total_records=%s matched=%s "
        "mismatched=%s missing_in_a=%s missing_in_b=%s duplicates=%s invalid_keys=%s "
        "unmapped=%s exceptions=%s passed=%s",
        table_a.origin,
        table_b.origin,
        result.total_records,
        result.matched,
        result.mismatched,
        result.missing_in_a,
        result.missing_in_b,
        result.duplicates,
        result.invalid_keys,
        result.unmapped,
        result.exceptions,
        result.passed,
    )
    return result


def _compare_key(
    *,
    identity_display: tuple[str, ...],
    record_a: SourceRecord,
    record_b: SourceRecord,
    mapping: dict[str, str],
    rules: dict[str, FieldRule],
    normalized_maps: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]], str]:
    fields: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    unmapped_fields: list[dict[str, str]] = []
    any_mismatch = False
    for field_a, field_b in mapping.items():
        rule = rules[field_a]
        text_a = apply_trim(record_a.values.get(field_a), trim=rule.trim_whitespace)
        text_b = apply_trim(record_b.values.get(field_b), trim=rule.trim_whitespace)
        unmapped = False
        if field_a in normalized_maps and text_a is not None:
            mapped = lookup_mapped_value(
                normalized_maps[field_a],
                text_a,
                ignore_case=rule.ignore_case,
            )
            if mapped is None:
                unmapped = True
            else:
                text_a = apply_trim(mapped, trim=rule.trim_whitespace)
        matched, reason = _values_match(text_a, text_b, rule)
        fields.append(
            {
                "field_a": field_a,
                "field_b": field_b,
                "value_a": text_a,
                "value_b": text_b,
                "status": "matched" if matched else reason,
                "reason": "" if matched else reason,
                "unmapped": unmapped,
            }
        )
        base_issue = {
            "key": _display(identity_display),
            "key_components": list(identity_display),
            "row_a": record_a.row_number,
            "row_b": record_b.row_number,
            "field_a": field_a,
            "field_b": field_b,
        }
        if unmapped:
            original = apply_trim(record_a.values.get(field_a), trim=rule.trim_whitespace)
            unmapped_fields.append({"field": field_a, "value": original or ""})
            issues.append(
                {
                    **base_issue,
                    "value_a": original,
                    "value_b": text_b,
                    "reason": "unmapped",
                }
            )
        if not matched:
            any_mismatch = True
            issues.append({**base_issue, "value_a": text_a, "value_b": text_b, "reason": reason})

    if any_mismatch:
        status = "mismatched"
    elif unmapped_fields:
        status = "unmapped"
    else:
        status = "matched"
    detail = {
        "key": _display(identity_display),
        "key_components": list(identity_display),
        "row_a": record_a.row_number,
        "row_b": record_b.row_number,
        "status": status,
        "fields": fields,
    }
    return detail, issues, unmapped_fields, status


def _values_match(left: str | None, right: str | None, rule: FieldRule) -> tuple[bool, str]:
    if left is None and right is None:
        return True, "matched"
    if left is None or right is None:
        if rule.ignore_nulls:
            return True, "matched"
        return False, "null_mismatch"
    if rule.field_type == "date":
        parsed_left = parse_date(left, rule.date_formats)
        parsed_right = parse_date(right, rule.date_formats)
        if parsed_left is None or parsed_right is None:
            return False, "date_parse_failure"
        return (parsed_left == parsed_right), ("matched" if parsed_left == parsed_right else "mismatch")
    use_number = rule.field_type == "number" or (
        rule.field_type == "auto"
        and rule.numeric_tolerance is not None
        and is_auto_numeric(left)
        and is_auto_numeric(right)
    )
    if use_number:
        number_left = parse_number(left)
        number_right = parse_number(right)
        if number_left is None or number_right is None:
            return False, "number_parse_failure"
        tolerance = rule.numeric_tolerance if rule.numeric_tolerance is not None else Decimal("0")
        if abs(number_left - number_right) <= tolerance:
            return True, "matched"
        return False, "mismatch"
    if rule.ignore_case:
        left = left.casefold()
        right = right.casefold()
    if left == right:
        return True, "matched"
    return False, "mismatch"


def _classify(
    records: list[SourceRecord],
    key_columns: tuple[str, ...],
    request: ComparisonRequest,
) -> tuple[
    list[tuple[tuple[str | None, ...], SourceRecord]],
    dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]],
]:
    invalid: list[tuple[tuple[str | None, ...], SourceRecord]] = []
    grouped: dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]] = defaultdict(list)
    for record in records:
        components = tuple(
            apply_trim(record.values.get(column), trim=request.trim_whitespace) for column in key_columns
        )
        if any(part is None for part in components):
            invalid.append((components, record))
            continue
        identity = tuple(part.casefold() for part in components) if request.ignore_case else components
        grouped[identity].append((components, record))
    return invalid, grouped


def _split_groups(
    groups: dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]],
) -> tuple[
    dict[tuple[str, ...], tuple[tuple[str, ...], SourceRecord]],
    dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
]:
    unique: dict[tuple[str, ...], tuple[tuple[str, ...], SourceRecord]] = {}
    duplicates: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]] = {}
    for identity, entries in groups.items():
        ordered = tuple(sorted(entries, key=lambda item: item[1].row_number))
        if len(ordered) == 1:
            unique[identity] = ordered[0]
        else:
            duplicates[identity] = ordered
    return unique, duplicates


def _split_source_b(
    groups_b: dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]],
    groups_a: dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]],
    bidirectional: bool,
) -> tuple[
    dict[tuple[str, ...], tuple[tuple[str, ...], SourceRecord]],
    dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
    dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
]:
    unique: dict[tuple[str, ...], tuple[tuple[str, ...], SourceRecord]] = {}
    duplicates: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]] = {}
    ignored: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]] = {}
    for identity, entries in groups_b.items():
        ordered = tuple(sorted(entries, key=lambda item: item[1].row_number))
        if len(ordered) == 1:
            unique[identity] = ordered[0]
            continue
        if bidirectional or identity in groups_a:
            duplicates[identity] = ordered
        else:
            ignored[identity] = ordered
    return unique, duplicates, ignored


def _raise_duplicate_keys(
    duplicates_a: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
    duplicates_b: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
) -> None:
    summaries: list[dict[str, Any]] = []
    for source, groups in (("A", duplicates_a), ("B", duplicates_b)):
        for identity in sorted(groups):
            entries = groups[identity]
            summaries.append(
                {
                    "source": source,
                    "key": _display(entries[0][0]),
                    "key_components": list(entries[0][0]),
                    "occurrences": len(entries),
                    "rows": [record.row_number for _, record in entries],
                }
            )
    preview = ", ".join(f"{item['source']}:{item['key']}" for item in summaries[:10])
    suffix = "" if len(summaries) <= 10 else f" and {len(summaries) - 10} more"
    raise DuplicateKeyError(
        "Duplicate keys were found while detect_duplicates is False. "
        "The comparison did not run, because pairing those keys would either discard rows "
        "or expand into a many-to-many comparison. "
        f"Duplicate groups: {len(summaries)} ({preview}{suffix}).",
        summaries,
    )


def _duplicate_details(
    duplicates: dict[tuple[str, ...], tuple[tuple[tuple[str, ...], SourceRecord], ...]],
    other_groups: dict[tuple[str, ...], list[tuple[tuple[str, ...], SourceRecord]]],
    source: str,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for identity in sorted(duplicates):
        entries = duplicates[identity]
        counterpart_rows = sorted(record.row_number for _, record in other_groups.get(identity, []))
        for components, record in entries:
            details.append(
                {
                    "source": source,
                    "key": _display(components),
                    "key_components": list(components),
                    "row": record.row_number,
                    "occurrences": len(entries),
                    "present_in_other_source": identity in other_groups,
                    "counterpart_rows": counterpart_rows,
                }
            )
    return details


def _invalid_details(
    invalid: list[tuple[tuple[str | None, ...], SourceRecord]],
    key_columns: tuple[str, ...],
    source: str,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for components, record in invalid:
        display_parts = tuple("" if part is None else part for part in components)
        empty_components = [
            column for column, part in zip(key_columns, components, strict=True) if part is None
        ]
        reason = "empty_key" if len(empty_components) == len(key_columns) else "empty_key_component"
        details.append(
            {
                "source": source,
                "key": _display(display_parts),
                "key_components": list(display_parts),
                "row": record.row_number,
                "reason": reason,
                "empty_components": empty_components,
            }
        )
    details.sort(key=lambda item: (item["source"], item["row"]))
    return details


def _one_sided(
    source: str,
    entry: tuple[tuple[str, ...], SourceRecord],
    reason: str | None = None,
) -> dict[str, Any]:
    components, record = entry
    return _row_detail(source, components, record, reason=reason)


def _blocked(source: str, entry: tuple[tuple[str, ...], SourceRecord]) -> dict[str, Any]:
    return _one_sided(source, entry, reason="counterpart_duplicate")


def _row_detail(
    source: str,
    components: tuple[str, ...],
    record: SourceRecord,
    *,
    reason: str | None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "source": source,
        "key": _display(components),
        "key_components": list(components),
        "row": record.row_number,
    }
    if reason is not None:
        detail["reason"] = reason
    return detail


def _display(components: tuple[str, ...]) -> str:
    return KEY_DELIMITER.join(components)


def _exception_count(details: dict[str, list[dict[str, Any]]]) -> int:
    identities: set[tuple[Any, ...]] = set()
    for item in details["invalid_keys"]:
        identities.add(("invalid", item["source"], item["row"]))
    for item in details["duplicates"]:
        identities.add(("duplicate", item["source"], item["row"]))
    for item in details["missing_in_a"]:
        identities.add(("missing_in_a", tuple(item["key_components"])))
    for item in details["missing_in_b"]:
        identities.add(("missing_in_b", tuple(item["key_components"])))
    for item in details["compared"]:
        if item["status"] != "matched":
            identities.add(("compared", tuple(item["key_components"])))
    return len(identities)


def _assert_row_accounting(details: dict[str, list[dict[str, Any]]], total_records: int) -> None:
    accounted = (
        len(details["compared"]) * 2
        + len(details["missing_in_a"])
        + len(details["missing_in_b"])
        + len(details["duplicates"])
        + len(details["invalid_keys"])
        + len(details["blocked"])
        + len(details["not_evaluated"])
    )
    if accounted != total_records:
        raise RuntimeError(
            "Row accounting failed: "
            f"accounted={accounted} total_records={total_records} "
            f"detail_counts={{"
            + ", ".join(f"{key}={len(details[key])}" for key in DETAIL_KEYS)
            + "}"
        )


def _nonblank_rows(table: DataTable, trim: bool) -> tuple[list[SourceRecord], int]:
    kept: list[SourceRecord] = []
    blank = 0
    for record in table.records:
        if _is_blank(record, table.columns, trim):
            blank += 1
            continue
        kept.append(record)
    return kept, blank


def _is_blank(record: SourceRecord, columns: tuple[str, ...], trim: bool) -> bool:
    for column in columns:
        if apply_trim(record.values.get(column), trim=trim) is not None:
            return False
    return True


def _resolve_mapping(
    table_a: DataTable,
    table_b: DataTable,
    request: ComparisonRequest,
) -> dict[str, str]:
    if request.field_mapping is None:
        key_names = set(request.key_a)
        available_b = set(table_b.columns)
        mapping = {
            column: column
            for column in table_a.columns
            if column not in key_names and column in available_b
        }
    else:
        mapping = dict(request.field_mapping)
        _require_columns(table_a, tuple(mapping), "field_mapping source A")
        _require_columns(table_b, tuple(mapping.values()), "field_mapping source B")
    unknown_rules = sorted(set(request.comparison_rules) - set(mapping))
    if unknown_rules:
        raise ValidationError(
            "comparison_rules column "
            f"{unknown_rules[0]!r} is not part of the comparison. "
            f"Compared source A columns: {_column_list(mapping)}."
        )
    unknown_maps = sorted(set(request.value_mappings) - set(mapping))
    if unknown_maps:
        raise ValidationError(
            "value_mappings column "
            f"{unknown_maps[0]!r} is not part of the comparison. "
            f"Compared source A columns: {_column_list(mapping)}."
        )
    return mapping


def _column_list(mapping: dict[str, str]) -> str:
    if not mapping:
        return "<none>"
    return ", ".join(repr(column) for column in mapping)


def _effective_rule(field: str, request: ComparisonRequest) -> FieldRule:
    raw = request.comparison_rules.get(field, {})
    field_type = _coerce_type(raw.get("type", "auto"), field)
    explicit_case = "ignore_case" in raw
    ignore_case = raw["ignore_case"] if explicit_case else request.ignore_case
    trim_whitespace = raw.get("trim_whitespace", request.trim_whitespace)
    ignore_nulls = raw.get("ignore_nulls", request.ignore_nulls)
    _require_bool(ignore_case, f"comparison_rules[{field!r}].ignore_case")
    _require_bool(trim_whitespace, f"comparison_rules[{field!r}].trim_whitespace")
    _require_bool(ignore_nulls, f"comparison_rules[{field!r}].ignore_nulls")
    date_formats = _coerce_date_formats(raw.get("date_formats"), field) if "date_formats" in raw else ()
    if "numeric_tolerance" in raw:
        tolerance: Decimal | None = _parse_tolerance(
            raw["numeric_tolerance"],
            f"comparison_rules[{field!r}].numeric_tolerance",
        )
    else:
        tolerance = request.numeric_tolerance

    if field_type in {"number", "date"} and explicit_case and ignore_case:
        raise ValidationError(
            f"comparison_rules for {field!r} conflict: ignore_case cannot be combined with type {field_type!r}."
        )
    if field_type == "string" and "numeric_tolerance" in raw:
        raise ValidationError(
            f"comparison_rules for {field!r} conflict: numeric_tolerance cannot be combined with type 'string'."
        )
    if field_type == "date" and "numeric_tolerance" in raw:
        raise ValidationError(
            f"comparison_rules for {field!r} conflict: numeric_tolerance cannot be combined with type 'date'."
        )
    if field_type != "date" and "date_formats" in raw:
        raise ValidationError(
            f"comparison_rules for {field!r} conflict: date_formats requires type 'date'."
        )
    if field_type == "string":
        tolerance = None
        date_formats = ()
    elif field_type == "date":
        tolerance = None
        ignore_case = False
    elif field_type == "number":
        ignore_case = False
    return FieldRule(
        field_type=field_type,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        ignore_nulls=ignore_nulls,
        numeric_tolerance=tolerance,
        date_formats=date_formats,
    )


def _normalize_value_mappings(
    request: ComparisonRequest,
    rules: dict[str, FieldRule],
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for field, mapping in request.value_mappings.items():
        rule = rules[field]
        folded_owner: dict[str, str] = {}
        cleaned: dict[str, str] = {}
        for code, description in mapping.items():
            code_text = apply_trim(code, trim=rule.trim_whitespace)
            if code_text is None:
                raise ValidationError(f"value_mappings for {field!r} contains an empty code.")
            mapped_text = apply_trim(description, trim=rule.trim_whitespace)
            stored = "" if mapped_text is None else mapped_text
            if code_text in cleaned and cleaned[code_text] != stored:
                raise ValidationError(
                    f"value_mappings for {field!r} defines {code_text!r} more than once "
                    "with different descriptions."
                )
            cleaned[code_text] = stored
            if rule.ignore_case:
                folded = code_text.casefold()
                previous = folded_owner.get(folded)
                if previous is not None and previous != code_text:
                    raise ValidationError(
                        f"value_mappings for {field!r} has codes {previous!r} and {code_text!r} "
                        "that are equal when ignore_case is True."
                    )
                folded_owner[folded] = code_text
        normalized[field] = cleaned
    return normalized


def _metadata(
    table_a: DataTable,
    table_b: DataTable,
    request: ComparisonRequest,
    base: dict[str, Any],
    mapping: dict[str, str],
    rules: dict[str, FieldRule],
    normalized_maps: dict[str, dict[str, str]],
    blank_a: int,
    blank_b: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "library_version": LIBRARY_VERSION,
        "source_a": base.get("source_a"),
        "source_b": base.get("source_b"),
        "origin_a": table_a.origin,
        "origin_b": table_b.origin,
        "sheet_a": base.get("sheet_a"),
        "sheet_b": base.get("sheet_b"),
        "encoding": base.get("encoding"),
        "delimiter": base.get("delimiter"),
        "key_a": list(request.key_a),
        "key_b": list(request.key_b),
        "compared_fields": [
            {"source_a": field_a, "source_b": field_b} for field_a, field_b in mapping.items()
        ],
        "ignore_case": request.ignore_case,
        "trim_whitespace": request.trim_whitespace,
        "ignore_nulls": request.ignore_nulls,
        "numeric_tolerance": _decimal_text(request.numeric_tolerance),
        "detect_duplicates": request.detect_duplicates,
        "bidirectional": request.bidirectional,
        "blank_rows_skipped": {"source_a": blank_a, "source_b": blank_b},
        "value_mappings": {field: dict(mapping) for field, mapping in normalized_maps.items()},
        "comparison_rules": {field: _rule_metadata(rule) for field, rule in rules.items()},
    }


def _rule_metadata(rule: FieldRule) -> dict[str, Any]:
    return {
        "type": rule.field_type,
        "ignore_case": rule.ignore_case,
        "trim_whitespace": rule.trim_whitespace,
        "ignore_nulls": rule.ignore_nulls,
        "numeric_tolerance": _decimal_text(rule.numeric_tolerance),
        "date_formats": list(rule.date_formats),
    }


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format_decimal(value)


def _require_columns(table: DataTable, columns: tuple[str, ...], label: str) -> None:
    missing = [column for column in columns if column not in table.columns]
    if not missing:
        return
    available = ", ".join(repr(column) for column in table.columns) or "<none>"
    names = ", ".join(repr(column) for column in missing)
    raise ValidationError(f"Column {names} in {label} was not found. Available columns: {available}.")


def _coerce_key_columns(value: str | list[str], label: str) -> tuple[str, ...]:
    if isinstance(value, str):
        columns: list[Any] = [value]
    elif isinstance(value, (list, tuple)) and not isinstance(value, str):
        if len(value) == 0:
            raise ValidationError(
                f"{label} must be a non-empty column name or a non-empty list of column names."
            )
        columns = list(value)
    else:
        raise ValidationError(f"{label} must be a column name or a list of column names.")
    normalized: list[str] = []
    for column in columns:
        if not isinstance(column, str):
            raise ValidationError(f"{label} must contain only column names.")
        name = column.replace("\u00a0", " ").strip()
        if name == "":
            raise ValidationError(
                f"{label} must be a non-empty column name or a non-empty list of column names."
            )
        normalized.append(name)
    if len(set(normalized)) != len(normalized):
        raise ValidationError(f"{label} contains duplicate column names.")
    return tuple(normalized)


def _coerce_field_mapping(value: dict[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError("field_mapping must be a dictionary of source A columns to source B columns.")
    mapping: dict[str, str] = {}
    for source, target in value.items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValidationError("field_mapping keys and values must be column names.")
        left = source.replace("\u00a0", " ").strip()
        right = target.replace("\u00a0", " ").strip()
        if left == "" or right == "":
            raise ValidationError("field_mapping column names must not be empty.")
        mapping[left] = right
    return mapping


def _coerce_value_mappings(value: dict | None) -> dict[str, dict[str, str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("value_mappings must be a dictionary of field names to code maps.")
    normalized: dict[str, dict[str, str]] = {}
    for field, mapping in value.items():
        if not isinstance(field, str) or field.replace("\u00a0", " ").strip() == "":
            raise ValidationError("value_mappings field names must be non-empty strings.")
        field_name = field.replace("\u00a0", " ").strip()
        if not isinstance(mapping, dict):
            raise ValidationError(f"value_mappings for {field_name!r} must be a dictionary of codes.")
        codes: dict[str, str] = {}
        for code, description in mapping.items():
            if not isinstance(code, str) or not isinstance(description, str):
                raise ValidationError(
                    f"value_mappings for {field_name!r} must use strings, so leading zeros are preserved."
                )
            codes[code] = description
        normalized[field_name] = codes
    return normalized


def _coerce_comparison_rules(value: dict | None) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("comparison_rules must be a dictionary of field names to rule dictionaries.")
    normalized: dict[str, dict[str, Any]] = {}
    for field, rule in value.items():
        if not isinstance(field, str) or field.replace("\u00a0", " ").strip() == "":
            raise ValidationError("comparison_rules field names must be non-empty strings.")
        field_name = field.replace("\u00a0", " ").strip()
        if not isinstance(rule, dict):
            raise ValidationError(f"comparison_rules for {field_name!r} must be a dictionary.")
        unknown = sorted(set(rule) - _RULE_KEYS)
        if unknown:
            raise ValidationError(
                f"comparison_rules for {field_name!r} has unknown option {unknown[0]!r}."
            )
        normalized[field_name] = dict(rule)
    return normalized


def _coerce_type(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"comparison_rules for {field!r} type must be a string.")
    field_type = _TYPE_ALIASES.get(value)
    if field_type is None:
        raise ValidationError(
            f"comparison_rules for {field!r} has unsupported type {value!r}. "
            "Use 'string', 'number', 'date', or 'auto'."
        )
    return field_type


def _coerce_date_formats(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or len(value) == 0:
        raise ValidationError(
            f"comparison_rules for {field!r} date_formats must be a non-empty list of format strings."
        )
    formats: list[str] = []
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            raise ValidationError(
                f"comparison_rules for {field!r} date_formats must contain non-empty strings."
            )
        _validate_date_format(item, field)
        formats.append(item)
    return tuple(formats)


def _validate_date_format(fmt: str, field: str) -> None:
    try:
        datetime.strptime("2000-01-02 03:04:05", fmt)
    except ValueError as exc:
        if "bad directive" in str(exc).lower():
            raise ValidationError(
                f"comparison_rules for {field!r} has invalid date format {fmt!r}."
            ) from exc


def _parse_tolerance(value: Any, label: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise ValidationError(f"{label} must be a finite number or null.")
    if isinstance(value, float) and not _is_finite_float(value):
        raise ValidationError(f"{label} must be a finite number or null.")
    if isinstance(value, str) and value.strip() == "":
        raise ValidationError(f"{label} must be a finite number or null.")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except Exception as exc:
        raise ValidationError(f"{label} must be a finite number or null.") from exc
    if not number.is_finite() or number < 0:
        raise ValidationError(f"{label} must be zero or greater.")
    return number


def _is_finite_float(value: float) -> bool:
    return value == value and value not in {float("inf"), float("-inf")}


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise ValidationError(f"{label} must be true or false.")
