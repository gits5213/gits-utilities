# Windows Tosca Commander validation plan — 0.2.0

Status: **PENDING**. This document is a plan. It is not evidence that Tosca Commander has run.

No result in this repository was produced by Windows Tosca Commander. A passing PowerShell wrapper test, on macOS or in CI, is a process-boundary check only. Do not record Tosca validation as passed until the evidence list at the end comes from the Tosca host.

The command contract is [tosca-execution.md](tosca-execution.md). This plan adds the host prerequisites and the evidence required for release candidate 0.2.0. Windows Tosca Commander execution remains pending.

## Prerequisites

| Item | Requirement |
| --- | --- |
| Operating system | Windows version approved by the Tosca installation |
| Tosca | Tricentis Tosca Commander, On-Premises, with an approved process-execution module |
| PowerShell | PowerShell 7 (`pwsh`), if the approved module calls the repository script |
| Python | 3.11 or newer, 64-bit, installed for the account that Tosca uses |
| Network | Access to PyPI for the production install, or a copied wheel if the host cannot reach PyPI |
| Repository checkout | Required only to copy `adapters/tosca/run_reconciliation.ps1` and to generate the fixture. The comparison runs from the installed package |

Create a virtual environment owned by the Tosca runtime account:

```text
py -3.11 -m venv C:\qa-utils\venv
C:\qa-utils\venv\Scripts\python.exe -m pip install --upgrade pip
```

Install the version under test. Production 0.1.0:

```text
C:\qa-utils\venv\Scripts\python.exe -m pip install "universal-qa-utils==0.1.0"
```

Release candidate 0.2.0, until it is published, from a wheel built on the approved commit:

```text
C:\qa-utils\venv\Scripts\python.exe -m pip install C:\qa-utils\dist\universal_qa_utils-0.2.0-py3-none-any.whl
C:\qa-utils\venv\Scripts\python.exe -m pip check
C:\qa-utils\venv\Scripts\qa-utils.exe --help
```

Confirm the imported version before opening Tosca:

```text
C:\qa-utils\venv\Scripts\python.exe -c "import universal_utils; print(universal_utils.__version__)"
```

The printed version must be the version named in the test record.

## Fixture

On a machine with this repository:

```text
python -m integration_lab.reconciliation_fixture C:\qa-utils\ledger
```

Copy the whole `ledger` directory to the Tosca host. `reconciliation.json` uses paths relative to that directory. Do not rewrite those paths unless the copy location changes, and then keep them relative to the config file.

## PowerShell invocation

The script passes an argument array to Python. It does not build a shell command.

```powershell
pwsh -NoProfile -File C:\qa-utils\repo\adapters\tosca\run_reconciliation.ps1 `
  -Python C:\qa-utils\venv\Scripts\python.exe `
  -Config C:\qa-utils\ledger\reconciliation.json `
  -ResultFile C:\qa-utils\evidence\metrics.txt `
  -ExitCodeMode defer
```

The direct console script is also valid:

```text
C:\qa-utils\venv\Scripts\qa-utils.exe --config C:\qa-utils\ledger\reconciliation.json --result-file C:\qa-utils\evidence\metrics.txt --exit-code-mode defer
```

Run both once, outside Tosca, and save the exit code, stdout, and `metrics.txt`. Those files prove the host can run the package. They do not prove the Tosca module.

## Tosca Commander setup

1. Use the process module already approved in that Tosca workspace. Do not import a module from this repository.
2. Point it at `pwsh` or at `qa-utils.exe` with the arguments above.
3. Set the working directory only when that module requires one. The config file resolves its own relative paths.
4. Store stdout and `metrics.txt` where the Tosca test case can read them.

## Cases

| Case | Mode | Exit code | Business result | Assertion |
| --- | --- | --- | --- | --- |
| Ledger, defer | `defer` | 0 | fail | Tosca reads `passed=false` and the ledger counts from `metrics.txt` |
| Ledger, strict | `strict` | 2 | fail | Tosca records exit code 2 and the same counts |
| Missing workbook | `defer` or `strict` | 1 | not run | JSON `status` is `technical_failure` and `error_type` is `DataReadError` |
| Passing pair | `strict` | 0 | pass | A small synthetic pair with no exceptions returns `passed=true` |

Ledger counts:

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

The defer case is a passed Tosca test case about a failed reconciliation. A module that treats every non-zero exit as a crash will fail the strict case before it can read the business result. That is a host configuration issue, not a reconciliation defect.

## Evidence required before calling this passed

Collect all of the following from the Tosca host:

- Tosca version and Windows version
- `python --version` and `universal_utils.__version__`
- `pip check` output
- The Tosca execution log for the defer, strict, missing-workbook, and passing cases
- stdout JSON and `metrics.txt` for each case
- The name of the approved process module

Until that set exists, the status line in the release checklist stays **PENDING**.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Exit code 1 before comparison | The config path, both workbook paths, and that the virtual environment is the one named in `-Python` |
| Exit code 9009 or a command-not-found dialog | `py` or `pwsh` is not on the account's PATH. Use absolute paths |
| Tosca reports a crash on exit code 2 | The module is in a mode that rejects business failures. Use `defer`, then assert `passed` from the result file |
| `passed=true` on the ledger fixture | The installed package or the fixture copy is not the shared ledger |
| stdout contains a log line instead of one JSON object | A different interpreter is running. Logs belong on stderr |
