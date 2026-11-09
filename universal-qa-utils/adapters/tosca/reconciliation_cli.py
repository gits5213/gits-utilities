"""Thin process entry point for tools that execute a Python file.

The comparison itself lives in ``universal_utils``. This file only forwards
the process arguments. Install the package in the same interpreter:

    python reconciliation_cli.py --config examples/config/cam_mdg.json

Exit codes in the default ``strict`` mode:

- 0: the process ran and the reconciliation passed
- 2: the process ran and the reconciliation found business exceptions
- 1: the process did not finish because of a technical error

``--exit-code-mode defer`` returns 0 for both passing and failing business
results so the caller can read the JSON, or the optional key=value file,
before deciding whether the business result is acceptable. Technical errors
still return 1.

This repository does not ship a Tosca module. Before wiring this command into
Tricentis Tosca On-Premises, confirm the process-execution mechanism that is
approved in that installation and point it at this script or at
``adapters/tosca/run_reconciliation.ps1``.
"""

from __future__ import annotations

import sys

from universal_utils.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
