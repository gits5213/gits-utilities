"""Command-line entry point for openpyxl workbook comparison.

This command is separate from ``qa-utils``. Stdout is one JSON document unless
``--report-format text`` is selected. Logs go to stderr.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Sequence

from universal_utils.exceptions import ReportGenerationError, UniversalUtilsError, ValidationError
from universal_utils.excel_compare.engine import compare_workbooks
from universal_utils.excel_compare.report import render_text, to_json, write_report

EXIT_OK = 0
EXIT_TECHNICAL = 1
EXIT_BUSINESS = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, compare workbooks, and return a process exit code."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        options = _parse(argv)
        result = compare_workbooks(
            options["reference"],
            options["targets"],
            include_cells=options["include_cells"],
            include_formulas=options["include_formulas"],
            include_formats=options["include_formats"],
            include_objects=options["include_objects"],
            include_sheets=options["include_sheets"],
            abort_after_differences=options["abort_after_differences"],
            ignore_case=options["ignore_case"],
            trim_whitespace=options["trim_whitespace"],
            numeric_tolerance=options["numeric_tolerance"],
        )
    except UniversalUtilsError as exc:
        _emit_technical(exc)
        return EXIT_TECHNICAL
    except Exception as exc:  # noqa: BLE001
        _emit_technical(exc)
        return EXIT_TECHNICAL
    body = render_text(result) if options["report_format"] == "text" else to_json(result) + "\n"
    try:
        if options["output"] is not None:
            write_report(result, options["output"], options["report_format"])
    except ReportGenerationError as exc:
        _emit_technical(exc)
        return EXIT_TECHNICAL
    sys.stdout.write(body)
    if options["exit_code_mode"] == "defer" or result["passed"]:
        return EXIT_OK
    return EXIT_BUSINESS


def _parse(argv: Sequence[str] | None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        prog="qa-excel-compare",
        description=(
            "Compare Excel workbooks with openpyxl by worksheet and cell address. "
            "This does not calculate formulas or compare charts and shapes."
        ),
    )
    parser.error = _parser_error  # type: ignore[method-assign]
    parser.add_argument("--reference", required=True)
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--include-sheets", action="append", dest="include_sheets")
    parser.add_argument("--include-formulas", action="store_true")
    parser.add_argument("--include-formats", action="store_true")
    parser.add_argument("--include-objects", action="store_true")
    parser.add_argument("--no-cells", action="store_true")
    parser.add_argument("--abort-after", dest="abort_after_differences")
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--trim-whitespace", action="store_true")
    parser.add_argument("--numeric-tolerance")
    parser.add_argument("--output")
    parser.add_argument("--report-format", choices=("json", "text"), default="json")
    parser.add_argument("--exit-code-mode", choices=("strict", "defer"), default="strict")
    args = parser.parse_args(argv)
    tolerance = None
    if args.numeric_tolerance is not None:
        tolerance = _tolerance(args.numeric_tolerance)
    limit = None
    if args.abort_after_differences is not None:
        limit = _limit(args.abort_after_differences)
    return {
        "reference": args.reference,
        "targets": args.target,
        "include_sheets": args.include_sheets,
        "include_cells": not args.no_cells,
        "include_formulas": args.include_formulas,
        "include_formats": args.include_formats,
        "include_objects": args.include_objects,
        "abort_after_differences": limit,
        "ignore_case": args.ignore_case,
        "trim_whitespace": args.trim_whitespace,
        "numeric_tolerance": tolerance,
        "output": args.output,
        "report_format": args.report_format,
        "exit_code_mode": args.exit_code_mode,
    }


def _parser_error(message: str) -> None:
    raise ValidationError(message)


def _limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValidationError("abort-after must be an integer of 1 or greater.") from exc
    if number < 1:
        raise ValidationError("abort-after must be an integer of 1 or greater.")
    return number


def _tolerance(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValidationError("numeric-tolerance must be a finite number.") from exc
    if number < 0 or number != number or number in {float("inf"), float("-inf")}:
        raise ValidationError("numeric-tolerance must be a finite number.")
    return number


def _emit_technical(exc: BaseException) -> None:
    payload = {
        "status": "technical_failure",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    sys.stdout.write(to_json(payload) + "\n")
    logging.getLogger(__name__).error("%s: %s", type(exc).__name__, exc)
