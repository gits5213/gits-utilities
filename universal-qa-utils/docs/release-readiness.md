# Release readiness — universal-qa-utils 0.1.0

Recommendation: **READY FOR TESTPYPI UPLOAD APPROVAL**. The corrected wheel and sdist pass build, long-description, clean-install, and regression checks. Windows Tosca Commander remains pending. Do not upload until that approval is given.

This preparation run did not upload to TestPyPI or PyPI, and it did not create a commit, tag, or push.

Copyright holder: Global iTech Solutions Inc. Copyright year: 2026. License: MIT.

## Source

| Item | Value |
| --- | --- |
| Repository root | `/Users/mdzaman/Downloads/toGithub/gits-utilities` |
| Package directory | `universal-qa-utils/` |
| Branch | `master` |
| HEAD | `4b1d9c351ba235c7b3b39e054f8a40d3bced2f59` (`update`) |
| Remote | `git@github.com:gits5213/gits-utilities.git` |
| Remote `master` | same commit as HEAD, read with `git ls-remote` |
| Stated release commit | `36cf7948efc308fc82fb268325b494f125f60f2d` |

`36cf794` is still a local object. Its tree is identical to `80e31fb2066665a10ba30fc6a12041f1a646461e` (`chore(release): prepare universal-qa-utils v0.1.0`). HEAD adds one unintended README placeholder. That placeholder is removed in the working tree, and the artifacts below were rebuilt from the corrected README. Version `0.1.0` is unchanged.

## TestPyPI and PyPI name check

Read-only checks on 8 November 2026. No account was created and nothing was uploaded.

| Endpoint | Result |
| --- | --- |
| `https://test.pypi.org/pypi/universal-qa-utils/json` | HTTP 404, `{"message": "Not Found"}` |
| `https://test.pypi.org/simple/universal-qa-utils/` | HTTP 404 |
| `https://pypi.org/pypi/universal-qa-utils/json` | HTTP 404, `{"message": "Not Found"}` |
| `https://pypi.org/simple/universal-qa-utils/` | HTTP 404 |
| `https://test.pypi.org/project/universal-qa-utils/` | HTTP 200, HTML title `Client Challenge`. The body does not contain the project name |
| `https://pypi.org/project/universal-qa-utils/` | HTTP 200, same challenge page |

Version `0.1.0` is not published on either index. No current owner was returned. A 404 does not reserve the name. If an upload is later rejected because another account registered `universal-qa-utils`, a different distribution name is required. A version bump does not grant ownership of a name this project does not own.

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

The build that still contained the README placeholder was moved to `.tmp/dist-with-placeholder/` and was not reused. Those hashes were `dcd5560fb3f63e50bbbdd65784a110a49150a51e1558d345f33a706d8ec44041` and `e5f6253f4743d9b413190a72bf036b5ade00a3a65d359d14e3a44afc5ac3178f`.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `dist/universal_qa_utils-0.1.0-py3-none-any.whl` | 35400 | `b326075ad856b0d46c7f801620870fa41cd646c45fa8c23bc40477da449760b4` |
| `dist/universal_qa_utils-0.1.0.tar.gz` | 43866 | `03bc7645e2cde5b6896428ec1050a3f0e63816bca5d75e9be15812d2897eb6a9` |

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

Safer post-upload install, after the artifact hash is compared with the table above:

```bash
python -m pip download universal-qa-utils==0.1.0 \
  --index-url https://test.pypi.org/simple/ \
  --no-deps \
  -d /tmp/uq-testpypi-dl
python -m pip install /tmp/uq-testpypi-dl/universal_qa_utils-0.1.0-py3-none-any.whl
python -m pip check
qa-utils --help
```

The download uses TestPyPI only for this project. The local wheel install resolves pandas and openpyxl from PyPI. Do not install an unverified third-party upload that happens to use this name.

## Upload authentication

Preferred: TestPyPI Trusted Publishing. On `https://test.pypi.org` add a pending publisher for owner `gits5213`, repository `gits-utilities`, and a workflow that has not been created yet. A pending publisher can create the new project. A GitHub Actions workflow would need `id-token: write` and `https://test.pypi.org/legacy/`. No workflow was added.

If a later manual upload is approved, create the token in the TestPyPI account UI. The first manual upload of a new project needs an account-scoped token. After the project exists, replace it with a project-scoped token. Keep the token in the operator's keyring or a mode-`600` `~/.pypirc` outside the repository. Do not put it in a command argument, shell history, repository file, or committed `.pypirc`. Do not disable TLS verification.

**DO NOT EXECUTE — REQUIRES APPROVAL**

```bash
python -m twine upload --repository testpypi dist/*
```

## Known limitations

- Windows Tosca Commander execution is **PENDING — Not validated in an actual Windows Tosca Commander environment.** The passing PowerShell process tests are not Tosca Commander validation. Run the defer, strict, and missing-workbook commands from `docs/tosca-execution.md` in that environment before treating the Tosca adapter as released.
- The sdist test directory is incomplete, as listed above.
- Playwright and Tosca are repository adapters. `pip install universal-qa-utils` does not install them. Robot Framework is optional and is installed with the `robot` extra; the library module itself is already in the wheel.
