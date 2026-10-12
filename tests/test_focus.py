from __future__ import annotations

import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cursay.focus import _active_accessible_application, _x11_application, active_application


class FocusTests(unittest.TestCase):
    def test_headless_session_skips_desktop_detection(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("cursay.focus._x11_application") as detect:
            self.assertEqual(active_application(), ())
            detect.assert_not_called()

    def test_x11_reads_window_class_without_requesting_titles(self) -> None:
        with (
            patch.dict(os.environ, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}, clear=True),
            patch("cursay.focus.shutil.which", return_value="/usr/bin/xprop"),
            patch("cursay.focus.subprocess.run", side_effect=[
                subprocess.CompletedProcess([], 0, "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x123", ""),
                subprocess.CompletedProcess([], 0, 'WM_CLASS(STRING) = "warp", "dev.warp.Warp"', ""),
            ]) as run,
        ):
            self.assertEqual(_x11_application(), ("warp", "dev.warp.Warp"))
            self.assertEqual(run.call_args.args[0], ["xprop", "-id", "0x123", "WM_CLASS", "_NET_WM_STATE"])

    def test_wayland_rejects_stale_xwayland_focus(self) -> None:
        for focused in (False, True):
            with (
                self.subTest(focused=focused),
                patch.dict(os.environ, {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"}, clear=True),
                patch("cursay.focus.shutil.which", return_value="/usr/bin/xprop"),
                patch("cursay.focus.subprocess.run", side_effect=[
                    subprocess.CompletedProcess([], 0, "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x123", ""),
                    subprocess.CompletedProcess([], 0, 'WM_CLASS(STRING) = "warp"\n_NET_WM_STATE(ATOM) = '
                                                + ("_NET_WM_STATE_FOCUSED" if focused else ""), ""),
                ]),
            ):
                self.assertEqual(_x11_application(), ("warp",) if focused else ())

    def test_x11_unavailable_or_no_active_window(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("cursay.focus.subprocess.run") as run:
            self.assertEqual(_x11_application(), ())
            run.assert_not_called()
        with (
            patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True),
            patch("cursay.focus.shutil.which", return_value="xprop"),
            patch("cursay.focus.subprocess.run") as run,
        ):
            for output in ("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x0", "missing property"):
                run.return_value = subprocess.CompletedProcess([], 0, output, "")
                self.assertEqual(_x11_application(), ())
            run.side_effect = subprocess.TimeoutExpired("xprop", 0.3)
            self.assertEqual(_x11_application(), ())

    def test_accessibility_uses_active_window_and_application_executable(self) -> None:
        inactive = Mock()
        inactive.get_state_set.return_value.contains.return_value = False
        active = Mock()
        active.get_state_set.return_value.contains.return_value = True
        app = Mock()
        app.get_name.return_value = "Localized terminal name"
        app.get_process_id.return_value = 42
        app.get_child_count.return_value = 2
        app.get_child_at_index.side_effect = [inactive, active]
        desktop = Mock()
        desktop.get_child_count.return_value = 2
        desktop.get_child_at_index.side_effect = [RuntimeError("closed app"), app]
        atspi = SimpleNamespace(
            set_timeout=Mock(), get_desktop=Mock(return_value=desktop), StateType=SimpleNamespace(ACTIVE=1),
        )
        with patch("cursay.focus.os.readlink", return_value="/usr/libexec/gnome-terminal-server"):
            self.assertEqual(_active_accessible_application(atspi), ("Localized terminal name", "gnome-terminal-server"))
        active.get_state_set.return_value.contains.assert_called_once_with(1)
        active.get_name.assert_not_called()
        active.get_child_at_index.assert_not_called()
        atspi.set_timeout.assert_called_once_with(100, 100)


if __name__ == "__main__":
    unittest.main()
