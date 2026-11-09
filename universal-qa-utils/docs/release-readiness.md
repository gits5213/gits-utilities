# Release readiness — universal-qa-utils 0.1.0

**Update, 9 November 2026.** Version 0.1.0 is on production PyPI at https://pypi.org/project/universal-qa-utils/0.1.0/ and is tagged `v0.1.0` at `cd1e74cc3a07727059d60fa088f95b109a371d76`. The wheel SHA-256 remains `04c30c5fc89b0965dbcb6cf0603dc9de4814c8b3a4317951d8c9efb48eef6d90`. Windows Tosca Commander remains pending. The sections below are the historical TestPyPI verification record. Development of 0.1.1 is on `development/v0.1.1` and has not been published. Its checklist is [v0.1.1-release-checklist.md](v0.1.1-release-checklist.md).

Recommendation: **PASS** for the 0.1.0 TestPyPI verification recorded below. A fresh environment installed the published wheel after its SHA-256 matched the approved checksum. Windows Tosca Commander remains pending.

This verification did not upload another package, create a tag, or push.

Copyright holder: Global iTech Solutions Inc. Copyright year: 2026. License: MIT.

## Source

| Item | Value |
| --- | --- |
| Repository root | `/Users/mdzaman/Downloads/toGithub/gits-utilities` |
| Package directory | `universal-qa-utils/` |
| Branch | `master` |
| Package source | `ac4a3aadab63280b17267f303c069113141f94df` (`docs(release): finalize v0.1.0 TestPyPI preparation`) |
| Remote | `git@github.com:gits5213/gits-utilities.git` |
| Remote `master` | `4b1d9c351ba235c7b3b39e054f8a40d3bced2f59`; local commits have not been pushed |
| Stated release commit | `36cf7948efc308fc82fb268325b494f125f60f2d` |

`36cf794` is still a local object. Its tree is identical to `80e31fb2066665a10ba30fc6a12041f1a646461e`. The README placeholder is absent from HEAD. The artifacts below were rebuilt from that committed source. Version `0.1.0` is unchanged.

## TestPyPI publication

On 9 November 2026, `https://test.pypi.org/pypi/universal-qa-utils/0.1.0/json` returned HTTP 200.

| File | Bytes | SHA-256 | Yanked |
| --- | --- | --- | --- |
| `universal_qa_utils-0.1.0-py3-none-any.whl` | 35400 | `04c30c5fc89b0965dbcb6cf0603dc9de4814c8b3a4317951d8c9efb48eef6d90` | no |
| `universal_qa_utils-0.1.0.tar.gz` | 43872 | `052a42c7ed45956eea76e3eb893354fc72cb91533b0a79df21a571bd9b7d4ee8` | no |

Metadata: name `universal-qa-utils`, version `0.1.0`, license `MIT`, requires Python `>=3.11`. Production PyPI was not checked again for publication and was not used as the package index.

## Post-upload verification

A new Python 3.11.0 virtual environment was created at `/tmp/uq-testpypi-post-010`, outside the repository. The wheel was downloaded with `--index-url https://test.pypi.org/simple/ --no-deps`. Its SHA-256 matched `04c30c5fc89b0965dbcb6cf0603dc9de4814c8b3a4317951d8c9efb48eef6d90`, so installation continued. pandas and openpyxl were resolved from PyPI by installing that local file.

| Check | Result |
| --- | --- |
| `pip check` after install | PASS, exit 0 |
| Installed version and location | `0.1.0` from `/tmp/uq-testpypi-post-010/lib/python3.11/site-packages` |
| `qa-utils --help` | PASS, exit 0 |
| CAM/MDG strict | PASS, exit 0; `passed=true`, `matched=2`, `mismatched=0`, `exceptions=0`; report file exists |
| Ledger strict business failure | PASS, exit 2, `passed=false` |
| Ledger defer | PASS, exit 0, `passed=false` |
| Missing workbook | PASS, exit 1, `status=technical_failure`, `DataReadError` |
| Robot extra and `robot.libdoc` | PASS. Keywords: Compare Csv Files, Compare Excel Files, Get Reconciliation Summary, Verify Reconciliation Passed |
| `examples/robot_example.robot` | PASS, `2 tests, 2 passed, 0 failed`, exit 0 |
| Windows Tosca Commander | PENDING |

## Earlier name check

Read-only checks on 8 November 2026, and again on 9 November 2026 before publication, returned HTTP 404. Those results are historical.

