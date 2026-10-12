from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def runtime_digest(root: Path) -> str:
    """Fingerprint shipped application source, excluding generated build metadata."""
    paths = [*root.joinpath("cursay").glob("*.py"), *root.joinpath("assets").rglob("*")]
    if root.joinpath("bin/cursay").is_file():
        paths.append(root / "bin/cursay")
    digest = hashlib.sha256()
    for path in sorted(path for path in paths if path.is_file()):
        content = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(str(len(content)).encode() + b"\0" + content)
    return digest.hexdigest()


def capture_build_info(root: Path) -> dict[str, Any]:
    revision = ""
    dirty = None
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True,
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"source_revision": revision, "source_dirty": dirty, "source_digest": runtime_digest(root)}


def read_build_info(path: Path) -> dict[str, Any]:
    try:
        info = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return info if isinstance(info, dict) else {}


def build_label(info: dict[str, Any]) -> str:
    revision, digest = info.get("source_revision"), info.get("source_digest")
    if not revision and not digest:
        return ""
    label = f"Build {str(revision)[:7] if revision else 'unversioned'}"
    if info.get("source_dirty"):
        label += " • local changes"
    if digest:
        label += f"\nSource {str(digest)[:8]}"
    return label
