from __future__ import annotations

import unittest
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402

from cursay.insights import summarize_speed
from cursay.speed_chart import SpeedChart


class LayoutTests(unittest.TestCase):
    def test_speed_chart_renders_empty_and_isolated_days_without_cairo(self) -> None:
        Gtk.init()
        chart = SpeedChart()
        chart.allocate(600, 190, -1, None)
        now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        rows = [
            {"created_at": "2026-10-01T10:00:00+00:00", "word_count": 100, "duration_seconds": 60},
            {"created_at": "2026-10-12T10:00:00+00:00", "word_count": 100, "duration_seconds": 30},
        ]
        for history in ([], rows):
            with self.subTest(empty=not history):
                chart.set_data(summarize_speed(history, 14, now)["daily"])
                snapshot = Gtk.Snapshot()
                chart.do_snapshot(snapshot)
                image = snapshot.to_paintable(None)
                self.assertGreater(image.get_intrinsic_width(), 0)
                self.assertGreater(image.get_intrinsic_height(), 0)
        chart._motion(None, chart.get_width() - chart.RIGHT, 100)
        self.assertIn("2026-10-12: 200.0 WPM", chart.get_tooltip_text())

    def test_long_history_text_has_bounded_natural_width(self) -> None:
        Gtk.init()
        label = Gtk.Label(label="A long dictation with normal wrapping. " * 40, xalign=0)
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(72)
        _minimum, natural, _min_baseline, _nat_baseline = label.measure(
            Gtk.Orientation.HORIZONTAL,
            -1,
        )
        self.assertLess(natural, 700)


if __name__ == "__main__":
    unittest.main()
