"""Cursay: native, private dictation for Ubuntu."""

import json
from pathlib import Path

__version__ = "1.3.0"

try:
    __source_revision__ = json.loads(Path(__file__).with_name("build-info.json").read_text()).get("source_revision") or ""
except (OSError, ValueError, TypeError):
    __source_revision__ = ""
