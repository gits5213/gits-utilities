"""CLI integration tests for the installed qa-utils command.

These tests execute the console script. They do not call the comparison
engine in-process. Robot Framework, Playwright, and Tosca are later consumers
of the same fixture.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from integration_lab.lab_evidence import save_process_evidence
from integration_lab.reconciliation_fixture import (
    DETAIL_KEYS,
    RESULT_KEYS,
    TECHNICAL_KEYS,
    expected_document,
    materialize,
)

_POWERSHELL = """
$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
& $env:QA_UTILS --config $env:QA_CONFIG --exit-code-mode strict --result-file $env:QA_RESULT
exit $LASTEXITCODE
"""


def test_strict_cli_matches_the_shared_fixture_and_writes_evidence(tmp_path: Path) -> None:
    fixture = materialize(tmp_path / "fixture")
    result_file = tmp_path / "metrics.txt"
    completed = _run_qa_utils(
        [
            "--config",
            str(fixture.config),
            "--exit-code-mode",
            "strict",
            "--result-file",
            str(result_file),
        ]
    )
    payload = _one_json_document(completed.stdout)
    expected = expected_document()
    evidence = save_process_evidence(
        "cli",
        "strict",
        completed,
        technical_status="success",
        business_status=str(expected["business_status"]),
        extra_files={"metrics.txt": result_file, "ledger_report.xlsx": fixture.report},
    )

    assert completed.returncode == expected["strict_exit_code"], completed.stderr
    assert payload["passed"] is False
    assert _metrics(payload) == expected["metrics"]
    assert list(payload) == list(RESULT_KEYS)
    assert tuple(sorted(payload["details"])) == DETAIL_KEYS
    assert _keys(payload, "matched") == expected["keys"]["matched"]
    assert _keys(payload, "mismatched") == expected["keys"]["mismatched"]
    assert _keys(payload, "missing_in_a") == expected["keys"]["missing_in_a"]
    assert _keys(payload, "missing_in_b") == expected["keys"]["missing_in_b"]
    assert _keys(payload, "duplicates") == expected["keys"]["duplicates"]
    assert _keys(payload, "unmapped") == expected["keys"]["unmapped"]
    assert _keys(payload, "invalid_keys") == expected["keys"]["invalid_keys"]
    assert _keys(payload, "blocked") == expected["keys"]["blocked"]
    assert payload["details"]["not_evaluated"] == []
    assert _field_issues(payload) == expected["field_issues"]
    assert payload["metadata"]["schema_version"] == expected["schema_version"]
    assert payload["metadata"]["library_version"] == expected["library_version"]
    assert payload["metadata"]["numeric_tolerance"] == "0.01"
    assert payload["metadata"]["sheet_a"] == "Ledger"
    assert payload["metadata"]["sheet_b"] == "Directory"
    assert payload["report_path"] == str(fixture.report.resolve())
    assert _report_sheets(fixture.report) == [
        "Summary",
        "Detailed Comparison",
        "Exceptions Only",
        "Execution Metadata",
    ]
    assert result_file.read_text(encoding="utf-8") == _metric_file(expected["metrics"])
    assert "Ada Lovelace" not in completed.stderr
    assert "S0011" not in completed.stderr
    assert "INFO" not in completed.stdout
    assert (evidence / "stdout.txt").is_file()
    assert (evidence / "ledger_report.xlsx").is_file()


def test_defer_keeps_technical_success_when_reconciliation_fails(tmp_path: Path) -> None:
    fixture = materialize(tmp_path / "fixture")
    completed = _run_qa_utils(
        ["--config", str(fixture.config), "--exit-code-mode", "defer"]
    )
    payload = _one_json_document(completed.stdout)
    expected = expected_document()
    save_process_evidence(
        "cli",
        "defer",
        completed,
        technical_status="success",
        business_status=str(expected["business_status"]),
    )

    assert completed.returncode == expected["defer_exit_code"], completed.stderr
    assert payload["passed"] is False
    assert _metrics(payload) == expected["metrics"]
    assert "status" not in payload


def test_missing_workbook_is_a_technical_failure(tmp_path: Path) -> None:
    config = tmp_path / "missing.json"
    config.write_text(
        json.dumps(
            {
                "source_type": "excel",
                "source_a": "missing_a.xlsx",
                "source_b": "missing_b.xlsx",
                "key_a": "Account",
                "key_b": "Account ID",
            }
        ),
        encoding="utf-8",
    )
    result_file = tmp_path / "technical.txt"
    completed = _run_qa_utils(
        [
            "--config",
            str(config),
            "--exit-code-mode",
            "strict",
            "--result-file",
            str(result_file),
        ]
    )
    payload = _one_json_document(completed.stdout)
    save_process_evidence(
        "cli",
        "technical",
        completed,
        technical_status="failure",
        business_status="not_run",
        extra_files={"technical.txt": result_file},
    )

    assert completed.returncode == expected_document()["technical_exit_code"]
    assert tuple(payload) == TECHNICAL_KEYS
    assert payload["status"] == "technical_failure"
    assert payload["error_type"] == "DataReadError"
    assert isinstance(payload["message"], str) and payload["message"]
    assert "passed" not in payload
    assert result_file.read_text(encoding="utf-8").startswith("status=technical_failure\n")


def test_powershell_runs_the_same_qa_utils_fixture(tmp_path: Path) -> None:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.fail("pwsh is not on PATH, so the PowerShell CLI consumer was not executed.")
    fixture = materialize(tmp_path / "fixture")
    result_file = tmp_path / "metrics.txt"
    cli = _qa_utils_executable()
    completed = subprocess.run(
        [executable, "-NoProfile", "-Command", _POWERSHELL],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "QA_UTILS": str(cli),
            "QA_CONFIG": str(fixture.config),
            "QA_RESULT": str(result_file),
        },
    )
    payload = _one_json_document(completed.stdout)
    expected = expected_document()
    save_process_evidence(
        "powershell",
        "strict",
        completed,
        technical_status="success",
        business_status=str(expected["business_status"]),
        extra_files={"metrics.txt": result_file},
    )

    assert completed.returncode == expected["strict_exit_code"], completed.stderr
    assert payload["passed"] is False
    assert _metrics(payload) == expected["metrics"]
    assert result_file.read_text(encoding="utf-8") == _metric_file(expected["metrics"])


def _qa_utils_executable() -> Path:
    name = "qa-utils.exe" if os.name == "nt" else "qa-utils"
    candidate = Path(sys.executable).with_name(name)
    if not candidate.is_file():
        pytest.fail(
            f"{name} is not installed beside {sys.executable}. "
            'Install this environment with: pip install -e ".[dev]"'
        )
    script = candidate.read_text(encoding="utf-8")
    if "from universal_utils.cli import main" not in script:
        pytest.fail(f"{candidate} is not the installed qa-utils entry point.")
    return candidate


def _run_qa_utils(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_qa_utils_executable()), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _one_json_document(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise AssertionError("CLI stdout must be one JSON object.")
    return payload


def _metrics(payload: dict[str, Any]) -> dict[str, Any]:
    return {name: payload[name] for name in expected_document()["metrics"]}


def _keys(payload: dict[str, Any], category: str) -> list[str]:
    return [item["key"] for item in payload["details"][category]]


def _field_issues(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "key": item["key"],
            "field_a": item["field_a"],
            "reason": item["reason"],
            "value_a": item["value_a"],
            "value_b": item["value_b"],
        }
        for item in payload["details"]["field_issues"]
    ]


def _metric_file(metrics: dict[str, Any]) -> str:
    lines = ["status=completed"]
    for name, value in metrics.items():
        rendered = "true" if value is True else "false" if value is False else str(value)
        lines.append(f"{name}={rendered}")
    return "\n".join(lines) + "\n"


def _report_sheets(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()