| Endpoint | Result |
| --- | --- |
| `https://test.pypi.org/pypi/universal-qa-utils/json` | HTTP 404, `{"message": "Not Found"}` |
| `https://test.pypi.org/simple/universal-qa-utils/` | HTTP 404 |
| `https://pypi.org/pypi/universal-qa-utils/json` | HTTP 404, `{"message": "Not Found"}` |
| `https://pypi.org/simple/universal-qa-utils/` | HTTP 404 |
| `https://test.pypi.org/project/universal-qa-utils/` | HTTP 200, HTML title `Client Challenge`. The body does not contain the project name |
| `https://pypi.org/project/universal-qa-utils/` | HTTP 200, same challenge page |

Version `0.1.0` is now published on TestPyPI. It was not published on production PyPI by this verification.

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| MIT `LICENSE` | PASS | `Copyright (c) 2026 Global iTech Solutions Inc.` |
| `pyproject.toml` | PASS | setuptools `>=77` build backend, `license = "MIT"`, `license-files = ["LICENSE"]`, `requires-python = ">=3.11"` |
| Version consistency | PASS | `0.1.0` in `pyproject.toml` and `LIBRARY_VERSION` |
| `python -m build` | PASS | exit 0 from `.release-venv`. Isolated build used setuptools 84.2.1 and wheel 0.48.0. The wheel was built from the sdist |
| `twine check dist/*` | PASS | both artifacts `PASSED`, exit 0 |
| Clean Python 3.11 | PASS | recreated `.clean-install-venv`, Python 3.11.0 |
| Wheel install and `pip check` | PASS | both exit 0. Installed version `0.1.0` |
| Imports from site-packages | PASS | from `/tmp` with `python -P` |
| `qa-utils --help` | PASS | exit 0 |
| CAM/MDG CLI | PASS | strict exit 0; `passed=true`, `matched=2`, `mismatched=0`, `exceptions=0`; report file exists |
| Business and technical exits | PASS | ledger strict exit 2; defer exit 0 with `passed=false`; missing workbook exit 1, `status=technical_failure` |
| Robot extra | PASS | `.[robot]` install exit 0, `pip check` exit 0, `robot.libdoc` lists four keywords |
| Robot example | PASS | `2 tests, 2 passed, 0 failed`, exit 0. Also covered by `tests/test_adapters.py::test_robot_example_runs` inside the 66 |
| Playwright TypeScript | PASS | example 1 passed, exit 0. Ledger spec 2 passed inside `integration_lab/test_playwright.py`. Together 3. Node printed a `NO_COLOR`/`FORCE_COLOR` warning |
| Tosca PowerShell process | PASS | `integration_lab/test_tosca_process.py` 2 passed inside the 66. This is not Windows Tosca Commander |
| Long description | PASS | `readme-renderer` with comrak rendered README and wheel METADATA to 23072 characters of HTML. The placeholder is absent. `twine check` exit 0. Twine 7 does not itself render `text/markdown` |
| Clean reinstall | PASS | `--force-reinstall` of the corrected wheel, exit 0. `pip check` exit 0. Imports resolve from `.clean-install-venv` site-packages. `qa-utils --help` exit 0. CAM/MDG strict exit 0: `passed=true`, `matched=2`, `mismatched=0`, `exceptions=0` |
| Full regression | PASS | Rerun after the README correction: `./.release-venv/bin/python -P -m pytest tests/ integration_lab/ -q`, 66 passed, exit 0, no skips or failures |
| Windows Tosca Commander | PENDING | **PENDING — Not validated in an actual Windows Tosca Commander environment.** |

## Artifacts

Rebuilt from `ac4a3aa` on 9 November 2026 with `.release-venv` `python -m build`. The previous artifacts were moved to `.tmp/dist-before-ac4a3aa/` and were not reused. `twine check` passed for both files.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `dist/universal_qa_utils-0.1.0-py3-none-any.whl` | 35400 | `04c30c5fc89b0965dbcb6cf0603dc9de4814c8b3a4317951d8c9efb48eef6d90` |
| `dist/universal_qa_utils-0.1.0.tar.gz` | 43872 | `052a42c7ed45956eea76e3eb893354fc72cb91533b0a79df21a571bd9b7d4ee8` |

Wheel metadata: `Name: universal-qa-utils`, `Version: 0.1.0`, `License-Expression: MIT`, `License-File: LICENSE`, `Requires-Python: >=3.11`, `Description-Content-Type: text/markdown`. Normalized name: `universal-qa-utils`. Filename form: `universal_qa_utils`.

