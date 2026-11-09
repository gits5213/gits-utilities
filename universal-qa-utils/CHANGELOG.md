# Changelog

All notable changes to `universal-qa-utils` are recorded here. The package version and `LIBRARY_VERSION` move together. Reconciliation behavior, the command-line contract, and the Robot Framework keywords are unchanged unless a release says otherwise.

## 0.2.0 — unreleased

openpyxl-based workbook comparison, implemented on `feature/excel-compare-0.2.0`. The package version in this working tree remains `0.1.1` so the in-progress maintenance metadata is unchanged. This feature has not been published.

### Added

- `compare_workbooks` compares one reference workbook with one or more targets by worksheet and cell address.
- `qa-excel-compare` provides that comparison without changing `qa-utils`.
- `ExcelCompareLibrary` adds Compare Excel Workbooks, Get Excel Compare Summary, and Verify Excel Compare Passed.
- Formula text, formatting fingerprints, worksheet selection, image byte hashes, and a difference limit are optional.
- Results state that formula calculation, charts, shapes, and password decryption are not performed.

## 0.1.1 — unreleased

Maintenance release prepared on `development/v0.1.1`. It has not been published to PyPI and has no Git tag.

### Added

- Project URLs for the GitHub repository, issue tracker, and in-repository documentation.
- Contract tests for empty files, CSV encoding, value whitespace, an inclusive numeric-tolerance boundary, composite-key identity, sheet indexes, and CLI encoding.
- A GitHub Actions workflow that runs tests and packaging checks. It does not publish.
- A Windows Tosca Commander validation plan. Execution remains pending.
- A release checklist for 0.1.1.

### Fixed

- An Excel file that is not a workbook now raises `DataReadError`, including a zero-byte file. Callers no longer see `zipfile.BadZipFile` from that path.

### Changed

- Installation instructions now identify 0.1.0 as the production release on PyPI.
- The 0.1.0 readiness note records the production publication and the `v0.1.0` tag without changing that tag.

## 0.1.0 — 2026-11-09

Initial production release.

- Compare Excel files, CSV files, and pandas DataFrames with configurable keys, field mappings, value mappings, and comparison rules.
- Provide the `qa-utils` and `universal-qa-utils` commands.
- Ship the Robot Framework library in the wheel. Robot Framework itself is an optional extra.
- Keep the Playwright client and the Tosca PowerShell script in the repository. They are not wheel files.
- Publish https://pypi.org/project/universal-qa-utils/0.1.0/ from commit `cd1e74cc3a07727059d60fa088f95b109a371d76`, tag `v0.1.0`.
- Windows Tosca Commander execution was not part of this release.
