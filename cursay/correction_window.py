from __future__ import annotations

import sqlite3
from typing import Any, Callable

from .corrections import suggest_replacements

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class CorrectionWindow(Gtk.Window):
    def __init__(
        self, parent: Gtk.Window, item: dict[str, Any],
        save: Callable[[int, str, list[tuple[str, str]]], None],
    ) -> None:
        super().__init__(title="Correct dictation", transient_for=parent, modal=True)
        self.set_default_size(660, 650)
        self.item = item
        self.save = save
        self.choices: list[tuple[Gtk.CheckButton, tuple[str, str]]] = []
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scroll)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for edge in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{edge}")(20)
        scroll.set_child(content)
        intro = Gtk.Label(
            label="Edit the text below, or paste your corrected text from an email or another app. "
            "Cursay only remembers replacements you select after reviewing them.", xalign=0,
        )
        intro.set_wrap(True)
        intro.set_max_width_chars(65)
        content.append(intro)
        original = Gtk.Expander(label="Original speech recognition and pasted text")
        details = Gtk.Label(
            label=f"Speech recognition:\n{item['raw_text']}\n\n"
            f"Originally produced:\n{item.get('original_final_text') or item['final_text']}", xalign=0,
        )
        details.set_wrap(True)
        details.set_selectable(True)
        details.set_max_width_chars(65)
        original.set_child(details)
        content.append(original)
        content.append(Gtk.Label(label="Corrected text", xalign=0))
        self.editor = Gtk.TextView()
        self.editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.editor.set_top_margin(10)
        self.editor.set_bottom_margin(10)
        self.editor.set_left_margin(10)
        self.editor.set_right_margin(10)
        self.editor.get_buffer().set_text(item["final_text"])
        editor_scroll = Gtk.ScrolledWindow()
        editor_scroll.set_min_content_height(190)
        editor_scroll.set_child(self.editor)
        content.append(editor_scroll)
        review = Gtk.Button(label="Review replacements to remember")
        review.connect("clicked", lambda *_: self.review())
        content.append(review)
        self.suggestions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.append(self.suggestions)
        self.editor.get_buffer().connect("changed", lambda *_: self.clear_suggestions())
        self.clear_suggestions()
        self.error = Gtk.Label(xalign=0)
        self.error.set_wrap(True)
        content.append(self.error)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        actions.append(cancel)
        save_button = Gtk.Button(label="Save correction and copy")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", lambda *_: self.save_changes())
        actions.append(save_button)
        content.append(actions)
        help_label = Gtk.Label(
            label="Saving updates this history entry and your clipboard. Paste the copied result into "
            "your email or text box. Selected replacements apply to future dictations except Raw mode.",
            xalign=0,
        )
        help_label.set_wrap(True)
        help_label.set_max_width_chars(65)
        help_label.add_css_class("dim-label")
        content.append(help_label)

    def text(self) -> str:
        buffer = self.editor.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True).strip()

    def clear_suggestions(self) -> None:
        self.choices.clear()
        while child := self.suggestions.get_first_child():
            self.suggestions.remove(child)
        label = Gtk.Label(label="No replacements selected. Review changes to choose what to remember.", xalign=0)
        label.set_wrap(True)
        label.set_max_width_chars(65)
        self.suggestions.append(label)

    def review(self) -> None:
        self.clear_suggestions()
        pairs = suggest_replacements(self.item["final_text"], self.text())
        label = self.suggestions.get_first_child()
        label.set_label(
            "Select only recurring recognition mistakes. These phrases will be replaced in every non-Raw dictation."
            if pairs else "No short word replacements found. Save this edit, or add a rule on the Corrections page."
        )
        for pair in pairs:
            choice = Gtk.CheckButton()
            title = Gtk.Label(label=f"Remember: {pair[0]} → {pair[1]}", xalign=0)
            title.set_wrap(True)
            title.set_max_width_chars(65)
            choice.set_child(title)
            self.suggestions.append(choice)
            self.choices.append((choice, pair))

    def save_changes(self) -> None:
        try:
            self.save(self.item["id"], self.text(), [pair for choice, pair in self.choices if choice.get_active()])
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.error.set_label(str(exc))
            return
        self.close()
