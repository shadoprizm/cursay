from __future__ import annotations

import unittest

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402


class LayoutTests(unittest.TestCase):
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
