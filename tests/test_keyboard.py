from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cursay.keyboard import VirtualKeyboard, active_application, paste_shortcut


class VirtualKeyboardTests(unittest.TestCase):
    def test_paste_sends_only_ctrl_v(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket = Path(directory) / "cursay-ydotool.sock"
            socket.touch()
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
                patch("cursay.keyboard.YDOTOOL", Path(sys.executable)),
                patch("cursay.keyboard.active_application", return_value=("firefox",)),
                patch(
                    "cursay.keyboard.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, b"", b""),
                ) as run,
            ):
                self.assertTrue(VirtualKeyboard().paste())
            command = run.call_args.args[0]
            self.assertEqual(command[-4:], ["29:1", "47:1", "47:0", "29:0"])
            self.assertEqual(run.call_args.kwargs["env"]["YDOTOOL_SOCKET"], str(socket))

    def test_terminal_paste_releases_all_modifiers_without_enter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "cursay-ydotool.sock").touch()
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
                patch("cursay.keyboard.YDOTOOL", Path(sys.executable)),
                patch("cursay.keyboard.active_application", return_value=("dev.warp.Warp",)),
                patch("cursay.keyboard.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as run,
            ):
                self.assertTrue(VirtualKeyboard().paste())
            self.assertEqual(run.call_args.args[0][4:], ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"])

    def test_terminal_identities_choose_terminal_shortcut(self) -> None:
        for identity in ("gnome-terminal-server", "org.gnome.Terminal", "Warp", "warp-terminal", "kgx", "ptyxis"):
            with self.subTest(identity=identity), patch("cursay.keyboard.active_application", return_value=(identity,)):
                self.assertEqual(paste_shortcut(), "ctrl_shift_v")

    def test_unrecognized_apps_and_missing_focus_keep_standard_paste(self) -> None:
        for identities in (("firefox",), ("my-terminal-notes",), ("Terminal",), ()):
            with self.subTest(identities=identities), patch("cursay.keyboard.active_application", return_value=identities):
                self.assertEqual(paste_shortcut(), "ctrl_v")

    def test_manual_shortcut_does_not_require_focus_detection(self) -> None:
        with patch("cursay.keyboard.active_application") as detect:
            self.assertEqual(paste_shortcut("ctrl_shift_v"), "ctrl_shift_v")
            self.assertEqual(paste_shortcut("ctrl_v"), "ctrl_v")
            detect.assert_not_called()

    def test_focus_helper_failures_are_bounded_and_use_standard_paste(self) -> None:
        for error in (OSError("unavailable"), subprocess.TimeoutExpired("focus", 1.5)):
            with self.subTest(error=error), patch("cursay.keyboard.subprocess.run", side_effect=error) as run:
                self.assertEqual(active_application(), ())
                self.assertEqual(run.call_args.kwargs["timeout"], 1.5)
        for output, code in (("[\"warp\"]", 0), ("not json", 0), ('{"app":"warp"}', 0), ('[1]', 0), ('["warp"]', -6)):
            with self.subTest(output=output, code=code), patch(
                "cursay.keyboard.subprocess.run",
                return_value=subprocess.CompletedProcess([], code, output, ""),
            ):
                self.assertEqual(active_application(), ("warp",) if output == '["warp"]' and code == 0 else ())

    def test_keyboard_command_failure_reports_copy_only(self) -> None:
        with patch.object(VirtualKeyboard, "ready", True), patch("cursay.keyboard.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, b"", b"unavailable")
            self.assertFalse(VirtualKeyboard().paste("ctrl_shift_v"))

    def test_paste_fails_closed_without_private_socket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
                patch("cursay.keyboard.YDOTOOL", Path(sys.executable)),
                patch("cursay.keyboard.subprocess.run") as run,
            ):
                self.assertFalse(VirtualKeyboard().paste())
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
