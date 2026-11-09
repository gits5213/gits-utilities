# Tosca Commander execution

This repository does not contain a Tosca module, and the lab does not click through Tosca Commander. Run the steps below in the Tosca installation that will call the package. Use the process-execution module that installation already has approved. Do not add a module from this document.

The package under test is the installed distribution, not a checkout of this folder. Production version 0.1.0 is on PyPI. On the Tosca host:

```text
python -m pip install "universal-qa-utils==0.1.0"
```

To validate a locally built wheel instead, install that file. Release candidate 0.2.0 is not on PyPI:

```text
python -m pip install C:\qa-utils\dist\universal_qa_utils-<version>-py3-none-any.whl
```

The Windows plan for 0.2.0 is [tosca-windows-validation.md](tosca-windows-validation.md). That plan has not been executed.

Generate the shared fixture on a machine that has this repository, then copy that directory to the Tosca host:

```text
python -m integration_lab.reconciliation_fixture C:\qa-utils\ledger
```

The directory contains `ledger_a.xlsx`, `ledger_b.xlsx`, `reconciliation.json`, and `expected.json`. `reconciliation.json` is the only file the CLI reads. Its workbook paths are relative to that directory.

## Command

Technical success and business failure are different. Use `defer` when Tosca must read the result before it decides the business outcome. `strict` returns 2 for this fixture, and a process module that treats every non-zero code as a crash will stop before the business assertion.

PowerShell:

```powershell
pwsh -NoProfile -File C:\qa-utils\repo\adapters\tosca\run_reconciliation.ps1 `
  -Python C:\qa-utils\venv\Scripts\python.exe `
  -Config C:\qa-utils\ledger\reconciliation.json `
  -ResultFile C:\qa-utils\evidence\metrics.txt `
  -ExitCodeMode defer
```

Command Prompt, for the same installed console script:

```text
C:\qa-utils\venv\Scripts\qa-utils.exe --config C:\qa-utils\ledger\reconciliation.json --result-file C:\qa-utils\evidence\metrics.txt --exit-code-mode defer
```

`-Python` must be the interpreter where the wheel is installed. The script calls `python -m universal_utils.cli` with an argument array. It does not build a shell command.

## Results this fixture must produce

| Check | defer | strict | Missing workbook |
| --- | --- | --- | --- |
| Process exit code | 0 | 2 | 1 |
| Technical outcome | success | success | failure |
| Business outcome | fail | fail | not run |
| `metrics.txt` first lines | `status=completed` then `passed=false` | same | `status=technical_failure` |

Counts in both the JSON on stdout and `metrics.txt`:

```text
passed=false
total_records=12
matched=1
mismatched=1
missing_in_a=1
missing_in_b=1
duplicates=2
unmapped=1
invalid_keys=1
exceptions=7
```

Stdout of a completed run is one JSON object with those metrics. A technical failure is a different JSON object: `status`, `error_type`, and `message`. `error_type` for a missing workbook is `DataReadError`.

## What to record in Tosca

1. Point the approved process module at `pwsh` or `qa-utils.exe` with the arguments above. Set the working directory only if that module requires one. The config file resolves its own relative paths.
2. For the defer case, assert the process return code is 0, then read `metrics.txt` with the file or buffer module already in that workspace. Assert the counts above. This case is a passed Tosca test case about a failed reconciliation.
3. Repeat with `-ExitCodeMode strict`. Assert the return code is 2 and the counts are unchanged.
4. Point `--config` at a JSON file whose workbooks are missing. Assert the return code is 1 and `status=technical_failure`. Do not assert `passed`.
5. Attach the Tosca execution log, the stdout JSON, and `metrics.txt` to the run. Until those artifacts come from Tosca Commander, Tosca verification is not complete. Version 0.1.0 was published with this limitation still pending.
