from __future__ import annotations

import math
from datetime import date
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, Graphene, Gtk, Pango  # noqa: E402


class SpeedChart(Gtk.Widget):
    """Daily WPM points with gaps for days without timed dictation."""

    LEFT = 48
    RIGHT = 18
    TOP = 16
    BOTTOM = 32

    def __init__(self) -> None:
        super().__init__()
        self.daily: list[dict[str, Any]] = []
        self.set_hexpand(True)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        self.add_controller(motion)

    def set_data(self, daily: list[dict[str, Any]]) -> None:
        self.daily = daily
        self.set_tooltip_text("Daily words per minute. Hover over a day for details.")
        self.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Daily dictation speed in words per minute. See the daily breakdown for values."],
        )
        self.queue_draw()

    def _motion(self, _controller: Any, x: float, _y: float) -> None:
        if not self.daily:
            return
        width = max(1, self.get_width() - self.LEFT - self.RIGHT)
        index = round((x - self.LEFT) / width * (len(self.daily) - 1))
        row = self.daily[max(0, min(index, len(self.daily) - 1))]
        speed = f"{row['wpm']:.1f} WPM" if row["wpm"] is not None else "Speed unavailable"
        self.set_tooltip_text(f"{row['day']}: {speed} · {row['words']:,} words · {row['count']} dictations")

    def do_measure(self, orientation: Gtk.Orientation, _for_size: int) -> tuple[int, int, int, int]:
        size = 190 if orientation == Gtk.Orientation.VERTICAL else 0
        return size, size, -1, -1

    @staticmethod
    def _color(red: float, green: float, blue: float, alpha: float = 1) -> Gdk.RGBA:
        color = Gdk.RGBA()
        color.red, color.green, color.blue, color.alpha = red, green, blue, alpha
        return color

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        width, height = self.get_width(), self.get_height()
        foreground = self.get_color() if hasattr(self, "get_color") else self.get_style_context().get_color()
        dark = foreground.red + foreground.green + foreground.blue > 1.5
        accent_rgb = (0.47, 0.89, 0.76) if dark else (0.03, 0.46, 0.36)
        accent = self._color(*accent_rgb)
        grid = self._color(foreground.red, foreground.green, foreground.blue, 0.14)
        text = self._color(foreground.red, foreground.green, foreground.blue, 0.8)
        chart_width = max(1, width - self.LEFT - self.RIGHT)
        chart_height = max(1, height - self.TOP - self.BOTTOM)
        rates = [row["wpm"] for row in self.daily if row["wpm"] is not None]
        ceiling = max(50, math.ceil(max(rates, default=0) / 50) * 50)

        def rectangle(x: float, y: float, w: float, h: float) -> Graphene.Rect:
            return Graphene.Rect().init(x, y, w, h)

        def label_layout(label: str) -> Pango.Layout:
            layout = self.create_pango_layout(label)
            layout.set_font_description(Pango.FontDescription.from_string("Sans 8.5"))
            return layout

        def draw_label(layout: Pango.Layout, x: float, y: float) -> None:
            snapshot.save()
            snapshot.translate(Graphene.Point().init(x, y))
            snapshot.append_layout(layout, text)
            snapshot.restore()

        for value in (0, ceiling / 2, ceiling):
            y = self.TOP + chart_height * (1 - value / ceiling)
            snapshot.append_color(grid, rectangle(self.LEFT, y, chart_width, 1))
            draw_label(label_layout(f"{value:g}"), 4, y - 7)
        if not self.daily:
            return
        count = len(self.daily)
        for index in (0, (count - 1) // 2, count - 1):
            label = date.fromisoformat(self.daily[index]["day"]).strftime("%b %d")
            x = self.LEFT + chart_width * index / max(1, count - 1)
            layout = label_layout(label)
            label_width, label_height = layout.get_pixel_size()
            draw_label(layout, max(0, min(width - label_width, x - label_width / 2)), height - label_height - 4)
        previous: tuple[float, float] | None = None
        for index, row in enumerate(self.daily):
            if row["wpm"] is None:
                previous = None
                continue
            x = self.LEFT + chart_width * index / max(1, count - 1)
            y = self.TOP + chart_height * (1 - row["wpm"] / ceiling)
            if previous is not None:
                dx, dy = x - previous[0], y - previous[1]
                snapshot.save()
                snapshot.translate(Graphene.Point().init(*previous))
                snapshot.rotate(math.degrees(math.atan2(dy, dx)))
                snapshot.append_color(accent, rectangle(0, -1, math.hypot(dx, dy), 2))
                snapshot.restore()
            snapshot.save()
            snapshot.translate(Graphene.Point().init(x, y))
            snapshot.rotate(45)
            snapshot.append_color(accent, rectangle(-2, -2, 4, 4))
            snapshot.restore()
            previous = x, y
        if not rates:
            layout = label_layout("No timed dictations in this period.")
            label_width, _label_height = layout.get_pixel_size()
            draw_label(layout, self.LEFT + (chart_width - label_width) / 2, self.TOP + chart_height / 2)