Required: `pandas>=2.2.2`, `openpyxl>=3.1.5`. Extras: `robot` (`robotframework>=7.0`) and `dev` (`pytest`, `robotframework`, `build`). Console scripts:

```text
qa-utils = universal_utils.cli:main
universal-qa-utils = universal_utils.cli:main
```

The wheel contains `universal_utils`, including `universal_utils/robot/ReconciliationLibrary.py`, and `universal_qa_utils-0.1.0.dist-info/licenses/LICENSE`. It does not contain Playwright, Tosca, `adapters/`, virtual environments, `node_modules/`, tests, or generated evidence. No local home-directory paths or credentials were found. Strings such as `SECRET-CELL` appear only as synthetic test data in the sdist, not in the wheel.

The sdist contains `LICENSE`, `README.md`, `pyproject.toml`, `universal_utils`, and four `tests/test_*.py` modules. It does not contain `tests/conftest.py`, `tests/__init__.py`, or `tests/playwright_client_check.ts`, so the copy of the tests inside the sdist is not a complete checkout. The sdist did build the wheel.

`README.md` states that the Playwright client and the Tosca PowerShell script stay in the repository and are not files inside the wheel. The placeholder is absent from `README.md`, wheel `METADATA`, and the sdist `README.md` and `PKG-INFO`. The description ends with the Robot library sentence.

## Dependency installation after a future upload

TestPyPI does not host pandas or openpyxl. Do not use TestPyPI as the only index.

Combining `--index-url https://test.pypi.org/simple/` with `--extra-index-url https://pypi.org/simple/` merges both indexes. Pip can then select a higher version of a dependency name from TestPyPI, including a package someone else published under a trusted name such as `pandas`. That is a dependency-confusion risk.

Safer post-upload install in a fresh environment. Compare the downloaded wheel hash with the table above before installing it:

```bash
python3 -m venv /tmp/uq-testpypi-verify
/tmp/uq-testpypi-verify/bin/python -m pip install --upgrade pip
/tmp/uq-testpypi-verify/bin/python -m pip download universal-qa-utils==0.1.0 \
  --index-url https://test.pypi.org/simple/ \
  --no-deps \
  -d /tmp/uq-testpypi-dl
shasum -a 256 /tmp/uq-testpypi-dl/universal_qa_utils-0.1.0-py3-none-any.whl
/tmp/uq-testpypi-verify/bin/python -m pip install /tmp/uq-testpypi-dl/universal_qa_utils-0.1.0-py3-none-any.whl
/tmp/uq-testpypi-verify/bin/python -m pip check
cd /tmp
/tmp/uq-testpypi-verify/bin/python -P -c "import inspect, universal_utils; print(universal_utils.__version__); print(inspect.getfile(universal_utils))"
/tmp/uq-testpypi-verify/bin/qa-utils --help
```

The download uses TestPyPI only for this project. The local wheel install resolves pandas and openpyxl from PyPI. Do not install an unverified third-party upload that happens to use this name.

## Upload authentication

Trusted Publishing is not configured. The repository has no GitHub Actions workflow and no committed `.pypirc`.

For an approved manual upload, create the token in the TestPyPI account UI. The first upload of a new project needs an account-scoped token. After the project exists, replace it with a project-scoped token. Twine 7.0.0 is installed in `.release-venv`. Run the command below and let Twine prompt. At the prompt, the username is `__token__` and the password is the token typed into the hidden prompt. Do not pass the token with `-p`, an environment assignment in the shell command, a repository file, or shell history. Do not disable TLS verification.

**DO NOT EXECUTE — REQUIRES APPROVAL**

```bash
./.release-venv/bin/python -m twine upload \
  --repository-url https://test.pypi.org/legacy/ \
  dist/universal_qa_utils-0.1.0-py3-none-any.whl \
  dist/universal_qa_utils-0.1.0.tar.gz
```

## Known limitations

- Windows Tosca Commander execution is **PENDING — Not validated in an actual Windows Tosca Commander environment.** The passing PowerShell process tests are not Tosca Commander validation. Run the defer, strict, and missing-workbook commands from `docs/tosca-execution.md` in that environment before treating the Tosca adapter as released.
- The sdist test directory is incomplete, as listed above.
- Playwright and Tosca are repository adapters. `pip install universal-qa-utils` does not install them. Robot Framework is optional and is installed with the `robot` extra; the library module itself is already in the wheel.
