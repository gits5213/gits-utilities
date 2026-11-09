"""JSON and text projections of an openpyxl workbook comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from universal_utils.exceptions import ReportGenerationError, ValidationError

SCHEMA_VERSION = "1"


def result_document(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the public document with its schema and engine limits."""
    document = {
        "passed": payload["passed"],
        "difference_count": payload["difference_count"],
        "truncated": payload["truncated"],
        "excel_compare_schema_version": SCHEMA_VERSION,
        "engine": "openpyxl",
        "formula_evaluation": "not_performed",
        "charts_compared": False,
        "shapes_compared": False,
        "password_decryption": "not_supported",
        "unsupported": payload["unsupported"],
        "targets": payload["targets"],
    }
    return document


def to_json(payload: dict[str, Any]) -> str:
    """Serialize a result or technical failure with sorted keys."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def render_text(payload: dict[str, Any]) -> str:
    """Render a human-readable report. Cell values are included because they are the result."""
    lines = [
        "engine=openpyxl",
        "formula_evaluation=not_performed",
        "charts_compared=false",
        "shapes_compared=false",
        "password_decryption=not_supported",
        f"passed={str(payload['passed']).lower()}",
        f"difference_count={payload['difference_count']}",
        f"truncated={str(payload['truncated']).lower()}",
        "",
        "Unsupported capabilities are disclosed below. They were not validated.",
    ]
    for item in payload["unsupported"]:
        worksheet = item.get("worksheet")
        location = f" worksheet={worksheet}" if worksheet else ""
        lines.append(
            f"unsupported feature={item['feature']} status={item['status']}{location}"
        )
    lines.append("")
    for target in payload["targets"]:
        lines.append(f"reference={target['reference']}")
        lines.append(f"target={target['target']}")
        lines.append(f"target_passed={str(target['passed']).lower()}")
        lines.append(f"target_truncated={str(target['truncated']).lower()}")
        for difference in target["differences"]:
            lines.append(
                " ".join(
                    [
                        f"category={difference['category']}",
                        f"workbook={difference['workbook']}",
                        f"worksheet={difference['worksheet']}",
                        f"cell={difference['cell']}",
                        f"expected={_text(difference['expected'])}",
                        f"actual={_text(difference['actual'])}",
                    ]
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(payload: dict[str, Any], output_path: str | Path, report_format: str) -> str:
    """Write JSON or text. The format argument selects the projection."""
    if report_format not in {"json", "text"}:
        raise ValidationError("report_format must be 'json' or 'text'.")
    path = Path(output_path)
    body = to_json(payload) + "\n" if report_format == "json" else render_text(payload)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        raise ReportGenerationError(f"Unable to write workbook comparison report to {path}.") from exc
    return str(path.resolve())


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", "\\n")
