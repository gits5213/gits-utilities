"""Helpers for synthetic workbooks and CSV files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from openpyxl import Workbook


def write_excel(path: Path, sheets: dict[str, list[list[Any]]]) -> Path:
    workbook = Workbook()
    names = list(sheets)
    workbook.active.title = names[0]
    for row in sheets[names[0]]:
        workbook.active.append(row)
    for name in names[1:]:
        worksheet = workbook.create_sheet(name)
        for row in sheets[name]:
            worksheet.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()
    return path


def write_csv(
    path: Path,
    rows: list[list[Any]],
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding=encoding) as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        for row in rows:
            writer.writerow(["" if cell is None else cell for cell in row])
    return path
