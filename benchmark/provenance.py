"""Content fingerprints for local, non-secret run provenance."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_state(root: Path) -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            check=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"git_revision": None, "worktree_dirty": None}
    return {"git_revision": revision, "worktree_dirty": bool(status.strip())}


def candidate_provenance(config: dict[str, Any], rubric: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        "benchmark_config_sha256": sha256_json(config),
        "rubric_sha256": sha256_json(rubric),
        **git_state(root),
    }
