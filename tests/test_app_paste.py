from __future__ import annotations

import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cursay.app import CursayApplication


class AppPasteTests(unittest.TestCase):
    def make_app(self) -> SimpleNamespace:
        app = SimpleNamespace(
            config={"paste_shortcut": "ctrl_shift_v"},
            virtual_keyboard=Mock(),
            pending_auto_paste=True,
            pending_auto_paste_text="dictated text",
            window=None,
            notify=Mock(),
        )
        app._paste_pending = lambda: CursayApplication._paste_pending(app)
        app._verify_clipboard_for_paste = lambda attempt: CursayApplication._verify_clipboard_for_paste(app, attempt)
        return app

    def test_verified_clipboard_queues_selected_terminal_shortcut(self) -> None:
        app = self.make_app()
        with (
            patch("cursay.app.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"dictated text", b"")),
            patch("cursay.app.GLib.timeout_add") as timer,
        ):
            self.assertFalse(app._verify_clipboard_for_paste(0))
            app.virtual_keyboard.paste.assert_not_called()
            timer.call_args.args[1]()
        app.virtual_keyboard.paste.assert_called_once_with("ctrl_shift_v")
        self.assertFalse(app.pending_auto_paste)
        self.assertEqual(app.pending_auto_paste_text, "")

    def test_cancelled_delayed_paste_does_not_paste_correction_into_dialog(self) -> None:
        app = self.make_app()
        app.pending_auto_paste = False
        app.pending_auto_paste_text = ""
        self.assertFalse(app._paste_pending())
        app.virtual_keyboard.paste.assert_not_called()

    def test_stale_clipboard_cancels_terminal_paste(self) -> None:
        app = self.make_app()
        with (
            patch("cursay.app.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"old clipboard", b"")),
            patch("cursay.app.GLib.timeout_add") as timer,
        ):
            self.assertFalse(app._verify_clipboard_for_paste(8))
            timer.assert_not_called()
        app.virtual_keyboard.paste.assert_not_called()
        self.assertFalse(app.pending_auto_paste)


if __name__ == "__main__":
    unittest.main()
