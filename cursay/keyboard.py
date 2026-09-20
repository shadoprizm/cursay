from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import PROJECT_DIR


LOG = logging.getLogger(__name__)
_BUNDLED_YDOTOOL = PROJECT_DIR / "vendor" / "ydotool" / "usr" / "bin" / "ydotool"
YDOTOOL = _BUNDLED_YDOTOOL if _BUNDLED_YDOTOOL.is_file() else Path(shutil.which("ydotool") or _BUNDLED_YDOTOOL)


class VirtualKeyboard:
    """Minimal keyboard-only uinput client used to send Ctrl+V."""

    def __init__(self) -> None:
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        self.socket = runtime_dir / "cursay-ydotool.sock"

    @property
    def ready(self) -> bool:
        return YDOTOOL.is_file() and self.socket.exists()

    def paste(self) -> bool:
        if not self.ready:
            LOG.warning("Virtual keyboard is not ready (socket=%s)", self.socket)
            return False
        env = os.environ.copy()
        env["YDOTOOL_SOCKET"] = str(self.socket)
        try:
            # Linux input keycodes: KEY_LEFTCTRL=29 and KEY_V=47.
            result = subprocess.run(
                [str(YDOTOOL), "key", "--key-delay", "12", "29:1", "47:1", "47:0", "29:0"],
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
        LOG.info("Sent Ctrl+V through the private uinput keyboard")
        return True
