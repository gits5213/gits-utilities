"""Robot Framework integration against the shared ledger fixture.

Compare Excel Files returns the business failure and the suite exits 0.
Verify Reconciliation Passed is a separate suite and exits 1. A missing
workbook fails the keyword as a technical error.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

from integration_lab.lab_evidence import save_process_evidence
from integration_lab.reconciliation_fixture import DETAIL_KEYS, RESULT_KEYS, expected_document, materialize

REPO_ROOT = Path(__file__).resolve().parents[1]
LIBRARY = REPO_ROOT / "adapters" / "robot" / "ReconciliationLibrary.py"


def test_robot_counts_business_failure_without_failing_the_suite(tmp_path: Path) -> None:
    fixture = materialize(tmp_path / "fixture")
    missing_a = tmp_path / "missing_a.xlsx"
    missing_b = tmp_path / "missing_b.xlsx"
    suite = tmp_path / "ledger.robot"
    suite.write_text(_counts_suite(expected_document()), encoding="utf-8")
    output = tmp_path / "robot-counts"
    completed = _robot(suite, output, fixture.config, missing_a, missing_b)
    evidence = save_process_evidence(
        "robot",
        "counts",
        completed,
        technical_status="success",
        business_status="fail",
        extra_files={"ledger_report.xlsx": fixture.report, "output.xml": output / "output.xml"},
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert fixture.report.is_file()
    assert _sheet_names(fixture.report) == [
        "Summary",
        "Detailed Comparison",
        "Exceptions Only",
        "Execution Metadata",
    ]
    assert (evidence / "output.xml").is_file()


def test_robot_verify_keyword_fails_the_suite_on_business_exceptions(tmp_path: Path) -> None:
    fixture = materialize(tmp_path / "fixture")
    suite = tmp_path / "verify.robot"
    suite.write_text(
        "\n".join(
            [
                "*** Settings ***",
                "Library    ${LIBRARY}",
                "",
                "*** Test Cases ***",
                "Verify Keyword Rejects The Ledger",
                "    Compare Excel Files    config=${CONFIG}",
                "    Verify Reconciliation Passed",
                "",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "robot-verify"
    completed = _robot(suite, output, fixture.config, tmp_path / "missing_a.xlsx", tmp_path / "missing_b.xlsx")
    save_process_evidence(
        "robot",
        "verify",
        completed,
        technical_status="success",
        business_status="fail",
        extra_files={"output.xml": output / "output.xml"},
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "exceptions=7" in completed.stdout


def test_robot_technical_failure_is_a_keyword_error(tmp_path: Path) -> None:
    """The suite exits 0 because it expects the keyword to raise DataReadError."""
    fixture = materialize(tmp_path / "fixture")
    suite = tmp_path / "technical.robot"
    suite.write_text(
        "\n".join(
            [
                "*** Settings ***",
                "Library    ${LIBRARY}",
                "",
                "*** Test Cases ***",
                "Missing Workbook Is Technical",
                "    Run Keyword And Expect Error    *DataReadError*",
                "    ...    Compare Excel Files    ${MISSING_A}    ${MISSING_B}",
                "    ...    key_a=Account    key_b=${KEY_B}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "robot-technical"
    completed = _robot(
        suite,
        output,
        fixture.config,
        tmp_path / "missing_a.xlsx",
        tmp_path / "missing_b.xlsx",
    )
    save_process_evidence(
        "robot",
        "technical",
        completed,
        technical_status="success",
        business_status="not_run",
        extra_files={"output.xml": output / "output.xml"},
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "DataReadError" in (output / "output.xml").read_text(encoding="utf-8")


def _robot(
    suite: Path,
    output: Path,
    config: Path,
    missing_a: Path,
    missing_b: Path,
) -> subprocess.CompletedProcess[str]:
    if not LIBRARY.is_file():
        raise AssertionError(f"Robot library is missing: {LIBRARY}")
    return subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "robot",
            "--outputdir",
            str(output),
            "--variable",
            f"LIBRARY:{LIBRARY}",
            "--variable",
            f"CONFIG:{config}",
            "--variable",
            f"MISSING_A:{missing_a}",
            "--variable",
            f"MISSING_B:{missing_b}",
            "--variable",
            "KEY_B:Account ID",
            str(suite),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=suite.parent,
    )


def _counts_suite(expected: dict[str, object]) -> str:
    metrics = expected["metrics"]
    assert isinstance(metrics, dict)
    keys = expected["keys"]
    assert isinstance(keys, dict)
    issues = expected["field_issues"]
    assert isinstance(issues, list)
    lines = [
        "*** Settings ***",
        "Library    ${LIBRARY}",
        "Library    Collections",
        "Library    OperatingSystem",
        "",
        "*** Test Cases ***",
        "Ledger Counts Match The Shared Contract",
        "    ${result}=    Compare Excel Files    config=${CONFIG}",
        "    Should Be Equal    ${result}[passed]    ${FALSE}",
        "    @{top}=    Get Dictionary Keys    ${result}",
        "    Sort List    ${top}",
        "    @{expected_top}=    Create List    " + "    ".join(RESULT_KEYS),
        "    Lists Should Be Equal    ${top}    ${expected_top}",
        "    @{detail_names}=    Get Dictionary Keys    ${result}[details]",
        "    Sort List    ${detail_names}",
        "    @{expected_details}=    Create List    " + "    ".join(DETAIL_KEYS),
        "    Lists Should Be Equal    ${detail_names}    ${expected_details}",
    ]
    for name, value in metrics.items():
        if name == "passed":
            continue
        lines.append(f"    Should Be Equal As Integers    ${{result}}[{name}]    {value}")
    for category, values in keys.items():
        assert isinstance(values, list)
        lines.append(f"    ${{rows}}=    Set Variable    ${{result}}[details][{category}]")
        lines.append(f"    Length Should Be    ${{rows}}    {len(values)}")
        for index, key in enumerate(values):
            rendered = "${EMPTY}" if key == "" else str(key)
            lines.append(f"    Should Be Equal    ${{rows}}[{index}][key]    {rendered}")
    lines.append("    ${issues}=    Set Variable    ${result}[details][field_issues]")
    lines.append(f"    Length Should Be    ${{issues}}    {len(issues)}")
    for index, issue in enumerate(issues):
        assert isinstance(issue, dict)
        for field in ("key", "field_a", "reason", "value_a", "value_b"):
            lines.append(
                f"    Should Be Equal    ${{issues}}[{index}][{field}]    {issue[field]}"
            )
    lines.extend(
        [
            f"    Should Be Equal    ${{result}}[metadata][schema_version]    {expected['schema_version']}",
            f"    Should Be Equal    ${{result}}[metadata][library_version]    {expected['library_version']}",
            "    Should Be Equal    ${result}[metadata][numeric_tolerance]    0.01",
            "    File Should Exist    ${result}[report_path]",
            "    Run Keyword And Expect Error    Reconciliation did not pass.*",
            "    ...    Verify Reconciliation Passed    ${result}",
            "Missing Workbook Is Technical",
            "    Run Keyword And Expect Error    *DataReadError*",
            "    ...    Compare Excel Files    ${MISSING_A}    ${MISSING_B}",
            "    ...    key_a=Account    key_b=${KEY_B}",
            "",
        ]
    )
    return "\n".join(lines)


def _sheet_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()
