"""Small, deterministic provenance fields for saved evaluation reports."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def code_revision() -> str:
    configured = os.environ.get("DOCWISE_GIT_REVISION", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent.parent), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unrecorded"
    return result.stdout.strip() or "unrecorded"


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
