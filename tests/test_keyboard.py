from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cursay.keyboard import VirtualKeyboard


class VirtualKeyboardTests(unittest.TestCase):
    def test_paste_sends_only_ctrl_v(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket = Path(directory) / "cursay-ydotool.sock"
            socket.touch()
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
                patch("cursay.keyboard.YDOTOOL", Path("/bin/true")),
                patch(
                    "cursay.keyboard.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, b"", b""),
                ) as run,
            ):
                self.assertTrue(VirtualKeyboard().paste())
            command = run.call_args.args[0]
            self.assertEqual(command[-4:], ["29:1", "47:1", "47:0", "29:0"])
            self.assertEqual(run.call_args.kwargs["env"]["YDOTOOL_SOCKET"], str(socket))

    def test_paste_fails_closed_without_private_socket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
                patch("cursay.keyboard.YDOTOOL", Path("/bin/true")),
                patch("cursay.keyboard.subprocess.run") as run,
            ):
                self.assertFalse(VirtualKeyboard().paste())
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
