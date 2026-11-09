"""Guards for the clean-wheel rerun."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def require_wheel_when_requested() -> None:
    """Fail the lab when the wheel run still imports the checkout."""
    if os.environ.get("QA_UTILS_REQUIRE_WHEEL") != "1":
        return
    completed = subprocess.run(
        [
            sys.executable,
            "-P",
            "-c",
            "import universal_utils; print(universal_utils.__file__)",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(sys.executable).anchor,
    )
    assert completed.returncode == 0, completed.stderr
    location = Path(completed.stdout.strip()).resolve()
    source_tree = (REPO_ROOT / "universal_utils").resolve()
    assert not location.is_relative_to(source_tree), location
    assert "site-packages" in location.parts, location
