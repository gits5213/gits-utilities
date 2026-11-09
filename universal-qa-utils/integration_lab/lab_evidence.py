"""Write process stdout, stderr, and a manifest for one lab run."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

EVIDENCE_ROOT = Path(__file__).resolve().parent / "evidence"


def save_process_evidence(
    consumer: str,
    name: str,
    completed: subprocess.CompletedProcess[str],
    *,
    technical_status: str,
    business_status: str,
    extra_files: dict[str, Path] | None = None,
) -> Path:
    """Replace ``evidence/<consumer>/<name>`` with this process result."""
    folder = EVIDENCE_ROOT / consumer / name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (folder / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    for filename, source in (extra_files or {}).items():
        if source.is_file():
            shutil.copy2(source, folder / filename)
    manifest = {
        "business_status": business_status,
        "command": [str(part) for part in completed.args],
        "consumer": consumer,
        "returncode": completed.returncode,
        "technical_status": technical_status,
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return folder
