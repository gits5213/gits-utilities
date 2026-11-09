"""Robot, process CLI, and Playwright client adapters."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.robot.ReconciliationLibrary import ReconciliationLibrary
from tests.conftest import write_csv, write_excel

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "universal_utils.cli"]
SHIM = [sys.executable, str(ROOT / "adapters" / "tosca" / "reconciliation_cli.py")]
CLIENT_CHECK = ROOT / "tests" / "playwright_client_check.ts"
POWERSHELL = ROOT / "adapters" / "tosca" / "run_reconciliation.ps1"


def _run(args: list[str], *, program: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (program or CLI) + args,
        check=False,
        capture_output=True,
        text=True,
    )


def _pair(tmp_path: Path, left: list[list[object]], right: list[list[object]]) -> tuple[Path, Path]:
    return (
        write_excel(tmp_path / "a.xlsx", {"Data": left}),
        write_excel(tmp_path / "b.xlsx", {"Data": right}),
    )


def test_robot_keywords_return_a_dictionary_and_verify(tmp_path: Path) -> None:
    source_a, source_b = _pair(
        tmp_path,
        [["ID", "Name"], ["001", "Ada"]],
        [["Code", "Name"], ["001", "Ada"]],
    )
    library = ReconciliationLibrary()
    result = library.compare_excel_files(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="Code",
        field_mapping='{"Name": "Name"}',
    )
    assert result["passed"] is True
    assert result["details"]["matched"][0]["key"] == "001"
    summary = library.get_reconciliation_summary()
    assert summary["matched"] == 1
    library.verify_reconciliation_passed()
    library.verify_reconciliation_passed(result)


def test_robot_business_failure_is_not_a_keyword_error(tmp_path: Path) -> None:
    source_a, source_b = _pair(
        tmp_path,
        [["ID", "Name"], ["1", "SECRET-CELL"]],
        [["ID", "Name"], ["1", "Other"]],
    )
    library = ReconciliationLibrary()
    result = library.compare_excel_files(str(source_a), str(source_b), key_a="ID", key_b="ID")
    assert result["passed"] is False
    assert result["exceptions"] == 1
    with pytest.raises(AssertionError, match="exceptions=1") as captured:
        library.verify_reconciliation_passed()
    assert "SECRET-CELL" not in str(captured.value)


def test_robot_config_json_and_csv(tmp_path: Path) -> None:
    source_a = write_csv(tmp_path / "a.csv", [["Country", "ID", "Name"], ["US", "001", "Ada"]], delimiter=";")
    source_b = write_csv(tmp_path / "b.csv", [["Nation", "Code", "Name"], ["US", "001", "Ada"]], delimiter=";")
    config = tmp_path / "compare.json"
    config.write_text(
        json.dumps(
            {
                "source_type": "csv",
                "source_a": "a.csv",
                "source_b": "b.csv",
                "key_a": ["Country", "ID"],
                "key_b": ["Nation", "Code"],
                "delimiter": ";",
            }
        ),
        encoding="utf-8",
    )
    library = ReconciliationLibrary()
    result = library.compare_csv_files(config=str(config))
    assert result["passed"] is True
    assert result["details"]["matched"][0]["key"] == "US||001"
    with pytest.raises(AssertionError, match="No reconciliation result"):
        ReconciliationLibrary().get_reconciliation_summary()


def test_cli_strict_and_defer_exit_codes(tmp_path: Path) -> None:
    source_a, source_b = _pair(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Grace"]],
    )
    passing_a, passing_b = _pair(
        tmp_path / "pass",
        [["ID", "Name"], ["001", "Ada"]],
        [["ID", "Name"], ["001", "Ada"]],
    )
    passed = _run(
        ["--source-a", str(passing_a), "--source-b", str(passing_b), "--key-a", "ID", "--key-b", "ID"]
    )
    failed = _run(
        ["--source-a", str(source_a), "--source-b", str(source_b), "--key-a", "ID", "--key-b", "ID"]
    )
    deferred = _run(
        [
            "--exit-code-mode",
            "defer",
            "--source-a",
            str(source_a),
            "--source-b",
            str(source_b),
            "--key-a",
            "ID",
            "--key-b",
            "ID",
            "--result-file",
            str(tmp_path / "metrics.txt"),
        ]
    )
    assert passed.returncode == 0
    assert json.loads(passed.stdout)["passed"] is True
    assert "INFO" not in passed.stdout
    assert failed.returncode == 2
    assert json.loads(failed.stdout)["passed"] is False
    assert deferred.returncode == 0
    assert json.loads(deferred.stdout)["exceptions"] == 1
    metrics = (tmp_path / "metrics.txt").read_text(encoding="utf-8")
    assert "status=completed" in metrics
    assert "passed=false" in metrics
    assert "exceptions=1" in metrics


def test_cli_technical_failure_and_result_file(tmp_path: Path) -> None:
    result_file = tmp_path / "nested" / "result.txt"
    completed = _run(
        [
            "--source-a",
            str(tmp_path / "missing.xlsx"),
            "--source-b",
            str(tmp_path / "also-missing.xlsx"),
            "--key-a",
            "ID",
            "--key-b",
            "ID",
            "--result-file",
            str(result_file),
        ]
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["status"] == "technical_failure"
    assert payload["error_type"] == "DataReadError"
    assert "status=technical_failure" in result_file.read_text(encoding="utf-8")


def test_cli_config_resolves_paths_and_shim(tmp_path: Path) -> None:
    data = tmp_path / "data"
    source_a, source_b = _pair(
        data,
        [["ID", "Amount"], ["1", "10.00"]],
        [["ID", "Amount"], ["1", "10.04"]],
    )
    config = tmp_path / "config" / "job.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "source_type": "excel",
                "source_a": "../data/a.xlsx",
                "source_b": "../data/b.xlsx",
                "key_a": "ID",
                "key_b": "ID",
                "numeric_tolerance": 0.05,
            }
        ),
        encoding="utf-8",
    )
    completed = _run(["--config", str(config)], program=SHIM)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["passed"] is True
    assert source_a.is_file() and source_b.is_file()


def test_cli_composite_keys(tmp_path: Path) -> None:
    source_a, source_b = _pair(
        tmp_path,
        [["Country", "ID", "Name"], ["US", "001", "Ada"]],
        [["Nation", "Code", "Name"], ["US", "001", "Ada"]],
    )
    completed = _run(
        [
            "--source-a",
            str(source_a),
            "--source-b",
            str(source_b),
            "--key-a",
            "Country",
            "--key-a",
            "ID",
            "--key-b",
            "Nation",
            "--key-b",
            "Code",
        ]
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["details"]["matched"][0]["key"] == "US||001"


def test_powershell_wrapper_returns_business_and_technical_codes(tmp_path: Path) -> None:
    source_a, source_b = _pair(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Grace"]],
    )
    config = tmp_path / "job.json"
    config.write_text(
        json.dumps(
            {
                "source_type": "excel",
                "source_a": str(source_a),
                "source_b": str(source_b),
                "key_a": "ID",
                "key_b": "ID",
            }
        ),
        encoding="utf-8",
    )
    strict = _powershell(["-Python", sys.executable, "-Config", str(config), "-ExitCodeMode", "strict"])
    deferred = _powershell(["-Python", sys.executable, "-Config", str(config), "-ExitCodeMode", "defer"])
    assert strict.returncode == 2, strict.stderr
    assert json.loads(strict.stdout)["passed"] is False
    assert deferred.returncode == 0, deferred.stderr
    script = POWERSHELL.read_text(encoding="utf-8")
    assert "Invoke-Expression" not in script
    assert "& $Python @arguments" in script


def test_playwright_client_handles_results_and_failures(tmp_path: Path) -> None:
    match_a, match_b = _pair(
        tmp_path / "match",
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Ada"]],
    )
    mismatch_a, mismatch_b = _pair(
        tmp_path / "mismatch",
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Grace"]],
    )
    csv_a = write_csv(tmp_path / "a.csv", [["ID", "Name"], ["001", "Ada"]], delimiter=";")
    csv_b = write_csv(tmp_path / "b.csv", [["ID", "Name"], ["001", "Ada"]], delimiter=";")
    bad_json = tmp_path / "bad-json.sh"
    sleeper = tmp_path / "sleep.sh"
    bad_json.write_text("#!/bin/sh\nprintf 'not-json\\n'\n", encoding="utf-8")
    sleeper.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    bad_json.chmod(0o755)
    sleeper.chmod(0o755)
    client = (ROOT / "adapters" / "playwright" / "reconciliation-client.ts").read_text(encoding="utf-8")
    assert "execFile" in client
    assert "shell: true" not in client
    assert "shell:true" not in client
    completed = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            str(CLIENT_CHECK),
            "--python",
            sys.executable,
            "--match-a",
            str(match_a),
            "--match-b",
            str(match_b),
            "--mismatch-a",
            str(mismatch_a),
            "--mismatch-b",
            str(mismatch_b),
            "--csv-a",
            str(csv_a),
            "--csv-b",
            str(csv_b),
            "--missing-python",
            str(tmp_path / "missing-python"),
            "--bad-json-python",
            str(bad_json),
            "--sleep-python",
            str(sleeper),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_robot_example_runs() -> None:
    robot = Path(sys.executable).with_name("robot")
    if not robot.exists():
        pytest.skip("robotframework is not installed")
    output = ROOT / ".tmp" / "robot-example"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(output),
            "--variable",
            f"PYTHON:{sys.executable}",
            str(ROOT / "examples" / "robot_example.robot"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _powershell(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-File", str(POWERSHELL), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
