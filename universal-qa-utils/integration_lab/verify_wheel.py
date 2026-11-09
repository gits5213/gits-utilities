"""Build a wheel, install it into a clean virtual environment, and rerun the lab.

The lab proves the installed files, not the checkout. Tosca Commander is not
started here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV = REPO_ROOT / ".release-venv"
DIST = REPO_ROOT / "dist"


def main() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    _run([sys.executable, "-m", "build"], cwd=REPO_ROOT)
    wheels = sorted(DIST.glob("universal_qa_utils-*.whl"))
    if len(wheels) != 1:
        print(f"Expected one wheel in {DIST}, found {wheels}", file=sys.stderr)
        return 1
    wheel = wheels[0]
    _assert_wheel_contents(wheel)
    if VENV.exists():
        shutil.rmtree(VENV)
    _run([sys.executable, "-m", "venv", str(VENV)])
    python = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run([str(python), "-m", "pip", "install", str(wheel), "pytest", "robotframework"])
    env = os.environ.copy()
    env["QA_UTILS_REQUIRE_WHEEL"] = "1"
    env["PYTHON"] = str(python)
    completed = subprocess.run(
        [
            str(python),
            "-m",
            "pytest",
            "integration_lab",
            "--basetemp",
            str(REPO_ROOT / ".tmp" / "wheel"),
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    print(f"wheel={wheel.name}")
    print(f"venv={VENV}")
    print(f"integration_exit={completed.returncode}")
    return completed.returncode


def _assert_wheel_contents(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    if "universal_utils/cli.py" not in names:
        raise SystemExit("Wheel is missing universal_utils/cli.py")
    if any(name.startswith("adapters/") or name.startswith("integration_lab/") for name in names):
        raise SystemExit("Wheel contains lab or adapter sources.")
    entry = next(name for name in names if name.endswith("entry_points.txt"))
    with zipfile.ZipFile(wheel) as archive:
        text = archive.read(entry).decode("utf-8")
    if "qa-utils = universal_utils.cli:main" not in text:
        raise SystemExit("Wheel entry points do not install qa-utils.")


def _run(command: list[str], cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
