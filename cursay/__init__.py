"""Cursay: native, private dictation for Ubuntu."""

from pathlib import Path

from .build_info import read_build_info

__version__ = "1.3.0"

__build_info__ = read_build_info(Path(__file__).with_name("build-info.json"))
__source_revision__ = __build_info__.get("source_revision") or ""
