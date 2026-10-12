"""Read active application identities, without reading window titles or text.

Run separately from the GTK app: accessibility providers may hang, and libatspi
can abort when the accessibility bus is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import resource
import shutil
import subprocess
from pathlib import Path


def _x11_application() -> tuple[str, ...]:
    if not os.environ.get("DISPLAY") or not shutil.which("xprop"):
        return ()
    try:
        root = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True, text=True, timeout=0.3, check=False,
        )
        match = re.search(r"window id # (0x[0-9a-fA-F]+)", root.stdout)
        if root.returncode or not match or int(match[1], 16) == 0:
            return ()
        window = subprocess.run(
            ["xprop", "-id", match[1], "WM_CLASS", "_NET_WM_STATE"],
            capture_output=True, text=True, timeout=0.3, check=False,
        )
        if window.returncode:
            return ()
        # XWayland's root can still name the last X11 window after focus moves
        # to a native Wayland app. Accept it only if it is currently focused.
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            if "_NET_WM_STATE_FOCUSED" not in window.stdout:
                return ()
        for line in window.stdout.splitlines():
            if line.startswith("WM_CLASS(STRING)"):
                return tuple(re.findall(r'"([^"\\]*)"', line))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ()


def _active_accessible_application(atspi) -> tuple[str, ...]:
    atspi.set_timeout(100, 100)
    desktop = atspi.get_desktop(0)
    if desktop is None:
        return ()
    # Inspect only applications and their top-level windows, never text widgets.
    for index in range(min(desktop.get_child_count(), 64)):
        try:
            app = desktop.get_child_at_index(index)
            if app is None:
                continue
            for child_index in range(min(app.get_child_count(), 16)):
                window = app.get_child_at_index(child_index)
                if window is None:
                    continue
                states = window.get_state_set()
                if states is None or not states.contains(atspi.StateType.ACTIVE):
                    continue
                identities = [app.get_name() or ""]
                try:
                    identities.append(Path(os.readlink(f"/proc/{app.get_process_id()}/exe")).name)
                except OSError:
                    pass
                return tuple(identities)
        except Exception:
            # One inaccessible or closing app must not hide the other apps.
            continue
    return ()


def active_application() -> tuple[str, ...]:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return ()
    identities = _x11_application()
    if identities:
        return identities
    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        return _active_accessible_application(Atspi)
    except Exception:
        return ()


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    print(json.dumps(active_application()))
