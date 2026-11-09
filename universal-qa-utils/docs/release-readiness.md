# Release readiness — universal-qa-utils 0.1.0

Recommendation: **CONDITIONALLY READY**. Local package, license, build, clean-install, and regression gates pass. Do not upload to PyPI, push, or tag until Windows Tosca Commander is validated.

Copyright holder: Global iTech Solutions Inc. Copyright year: 2026. License: MIT.

Nothing was uploaded, tagged, or committed.

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| MIT `LICENSE` | PASS | Standard MIT text. Notice: `Copyright (c) 2026 Global iTech Solutions Inc.` |
| `pyproject.toml` license | PASS | PEP 639 `license = "MIT"` and `license-files = ["LICENSE"]`. Build backend `setuptools>=77` (build used setuptools 84.2.1) |
| Wheel and sdist metadata | PASS | `License-Expression: MIT`, `Version: 0.1.0`, `Requires-Python: >=3.11`. Sdist `License-File: LICENSE` |
| `python -m build` | PASS | exit 0, from `.release-venv` after `dist/` was removed |
| `twine check dist/*` | PASS | both artifacts `PASSED`, exit 0 |
| `pip check` | PASS | release and clean environments: `No broken requirements found.` |
| Clean Python >= 3.11 | PASS | `.clean-install-venv` Python 3.11.0 |
| Wheel install | PASS | force-reinstall exit 0; installed version `0.1.0` |
| Imports from site-packages | PASS | from `/tmp` with `python -P`: both `universal_utils` and `universal_utils.robot.ReconciliationLibrary` resolve under `.clean-install-venv/.../site-packages` |
| `qa-utils --help` | PASS | exit 0 |
| CAM/MDG CLI | PASS | strict exit 0; `passed=true`, `matched=2`, `mismatched=0`, `exceptions=0`; `examples/demo-output/cam_mdg_report.xlsx` exists |
| Robot example | PASS | `2 tests, 2 passed, 0 failed`; exit 0. This example is also exercised by one test inside the 66 and is not an extra count |
| Playwright TypeScript | PASS | example 1 passed, exit 0; ledger spec 2 passed, exit 0. Together 3. The ledger spec is also inside the regression suite |
| Tosca PowerShell process | PASS | `integration_lab/test_tosca_process.py` 2 passed, exit 0. These 2 are part of the 66, not additional tests |
| Full regression | PASS | `./.release-venv/bin/python -P -m pytest tests/ integration_lab/ -q` exit 0; 66 passed; no skips |
| Third-party obligations | PASS | see below. Nothing was vendored |
| Windows Tosca Commander | PENDING | **PENDING — Not validated in an actual Windows Tosca Commander environment.** |

## Artifacts

Rebuilt after the license metadata change. Previous checksums were not reused.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `dist/universal_qa_utils-0.1.0-py3-none-any.whl` | 35400 | `91be0744577221fd1fbc2384d0d54da8320921aa6217e63a91340f1b48df62a2` |
| `dist/universal_qa_utils-0.1.0.tar.gz` | 43844 | `c3d37c57e5ffd4a0a1446de2a4983de271f0d74f7931ff1454322aed21f57e5d` |

The wheel contains `universal_utils`, including `universal_utils/robot/ReconciliationLibrary.py`, `universal_qa_utils-0.1.0.dist-info/licenses/LICENSE`, and both console scripts:

```text
qa-utils = universal_utils.cli:main
universal-qa-utils = universal_utils.cli:main
```

The wheel does not contain Playwright, Tosca, `adapters/`, virtual environments, `node_modules/`, or test evidence. The sdist contains `LICENSE`, `README.md`, `pyproject.toml`, `universal_utils` (including the Robot library), and the unit tests. It does not contain adapters, virtual environments, or evidence.

Version `0.1.0` is unchanged in `pyproject.toml` and `LIBRARY_VERSION`.

## Dependencies

Installed metadata in `.release-venv`:

| Package | Version | License metadata | Role |
| --- | --- | --- | --- |
| pandas | 3.1.1 | `License-Expression: BSD-3-Clause` | runtime |
| openpyxl | 3.1.5 | `License-Expression: MIT` | runtime |
| numpy | 2.4.6 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` | pandas dependency |
| python-dateutil | 4.0.0 | `BSD-3-Clause` | pandas dependency |
| tzdata | 2026.6 | `Apache-2.0` | pandas dependency |
| et-xmlfile | 2.0.0 | `MIT` | openpyxl dependency |
| robotframework | 7.5.1 | `Apache License 2.0` | optional `robot` extra |
| pytest | 9.2.0 | `MIT` | development only |
| `@playwright/test` | 1.65.0 | `Apache-2.0` in `package.json` | repository dev dependency; not in the wheel |

These licenses are compatible with distributing this project under MIT. Third-party license texts were not copied into the repository.

## Git staging

`LICENSE`, `README.md`, `pyproject.toml`, and this file are staged with the rest of the initial package. `dist/`, `build/`, virtual environments, `.tmp/`, `node_modules/`, demo output, and test evidence stay untracked. No commit was created.

## Remaining blocker

Windows Tosca Commander execution is **PENDING — Not validated in an actual Windows Tosca Commander environment.** The passing PowerShell process tests are not Tosca Commander validation. Run the defer, strict, and missing-workbook commands from `docs/tosca-execution.md` in that environment and attach the execution log before publishing.
