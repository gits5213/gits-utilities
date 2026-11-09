"""Playwright client integration against the shared ledger fixture.

The Playwright test process exits 0. The reconciliation inside it is a
business failure, and a missing workbook rejects as a technical failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

from integration_lab.lab_evidence import save_process_evidence
from integration_lab.reconciliation_fixture import materialize

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT = REPO_ROOT / "node_modules" / ".bin" / "playwright"
CONFIG = Path(__file__).resolve().parent / "playwright.config.ts"


def test_playwright_ledger_separates_business_and_technical_results(tmp_path: Path) -> None:
    if not PLAYWRIGHT.is_file():
        raise AssertionError("Playwright is not installed. Run npm install in universal-qa-utils.")
    fixture = materialize(tmp_path / "fixture")
    report = tmp_path / "playwright-report.json"
    completed = subprocess.run(
        [str(PLAYWRIGHT), "test", "--config", str(CONFIG)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "LEDGER_DIR": str(fixture.directory),
            "LEDGER_PLAYWRIGHT_REPORT": str(report),
            "PYTHON": sys.executable,
        },
    )
    evidence = save_process_evidence(
        "playwright",
        "ledger",
        completed,
        technical_status="success",
        business_status="fail",
        extra_files={
            "playwright-report.json": report,
            "ledger_report.xlsx": fixture.report,
        },
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout
    assert fixture.report.is_file()
    assert _sheet_names(fixture.report) == [
        "Summary",
        "Detailed Comparison",
        "Exceptions Only",
        "Execution Metadata",
    ]
    assert (evidence / "playwright-report.json").is_file()


def _sheet_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()
