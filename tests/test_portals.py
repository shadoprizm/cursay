from __future__ import annotations

import unittest
from unittest.mock import patch

from cursay.portals import GlobalShortcutPortal


def portal_fixture() -> tuple[GlobalShortcutPortal, list[str]]:
    events: list[str] = []
    portal = object.__new__(GlobalShortcutPortal)
    portal.session_path = "/session/test"
    portal.key_down = False
    portal.key_repeating = False
    portal.last_activation_at = 0.0
    portal.release_watch_id = None
    portal._ensure_release_watch = lambda: None
    portal.on_pressed = lambda: events.append("press")
    portal.on_released = lambda: events.append("release")
    return portal, events


class ShortcutDebounceTests(unittest.TestCase):
    def test_suppresses_keyboard_repeat_burst(self) -> None:
        portal, events = portal_fixture()
        for _ in range(4):
            portal._activated("/session/test", "push-to-talk", 0, {})
        portal._deactivated("/session/test", "push-to-talk", 0, {})
        self.assertEqual(events, ["press", "release"])

    def test_does_not_toggle_without_a_release(self) -> None:
        portal, events = portal_fixture()
        portal._activated("/session/test", "push-to-talk", 0, {})
        portal._activated("/session/test", "push-to-talk", 0, {})
        portal._activated("/session/test", "push-to-talk", 0, {})
        self.assertEqual(events, ["press"])

    def test_next_press_requires_release(self) -> None:
        portal, events = portal_fixture()
        portal._activated("/session/test", "push-to-talk", 0, {})
        portal._deactivated("/session/test", "push-to-talk", 0, {})
        portal._activated("/session/test", "push-to-talk", 0, {})
        portal._deactivated("/session/test", "push-to-talk", 0, {})
        self.assertEqual(events, ["press", "release", "press", "release"])

    def test_infers_release_when_repeat_stream_ends(self) -> None:
        portal, events = portal_fixture()
        portal.key_down = True
        portal.key_repeating = True
        portal.last_activation_at = 10.0
        portal.release_watch_id = 99
        with patch("cursay.portals.time.monotonic", return_value=10.31):
            self.assertFalse(portal._check_inferred_release())
        self.assertEqual(events, ["release"])
        self.assertFalse(portal.key_down)
        self.assertIsNone(portal.release_watch_id)

    def test_keeps_recording_while_repeat_stream_is_active(self) -> None:
        portal, events = portal_fixture()
        portal.key_down = True
        portal.key_repeating = True
        portal.last_activation_at = 10.0
        portal.release_watch_id = 99
        with patch("cursay.portals.time.monotonic", return_value=10.20):
            self.assertTrue(portal._check_inferred_release())
        self.assertEqual(events, [])
        self.assertTrue(portal.key_down)


if __name__ == "__main__":
    unittest.main()
