"""Read Excel workbooks, CSV files, and pandas DataFrames into one table shape."""

from __future__ import annotations

import csv
import codecs
import zipfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from universal_utils.exceptions import DataReadError, ValidationError
from universal_utils.models import DataTable, SourceRecord
from universal_utils.normalization import canonicalize_cell

ROW_NUMBER_SENTINEL = "__universal_utils_row_number__"


def read_excel_table(path: str | Path, sheet: str | int) -> DataTable:
    """Read one worksheet. The first row is the header and data rows start at row 2."""
    source = Path(path)
    if not source.is_file():
        raise DataReadError(f"Excel file not found: {source}")
    try:
        workbook = load_workbook(filename=source, data_only=True, read_only=False)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise DataReadError(f"Unable to read Excel file: {source}") from exc
    try:
        worksheet = _resolve_sheet(workbook, sheet, source)
        rows = worksheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration as exc:
            raise DataReadError(f"Sheet {worksheet.title!r} in {source.name} has no header row.") from exc
        columns = parse_headers(
            trim_trailing_empty_cells(header),
            origin=f"{source.name} sheet {worksheet.title!r}",
        )
        records = records_from_rows(
            columns,
            rows,
            origin=f"{source.name} sheet {worksheet.title!r}",
            first_row_number=2,
        )
        return DataTable(columns=columns, records=tuple(records), origin="excel")
    finally:
        workbook.close()


def read_csv_table(
    path: str | Path,
    *,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
) -> DataTable:
    """Read a CSV file. Every cell stays text, so leading zeros are preserved."""
    source = Path(path)
    if not source.is_file():
        raise DataReadError(f"CSV file not found: {source}")
    _validate_csv_options(encoding, delimiter)
    try:
        with source.open(newline="", encoding=encoding) as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise DataReadError(f"CSV file {source.name} has no header row.") from exc
            columns = parse_headers(trim_trailing_empty_cells(header), origin=source.name)
            records = records_from_rows(
                columns,
                reader,
                origin=source.name,
                first_row_number=2,
            )
    except UnicodeError as exc:
        raise DataReadError(f"Unable to decode CSV file {source.name} with encoding {encoding!r}.") from exc
    except csv.Error as exc:
        raise DataReadError(f"Unable to read CSV file: {source}") from exc
    return DataTable(columns=columns, records=tuple(records), origin="csv")


def table_from_dataframe(frame: pd.DataFrame) -> DataTable:
    """Copy a DataFrame into a table. Row numbers are 1-based positions, not index labels."""
    if not isinstance(frame, pd.DataFrame):
        raise ValidationError(
            "Expected a pandas DataFrame. Use compare_excel or compare_csv for files."
        )
    if isinstance(frame.columns, pd.MultiIndex):
        raise ValidationError("DataFrame columns must be a single level.")
    columns = parse_headers(tuple(frame.columns), origin="DataFrame")
    records: list[SourceRecord] = []
    for position, row in enumerate(frame.itertuples(index=False, name=None), start=1):
        values = {
            column: canonicalize_cell(cell)
            for column, cell in zip(columns, row, strict=True)
        }
        records.append(SourceRecord(row_number=position, values=values))
    return DataTable(columns=columns, records=tuple(records), origin="dataframe")


def trim_trailing_empty_cells(header_row: Iterable[Any]) -> list[Any]:
    """Drop empty cells after the last real header.

    A formatted column or a trailing CSV comma should not create a blank header.
    An empty header between two names is still rejected.
    """
    cells = list(header_row)
    while cells and _header_cell_is_empty(cells[-1]):
        cells.pop()
    return cells


def _header_cell_is_empty(cell: Any) -> bool:
    text = canonicalize_cell(cell)
    if text is None:
        return True
    return text.replace("\u00a0", " ").strip() == ""


def parse_headers(header_row: Iterable[Any], *, origin: str) -> tuple[str, ...]:
    """Normalize header cells. Headers are always stripped, independent of trim_whitespace."""
    columns: list[str] = []
    seen: set[str] = set()
    for index, cell in enumerate(header_row, start=1):
        text = canonicalize_cell(cell)
        if text is None:
            raise DataReadError(f"{origin} header column {index} is empty.")
        name = text.replace("\u00a0", " ").strip()
        if name == "":
            raise DataReadError(f"{origin} header column {index} is empty.")
        if name == ROW_NUMBER_SENTINEL:
            raise DataReadError(
                f"{origin} uses reserved column name {ROW_NUMBER_SENTINEL!r}. Rename that column."
            )
        if name in seen:
            raise DataReadError(f"{origin} header has duplicate column {name!r}.")
        seen.add(name)
        columns.append(name)
    if not columns:
        raise DataReadError(f"{origin} contains no columns.")
    return tuple(columns)


def records_from_rows(
    columns: tuple[str, ...],
    rows: Iterable[Any],
    *,
    origin: str,
    first_row_number: int,
) -> list[SourceRecord]:
    """Build records. Short rows are padded. Extra non-empty cells are rejected."""
    records: list[SourceRecord] = []
    width = len(columns)
    for offset, row in enumerate(rows):
        row_number = first_row_number + offset
        cells = list(row) if row is not None else []
        extras = cells[width:]
        if any(canonicalize_cell(cell) is not None for cell in extras):
            raise DataReadError(f"{origin} row {row_number} has values outside the header columns.")
        padded = cells[:width] + [None] * max(0, width - len(cells))
        values = {
            column: canonicalize_cell(cell)
            for column, cell in zip(columns, padded, strict=True)
        }
        records.append(SourceRecord(row_number=row_number, values=values))
    return records


def _resolve_sheet(workbook: Workbook, sheet: str | int, path: Path) -> Any:
    names = list(workbook.sheetnames)
    if isinstance(sheet, int):
        if sheet >= len(names):
            raise DataReadError(
                f"Sheet index {sheet} is outside {path.name}, which has {len(names)} sheet(s)."
            )
        return workbook[names[sheet]]
    if sheet not in names:
        available = ", ".join(repr(name) for name in names) or "<none>"
        raise DataReadError(
            f"Sheet {sheet!r} was not found in {path.name}. Available sheets: {available}."
        )
    return workbook[sheet]


def _validate_csv_options(encoding: str, delimiter: str) -> None:
    if not isinstance(encoding, str) or encoding.strip() == "":
        raise ValidationError("encoding must be a non-empty string.")
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        raise ValidationError(f"Unknown encoding {encoding!r}.") from exc
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValidationError("delimiter must be a single character.")

