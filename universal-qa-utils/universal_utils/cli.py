"""Command-line entry point for the reconciliation engine.

Stdout is one JSON document. Logs go to stderr. Business differences are a
result with a non-zero exit code only in ``strict`` mode. They are not
technical failures.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

from universal_utils.exceptions import ReportGenerationError, UniversalUtilsError, ValidationError
from universal_utils.models import METRIC_ORDER, ReconciliationResult
from universal_utils.reconciliation import compare_csv, compare_excel

EXIT_OK = 0
EXIT_TECHNICAL = 1
EXIT_BUSINESS = 2

_PATH_OPTIONS = ("source_a", "source_b", "output_path")
_EXCEL_OPTIONS = {
    "source_a",
    "source_b",
    "sheet_a",
    "sheet_b",
    "key_a",
    "key_b",
    "field_mapping",
    "value_mappings",
    "comparison_rules",
    "ignore_case",
    "trim_whitespace",
    "ignore_nulls",
    "numeric_tolerance",
    "detect_duplicates",
    "bidirectional",
    "output_path",
    "generate_report",
}
_CSV_OPTIONS = (_EXCEL_OPTIONS - {"sheet_a", "sheet_b"}) | {"encoding", "delimiter"}
_CONFIG_OPTIONS = _EXCEL_OPTIONS | _CSV_OPTIONS | {"source_type"}


def execute_comparison(options: dict[str, Any]) -> ReconciliationResult:
    """Run one comparison from a plain option dictionary."""
    if not isinstance(options, dict):
        raise ValidationError("Comparison options must be a dictionary.")
    source_type = options.get("source_type", "excel")
    if source_type not in {"excel", "csv"}:
        raise ValidationError("source_type must be 'excel' or 'csv'.")
    allowed = _CSV_OPTIONS if source_type == "csv" else _EXCEL_OPTIONS
    unknown = sorted(set(options) - allowed - {"source_type"})
    if unknown:
        raise ValidationError(f"Unknown comparison option {unknown[0]!r}.")
    kwargs = {key: options[key] for key in allowed if key in options}
    if source_type == "csv":
        return compare_csv(**kwargs)
    return compare_excel(**kwargs)


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON config. Relative file paths are resolved from the config directory."""
    source = Path(path)
    if not source.is_file():
        raise ValidationError(f"Configuration file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Configuration file {source.name} is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Configuration file must contain a JSON object.")
    unknown = sorted(set(payload) - _CONFIG_OPTIONS)
    if unknown:
        raise ValidationError(f"Configuration file has unknown option {unknown[0]!r}.")
    base = source.parent.resolve()
    resolved = dict(payload)
    for key in _PATH_OPTIONS:
        value = resolved.get(key)
        if isinstance(value, str) and value.strip() != "" and not Path(value).is_absolute():
            resolved[key] = str((base / value).resolve())
    return resolved


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the engine, and return a process exit code."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        options, exit_mode, result_file = _parse_invocation(argv)
    except ValidationError as exc:
        _emit_technical(exc, None)
        return EXIT_TECHNICAL
    try:
        result = execute_comparison(options)
    except UniversalUtilsError as exc:
        _emit_technical(exc, result_file)
        return EXIT_TECHNICAL
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        _emit_technical(exc, result_file)
        return EXIT_TECHNICAL
    try:
        if result_file is not None:
            _write_metric_file(result_file, result.to_dict())
    except OSError:
        _emit_technical(ReportGenerationError(f"Unable to write result file {result_file}."), None)
        return EXIT_TECHNICAL
    sys.stdout.write(result.to_json())
    if exit_mode == "defer" or result.passed:
        return EXIT_OK
    return EXIT_BUSINESS


