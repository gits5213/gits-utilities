"""Process boundary used by Tosca. This does not execute Tosca Commander.

The PowerShell wrapper calls the installed package. Tosca Commander must run
this same command through the process module approved in that installation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from integration_lab.lab_evidence import save_process_evidence
from integration_lab.reconciliation_fixture import expected_document, materialize

WRAPPER = Path(__file__).resolve().parents[1] / "adapters" / "tosca" / "run_reconciliation.ps1"


def test_powershell_wrapper_returns_the_shared_fixture_result(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.fail("pwsh is not on PATH, so the Tosca process wrapper was not executed.")
    fixture = materialize(tmp_path / "fixture")
    strict_metrics = tmp_path / "strict.txt"
    defer_metrics = tmp_path / "defer.txt"
    strict = _wrapper(pwsh, fixture.config, strict_metrics, "strict")
    deferred = _wrapper(pwsh, fixture.config, defer_metrics, "defer")
    expected = expected_document()
    save_process_evidence(
        "tosca-process",
        "strict",
        strict,
        technical_status="success",
        business_status="fail",
        extra_files={"metrics.txt": strict_metrics},
    )
    save_process_evidence(
        "tosca-process",
        "defer",
        deferred,
        technical_status="success",
        business_status="fail",
        extra_files={"metrics.txt": defer_metrics},
    )

    assert strict.returncode == expected["strict_exit_code"], strict.stderr
    assert deferred.returncode == expected["defer_exit_code"], deferred.stderr
    assert _metrics(strict.stdout) == expected["metrics"]
    assert _metrics(deferred.stdout) == expected["metrics"]
    assert strict_metrics.read_text(encoding="utf-8").startswith("status=completed\npassed=false\n")
    script = WRAPPER.read_text(encoding="utf-8")
    assert "Invoke-Expression" not in script
    assert "& $Python @arguments" in script


def test_powershell_wrapper_technical_failure_exits_1(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.fail("pwsh is not on PATH, so the Tosca process wrapper was not executed.")
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
    completed = _wrapper(pwsh, config, result_file, "defer")
    save_process_evidence(
        "tosca-process",
        "technical",
        completed,
        technical_status="failure",
        business_status="not_run",
        extra_files={"technical.txt": result_file},
    )

    assert completed.returncode == expected_document()["technical_exit_code"], completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "technical_failure"
    assert payload["error_type"] == "DataReadError"
    assert result_file.read_text(encoding="utf-8").startswith("status=technical_failure\n")


def _wrapper(
    pwsh: str,
    config: Path,
    result_file: Path,
    exit_mode: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(WRAPPER),
            "-Python",
            sys.executable,
            "-Config",
            str(config),
            "-ResultFile",
            str(result_file),
            "-ExitCodeMode",
            exit_mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def _metrics(stdout: str) -> dict[str, object]:
    payload = json.loads(stdout)
    return {name: payload[name] for name in expected_document()["metrics"]}
