from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from . import __version__
from .audio import AudioError, PipeWireRecorder
from .config import CONFIG_FILE, DATABASE_FILE, PROJECT_DIR, load_config
from .keyboard import YDOTOOL, VirtualKeyboard
from .stt import TranscriptionError, health, transcribe


def check() -> dict[str, Any]:
    config = load_config()
    virtual_keyboard = VirtualKeyboard()
    result: dict[str, Any] = {
        "app": "Cursay",
        "version": __version__,
        "project": str(PROJECT_DIR),
        "config": str(CONFIG_FILE),
        "database": str(DATABASE_FILE),
        "session_type": __import__("os").environ.get("XDG_SESSION_TYPE", "unknown"),
        "commands": {name: bool(shutil.which(name)) for name in ("pw-record", "gdbus", "systemctl")},
        "virtual_keyboard": {
            "binary": str(YDOTOOL),
            "socket": str(virtual_keyboard.socket),
            "ready": virtual_keyboard.ready,
        },
        "stt": health(str(config["stt_endpoint"])),
    }
    try:
        import dbus
        import gi

        gi.require_version("Gtk", "4.0")
        result["desktop_runtime"] = "ok"
        bus = dbus.SessionBus()
        result["portal_available"] = bool(bus.name_has_owner("org.freedesktop.portal.Desktop"))
    except Exception as exc:
        result["desktop_runtime"] = f"error: {exc}"
        result["portal_available"] = False
    result["ok"] = (
        all(result["commands"].values())
        and result["stt"].get("status") == "ok"
        and result["desktop_runtime"] == "ok"
        and result["portal_available"]
        and result["virtual_keyboard"]["ready"]
    )
    return result


def print_check() -> int:
    result = check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def record_test(seconds: float = 1.25) -> int:
    config = load_config()
    recorder = PipeWireRecorder()
    try:
        path = recorder.start()
        time.sleep(max(0.5, min(seconds, 10)))
        path, duration = recorder.stop(False)
        size = path.stat().st_size
        print(json.dumps({"recorded": str(path), "seconds": round(duration, 2), "bytes": size}, indent=2))
        try:
            result = transcribe(
                path,
                str(config["stt_endpoint"]),
                "whisper-base.en",
                str(config["language"]),
            )
            print(json.dumps({"transcription": result}, indent=2))
        finally:
            path.unlink(missing_ok=True)
        return 0
    except (AudioError, TranscriptionError, OSError) as exc:
        recorder.cancel()
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
