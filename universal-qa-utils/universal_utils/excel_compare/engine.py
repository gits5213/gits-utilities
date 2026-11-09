"""Compare workbooks by worksheet and cell address.

openpyxl reads the stored workbook. It does not calculate formulas, decrypt
files, or compare charts and shapes as Excel objects.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from openpyxl import load_workbook
from openpyxl.utils import coordinate_to_tuple
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from universal_utils.exceptions import DataReadError, ValidationError
from universal_utils.excel_compare.report import result_document
from universal_utils.normalization import parse_number

logger = logging.getLogger(__name__)

_SUPPORTED_SUFFIXES = {".xlsx", ".xlsm"}
_ENGINE_LIMITS = (
    {
        "feature": "calculated_formula_evaluation",
        "status": "not_performed",
        "reason": "Formula text is compared. openpyxl does not calculate formulas.",
    },
    {
        "feature": "charts",
        "status": "not_compared",
        "reason": "Charts are disclosed when present and are not compared.",
    },
    {
        "feature": "shapes",
        "status": "not_compared",
        "reason": "Shapes are not compared by this openpyxl-based engine.",
    },
    {
        "feature": "password_decryption",
        "status": "not_supported",
        "reason": "Encrypted workbooks are rejected. Decryption is not implemented.",
    },
)


def compare_workbooks(
    reference: str | Path,
    targets: str | Path | Sequence[str | Path],
    *,
    include_cells: bool = True,
    include_formulas: bool = False,
    include_formats: bool = False,
    include_objects: bool = False,
    include_sheets: Sequence[str] | None = None,
    abort_after_differences: int | None = None,
    ignore_case: bool = False,
    trim_whitespace: bool = False,
    numeric_tolerance: float | None = None,
) -> dict[str, Any]:
    """Compare one reference workbook with one or more target workbooks.

    The result is a dictionary. Business differences are entries in that
    dictionary. Missing files and unreadable workbooks raise technical errors.
    """
    reference_path = _require_workbook(reference, "reference")
    target_paths = _resolve_targets(targets)
    sheets = _require_sheets(include_sheets)
    limit = _require_limit(abort_after_differences)
    _require_bool(include_cells, "include_cells")
    _require_bool(include_formulas, "include_formulas")
    _require_bool(include_formats, "include_formats")
    _require_bool(include_objects, "include_objects")
    _require_bool(ignore_case, "ignore_case")
    _require_bool(trim_whitespace, "trim_whitespace")
    tolerance = _require_tolerance(numeric_tolerance)
    options = _Options(
        include_cells=include_cells,
        include_formulas=include_formulas,
        include_formats=include_formats,
        include_objects=include_objects,
        include_sheets=sheets,
        limit=limit,
        ignore_case=ignore_case,
        trim_whitespace=trim_whitespace,
        numeric_tolerance=tolerance,
    )
    compared: list[dict[str, Any]] = []
    observed_limits: list[dict[str, Any]] = []
    for target_path in target_paths:
        target_result, observations = _compare_pair(reference_path, target_path, options)
        compared.append(target_result)
        observed_limits.extend(observations)
    passed = all(item["passed"] for item in compared)
    difference_count = sum(item["difference_count"] for item in compared)
    truncated = any(item["truncated"] for item in compared)
    logger.info(
        "Workbook comparison finished targets=%s differences=%s truncated=%s passed=%s",
        len(compared),
        difference_count,
        truncated,
        passed,
    )
    return result_document(
        {
            "passed": passed,
            "difference_count": difference_count,
            "truncated": truncated,
            "unsupported": [*_ENGINE_LIMITS, *observed_limits],
            "targets": compared,
        }
    )


class _Options:
    def __init__(
        self,
        *,
        include_cells: bool,
        include_formulas: bool,
        include_formats: bool,
        include_objects: bool,
        include_sheets: tuple[str, ...] | None,
        limit: int | None,
        ignore_case: bool,
        trim_whitespace: bool,
        numeric_tolerance: Decimal | None,
    ) -> None:
        self.include_cells = include_cells
        self.include_formulas = include_formulas
        self.include_formats = include_formats
        self.include_objects = include_objects
        self.include_sheets = include_sheets
        self.limit = limit
        self.ignore_case = ignore_case
        self.trim_whitespace = trim_whitespace
        self.numeric_tolerance = numeric_tolerance


def _compare_pair(
    reference: Path,
    target: Path,
    options: _Options,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reference_book = _open_workbook(reference)
    target_book = _open_workbook(target)
    try:
        scope = _scope(reference_book, options.include_sheets)
        differences = _worksheet_differences(reference_book, target_book, target, scope, options)
        observations = _object_observations(reference_book, target_book)
        for name in scope:
            if name not in reference_book.sheetnames or name not in target_book.sheetnames:
                continue
            differences.extend(
                _sheet_differences(
                    reference_book[name],
                    target_book[name],
                    target,
                    options,
                )
            )
        if options.include_objects:
            differences.extend(_media_differences(reference, target))
        ordered = _ordered(differences)
        truncated = options.limit is not None and len(ordered) > options.limit
        if truncated:
            ordered = ordered[: options.limit]
        return (
            {
                "reference": str(reference),
                "target": str(target),
                "passed": not ordered,
                "truncated": truncated,
                "difference_count": len(ordered),
                "differences": ordered,
            },
            observations,
        )
    finally:
        reference_book.close()
        target_book.close()


def _scope(reference: Workbook, include_sheets: tuple[str, ...] | None) -> tuple[str, ...]:
    if include_sheets is None:
        return tuple(reference.sheetnames)
    missing = [name for name in include_sheets if name not in reference.sheetnames]
    if missing:
        raise ValidationError(
            f"Included sheet {missing[0]!r} was not found in the reference workbook."
        )
    return include_sheets


def _worksheet_differences(
    reference: Workbook,
    target: Workbook,
    target_path: Path,
    scope: tuple[str, ...],
    options: _Options,
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    reference_names = set(reference.sheetnames)
    target_names = set(target.sheetnames)
    for name in scope:
        if name not in target_names:
            differences.append(
                _difference(
                    "worksheet",
                    target_path,
                    name,
                    None,
                    "present",
                    "missing",
                )
            )
            continue
        expected_state = reference[name].sheet_state
        actual_state = target[name].sheet_state
        if expected_state != actual_state:
            differences.append(
                _difference(
                    "worksheet",
                    target_path,
                    name,
                    None,
                    expected_state,
                    actual_state,
                )
            )
    if options.include_sheets is None:
        for name in target.sheetnames:
            if name not in reference_names:
                differences.append(
                    _difference("worksheet", target_path, name, None, "missing", "present")
                )
    expected_order = [name for name in reference.sheetnames if name in scope and name in target_names]
    actual_order = [name for name in target.sheetnames if name in scope and name in reference_names]
    if expected_order != actual_order:
        differences.append(
            _difference(
                "worksheet_order",
                target_path,
                None,
                None,
                "|".join(expected_order),
                "|".join(actual_order),
            )
        )
    return differences


def _sheet_differences(
    reference: Worksheet,
    target: Worksheet,
    target_path: Path,
    options: _Options,
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    coordinates = sorted(set(reference._cells) | set(target._cells))
    for key in coordinates:
        expected_cell = reference._cells.get(key)
        actual_cell = target._cells.get(key)
        coordinate = (expected_cell or actual_cell).coordinate
        if options.include_cells and not _values_match(expected_cell, actual_cell, options):
            differences.append(
                _difference(
                    "cell_value",
                    target_path,
                    reference.title,
                    coordinate,
                    _display_value(expected_cell, options),
                    _display_value(actual_cell, options),
                )
            )
        if options.include_formulas and not _formulas_match(expected_cell, actual_cell):
            differences.append(
                _difference(
                    "formula",
                    target_path,
                    reference.title,
                    coordinate,
                    _formula_text(expected_cell),
                    _formula_text(actual_cell),
                )
            )
        if options.include_formats and _fingerprint(expected_cell) != _fingerprint(actual_cell):
            differences.append(
                _difference(
                    "formatting",
                    target_path,
                    reference.title,
                    coordinate,
                    _fingerprint(expected_cell),
                    _fingerprint(actual_cell),
                )
            )
    return differences


def _object_observations(reference: Workbook, target: Workbook) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for workbook, role in ((reference, "reference"), (target, "target")):
        for name in workbook.sheetnames:
            charts = getattr(workbook[name], "_charts", ())
            if charts:
                observations.append(
                    {
                        "feature": "charts",
                        "status": "not_compared",
                        "workbook_role": role,
                        "worksheet": name,
                        "count": len(charts),
                        "reason": "Charts were found and were not compared.",
                    }
                )
    return observations


def _media_differences(reference: Path, target: Path) -> list[dict[str, Any]]:
    expected = _media_tokens(reference)
    actual = _media_tokens(target)
    if expected == actual:
        return []
    return [_difference("object", target, None, None, expected, actual)]


def _media_tokens(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("xl/media/") and not name.endswith("/")
        )
        return [
            {"name": name, "sha256": hashlib.sha256(archive.read(name)).hexdigest()}
            for name in names
        ]


def _values_match(expected: Any, actual: Any, options: _Options) -> bool:
    left = _compare_value(expected, options)
    right = _compare_value(actual, options)
    if left is None and right is None:
        return True
    if (
        options.numeric_tolerance is not None
        and isinstance(left, Decimal)
        and isinstance(right, Decimal)
    ):
        return abs(left - right) <= options.numeric_tolerance
    return left == right


def _compare_value(cell: Any, options: _Options) -> str | Decimal | None:
    if cell is None or _is_formula(cell):
        return None
    value = cell.value
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(str(value))
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if options.trim_whitespace:
        text = text.replace("\u00a0", " ").strip()
    if text == "":
        return None
    if options.ignore_case:
        text = text.casefold()
    return text


def _display_value(cell: Any, options: _Options) -> Any:
    value = _compare_value(cell, options)
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _formulas_match(expected: Any, actual: Any) -> bool:
    return _formula_text(expected) == _formula_text(actual)


def _formula_text(cell: Any) -> str | None:
    if cell is None or not _is_formula(cell):
        return None
    return str(cell.value)


def _is_formula(cell: Any) -> bool:
    return isinstance(getattr(cell, "value", None), str) and cell.value.startswith("=")


def _fingerprint(cell: Any) -> dict[str, Any] | None:
    if cell is None:
        return None
    font = cell.font
    fill = cell.fill
    alignment = cell.alignment
    border = cell.border
    return {
        "number_format": cell.number_format,
        "font_name": font.name,
        "font_size": font.size,
        "font_bold": bool(font.bold),
        "font_italic": bool(font.italic),
        "font_color": _color_token(font.color),
        "fill_type": fill.fill_type,
        "fill_color": _color_token(getattr(fill, "fgColor", None)),
        "horizontal": alignment.horizontal,
        "vertical": alignment.vertical,
        "border_left": border.left.style,
        "border_right": border.right.style,
        "border_top": border.top.style,
        "border_bottom": border.bottom.style,
    }


def _color_token(color: Any) -> str | None:
    if color is None or color.type is None:
        return None
    if color.type == "rgb":
        return f"rgb:{color.rgb}"
    if color.type == "theme":
        return f"theme:{color.theme}:{color.tint}"
    if color.type == "indexed":
        return f"indexed:{color.indexed}"
    return color.type


def _difference(
    category: str,
    workbook: Path,
    worksheet: str | None,
    cell: str | None,
    expected: Any,
    actual: Any,
) -> dict[str, Any]:
    return {
        "category": category,
        "workbook": str(workbook),
        "worksheet": worksheet,
        "cell": cell,
        "expected": expected,
        "actual": actual,
    }


def _ordered(differences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    categories = {
        "worksheet": 0,
        "worksheet_order": 1,
        "cell_value": 2,
        "formula": 3,
        "formatting": 4,
        "object": 5,
    }
    return sorted(
        differences,
        key=lambda item: (
            categories.get(item["category"], 9),
            item["worksheet"] or "",
            coordinate_to_tuple(item["cell"]) if item["cell"] else (0, 0),
            item["category"],
        ),
    )


def _resolve_targets(targets: str | Path | Sequence[str | Path]) -> list[Path]:
    items = [targets] if isinstance(targets, (str, Path)) else list(targets)
    if not items:
        raise ValidationError("At least one target workbook is required.")
    resolved: list[Path] = []
    for item in items:
        if not isinstance(item, (str, Path)) or str(item).strip() == "":
            raise ValidationError("Each target must be a workbook path or a folder path.")
        path = Path(item)
        if path.is_dir():
            found = sorted(
                child
                for child in path.iterdir()
                if child.is_file()
                and child.suffix.lower() in _SUPPORTED_SUFFIXES
                and not child.name.startswith("~$")
            )
            if not found:
                raise ValidationError(f"No .xlsx or .xlsm workbooks were found in {path}.")
            resolved.extend(found)
            continue
        resolved.append(_require_workbook(path, "target"))
    return resolved


def _require_workbook(value: str | Path, label: str) -> Path:
    if not isinstance(value, (str, Path)) or str(value).strip() == "":
        raise ValidationError(f"{label} must be a workbook path.")
    path = Path(value)
    if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise DataReadError(
            f"Unsupported workbook type {path.suffix or '<none>'!r} for {path.name}. "
            "This openpyxl-based comparison reads .xlsx and .xlsm files."
        )
    if not path.is_file():
        raise DataReadError(f"Excel file not found: {path}")
    return path


def _open_workbook(path: Path) -> Workbook:
    try:
        return load_workbook(path, data_only=False)
    except (OSError, ValueError, zipfile.BadZipFile, InvalidFileException) as exc:
        raise DataReadError(f"Unable to read Excel file: {path}") from exc
    except Exception as exc:
        message = str(exc).lower()
        if "encrypt" in message or "password" in message:
            raise DataReadError(
                f"Unable to read Excel file: {path}. Encrypted workbooks are not decrypted."
            ) from exc
        raise


def _require_sheets(include_sheets: Sequence[str] | None) -> tuple[str, ...] | None:
    if include_sheets is None:
        return None
    if isinstance(include_sheets, str) or not isinstance(include_sheets, Sequence):
        raise ValidationError("include_sheets must be a sequence of sheet names.")
    names: list[str] = []
    for name in include_sheets:
        if not isinstance(name, str) or name.strip() == "":
            raise ValidationError("include_sheets entries must be non-empty sheet names.")
        if name not in names:
            names.append(name)
    if not names:
        raise ValidationError("include_sheets must name at least one worksheet.")
    return tuple(names)


def _require_limit(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError("abort_after_differences must be an integer of 1 or greater.")
    return value


def _require_tolerance(value: float | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    number = parse_number(str(value))
    if number is None or number < 0:
        raise ValidationError("numeric_tolerance must be a finite number or null.")
    return number


def _require_bool(value: bool, label: str) -> None:
    if not isinstance(value, bool):
        raise ValidationError(f"{label} must be true or false.")