def _parse_invocation(argv: list[str] | None) -> tuple[dict[str, Any], str, Path | None]:
    parser = _parser()
    args = parser.parse_args(argv)
    options: dict[str, Any] = {}
    if args.config is not None:
        options.update(load_config(args.config))
    if args.source_type is not None:
        options["source_type"] = args.source_type
    _assign_text(options, "source_a", args.source_a)
    _assign_text(options, "source_b", args.source_b)
    if args.sheet_a is not None:
        options["sheet_a"] = _parse_sheet_flag(args.sheet_a)
    if args.sheet_b is not None:
        options["sheet_b"] = _parse_sheet_flag(args.sheet_b)
    if args.key_a:
        options["key_a"] = args.key_a[0] if len(args.key_a) == 1 else args.key_a
    if args.key_b:
        options["key_b"] = args.key_b[0] if len(args.key_b) == 1 else args.key_b
    if args.field_mapping is not None:
        options["field_mapping"] = _parse_json_object(args.field_mapping, "field_mapping")
    if args.value_mappings is not None:
        options["value_mappings"] = _parse_json_object(args.value_mappings, "value_mappings")
    if args.comparison_rules is not None:
        options["comparison_rules"] = _parse_json_object(args.comparison_rules, "comparison_rules")
    if args.numeric_tolerance is not None:
        options["numeric_tolerance"] = _parse_tolerance_flag(args.numeric_tolerance)
    for name in (
        "ignore_case",
        "trim_whitespace",
        "ignore_nulls",
        "detect_duplicates",
        "bidirectional",
        "generate_report",
    ):
        value = getattr(args, name)
        if value is not None:
            options[name] = value
    _assign_text(options, "output_path", args.output_path)
    _assign_text(options, "encoding", args.encoding)
    _assign_text(options, "delimiter", args.delimiter)
    result_file = Path(args.result_file) if args.result_file else None
    return options, args.exit_code_mode, result_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qa-utils",
        description="Compare two Excel or CSV sources and print a JSON reconciliation result.",
    )
    parser.error = _parser_error  # type: ignore[method-assign]
    parser.add_argument("--config", help="JSON file of comparison options.")
    parser.add_argument("--source-type", choices=("excel", "csv"))
    parser.add_argument("--source-a")
    parser.add_argument("--source-b")
    parser.add_argument("--sheet-a")
    parser.add_argument("--sheet-b")
    parser.add_argument("--key-a", action="append", dest="key_a")
    parser.add_argument("--key-b", action="append", dest="key_b")
    parser.add_argument("--field-mapping", help="JSON object of source A columns to source B columns.")
    parser.add_argument("--value-mappings", help="JSON object of source A value maps.")
    parser.add_argument("--comparison-rules", help="JSON object of per-field rules.")
    parser.add_argument("--numeric-tolerance")
    parser.add_argument("--output-path")
    parser.add_argument("--encoding")
    parser.add_argument("--delimiter")
    parser.add_argument("--ignore-case", action=argparse.BooleanOptionalAction)
    parser.add_argument("--trim-whitespace", action=argparse.BooleanOptionalAction)
    parser.add_argument("--ignore-nulls", action=argparse.BooleanOptionalAction)
    parser.add_argument("--detect-duplicates", action=argparse.BooleanOptionalAction)
    parser.add_argument("--bidirectional", action=argparse.BooleanOptionalAction)
    parser.add_argument("--generate-report", action=argparse.BooleanOptionalAction)
    parser.add_argument("--exit-code-mode", choices=("strict", "defer"), default="strict")
    parser.add_argument("--result-file", help="Optional key=value metrics file.")
    return parser


def _parser_error(message: str) -> None:
    raise ValidationError(message)


def _assign_text(options: dict[str, Any], key: str, value: str | None) -> None:
    if value is not None:
        options[key] = value


def _parse_sheet_flag(value: str) -> str | int:
    if value.isascii() and value.isdigit() and (value == "0" or not value.startswith("0")):
        return int(value)
    return value


def _parse_json_object(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ValidationError(f"{label} must be a JSON object.")
    return parsed


def _parse_tolerance_flag(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValidationError("numeric_tolerance must be a finite number or null.") from exc
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    return number


def _emit_technical(exc: BaseException, result_file: Path | None) -> None:
    payload = {
        "status": "technical_failure",
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }
    if result_file is not None:
        try:
            _write_lines(
                result_file,
                [
                    "status=technical_failure",
                    f"error_type={exc.__class__.__name__}",
                    "message=" + " ".join(str(exc).splitlines()),
                ],
            )
        except OSError:
            logging.getLogger(__name__).error("Unable to write result file.")
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _write_metric_file(path: Path, result: dict[str, Any]) -> None:
    lines = ["status=completed"]
    for name in METRIC_ORDER:
        value = result[name]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.append(f"{name}={rendered}")
    _write_lines(path, lines)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
