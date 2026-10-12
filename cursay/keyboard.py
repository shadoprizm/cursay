from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import PROJECT_DIR


LOG = logging.getLogger(__name__)
_BUNDLED_YDOTOOL = PROJECT_DIR / "vendor" / "ydotool" / "usr" / "bin" / "ydotool"
YDOTOOL = _BUNDLED_YDOTOOL if _BUNDLED_YDOTOOL.is_file() else Path(shutil.which("ydotool") or _BUNDLED_YDOTOOL)
TERMINAL_APPLICATIONS = frozenset({
    "gnome-terminal", "gnome-terminal-server", "org.gnome.terminal", "kgx", "org.gnome.console",
    "ptyxis", "org.gnome.ptyxis", "warp", "warp-terminal", "dev.warp.warp", "com.warp.warp",
    "tilix", "com.gexperts.tilix", "terminator", "xfce4-terminal", "konsole", "org.kde.konsole",
    "alacritty", "kitty", "foot", "footclient", "wezterm", "org.wezfurlong.wezterm",
})


def active_application() -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("focus.py"))],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=1.5, check=False,
        )
        identities = json.loads(result.stdout) if result.returncode == 0 else []
        if isinstance(identities, list) and all(isinstance(value, str) for value in identities):
            return tuple(identities)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return ()


def paste_shortcut(mode: str = "auto") -> str:
    if mode in {"ctrl_v", "ctrl_shift_v"}:
        return mode
    # Use app identities rather than titles: a browser tab named "Terminal"
    # must not change the shortcut. Resolve focus at paste time, not recording.
    if any(identity.casefold() in TERMINAL_APPLICATIONS for identity in active_application()):
        return "ctrl_shift_v"
    return "ctrl_v"


class VirtualKeyboard:
    """Minimal keyboard-only uinput client with application-aware paste."""

    def __init__(self) -> None:
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        self.socket = runtime_dir / "cursay-ydotool.sock"

    @property
    def ready(self) -> bool:
        return YDOTOOL.is_file() and self.socket.exists()

    def paste(self, mode: str = "auto") -> bool:
        if not self.ready:
            LOG.warning("Virtual keyboard is not ready (socket=%s)", self.socket)
            return False
        env = os.environ.copy()
        env["YDOTOOL_SOCKET"] = str(self.socket)
        shortcut = paste_shortcut(mode)
        # Linux input keycodes: KEY_LEFTCTRL=29, KEY_LEFTSHIFT=42, KEY_V=47.
        keys = ["29:1", "47:1", "47:0", "29:0"]
        if shortcut == "ctrl_shift_v":
            keys = ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
        try:
            result = subprocess.run(
                [str(YDOTOOL), "key", "--key-delay", "12", *keys],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            LOG.warning("Virtual keyboard paste failed: %s", exc)
            return False
        if result.returncode != 0:
            LOG.warning(
                "Virtual keyboard paste failed with status %s: %s",
                result.returncode,
                result.stderr.decode("utf-8", "replace").strip(),
            )
            return False
        LOG.info("Sent %s through the private uinput keyboard", shortcut)
        return True
