from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import __version__
from .audio import AudioError, PipeWireRecorder
from .cleanup import PolishError, clean_transcript, polish_transcript, should_polish
from .config import APPEARANCE_OPTIONS, APP_ID, APP_NAME, PROJECT_DIR, load_config, save_config
from .keyboard import VirtualKeyboard
from .portals import GlobalShortcutPortal
from .pricing import format_usd, reported_cost_usd
from .storage import HistoryStore
from .stt import TranscriptionError, health, transcribe
from .updates import (
    NoReleaseAvailable,
    ReleaseInfo,
    UpdateError,
    consume_update_status,
    fetch_latest_release,
    is_newer_version,
    launch_update,
)


LOG = logging.getLogger(__name__)
_BUNDLED_WL_COPY = PROJECT_DIR / "vendor" / "wl-clipboard" / "usr" / "bin" / "wl-copy"
_BUNDLED_WL_PASTE = PROJECT_DIR / "vendor" / "wl-clipboard" / "usr" / "bin" / "wl-paste"
WL_COPY = _BUNDLED_WL_COPY if _BUNDLED_WL_COPY.is_file() else Path(shutil.which("wl-copy") or _BUNDLED_WL_COPY)
WL_PASTE = _BUNDLED_WL_PASTE if _BUNDLED_WL_PASTE.is_file() else Path(shutil.which("wl-paste") or _BUNDLED_WL_PASTE)

CSS = """
window.theme-dark {
  background-color: #0a1120;
  color: #eef4fb;
}
window.theme-light {
  background-color: #f3f6fa;
  color: #172235;
}

.theme-dark .app-shell { background-color: #0a1120; }
.theme-light .app-shell { background-color: #f3f6fa; }

.theme-dark .sidebar {
  background-color: #101a2b;
  border-right: 1px solid #2b3a50;
}
.theme-light .sidebar {
  background-color: #e9eef5;
  border-right: 1px solid #cbd5e1;
}

.hero {
  border-radius: 24px;
  padding: 30px;
}
.theme-dark .hero {
  background-image: linear-gradient(135deg, #172842, #10343a);
  border: 1px solid #315067;
  box-shadow: 0 10px 28px alpha(#000000, 0.22);
}
.theme-light .hero {
  background-image: linear-gradient(135deg, #ffffff, #e7f8f2);
  border: 1px solid #b9dcd1;
  box-shadow: 0 10px 28px alpha(#4b6178, 0.12);
}

.card, .metric {
  border-radius: 18px;
}
.card { padding: 20px; }
.metric { padding: 18px; }
.theme-dark .card, .theme-dark .metric {
  background-color: #131f31;
  border: 1px solid #2a3a50;
}
.theme-light .card, .theme-light .metric {
  background-color: #ffffff;
  border: 1px solid #d4dce7;
  box-shadow: 0 4px 16px alpha(#4b6178, 0.07);
}

.brand { font-size: 22px; font-weight: 800; }
.hero-title { font-size: 28px; font-weight: 800; }
.section-title { font-size: 20px; font-weight: 750; }
.theme-dark .brand, .theme-dark .hero-title, .theme-dark .section-title { color: #f7faff; }
.theme-light .brand, .theme-light .hero-title, .theme-light .section-title { color: #142033; }
.theme-dark .muted { color: #b4c1d0; }
.theme-light .muted { color: #52647a; }

.metric-value { font-size: 28px; font-weight: 800; }
.theme-dark .metric-value { color: #78e4c3; }
.theme-light .metric-value { color: #08755d; }

.record-button {
  min-width: 220px;
  min-height: 72px;
  border-radius: 36px;
  font-size: 17px;
  font-weight: 800;
  background-image: none;
  background-color: #57d7ae;
  color: #071b14;
  box-shadow: 0 7px 18px alpha(#1a9c77, 0.26);
}
.record-button:hover { background-color: #6ee3be; }
.record-button:active, .recording {
  background-image: none;
  background-color: #ff7180;
  color: #2b080d;
}

.status-pill {
  border-radius: 999px;
  padding: 7px 13px;
  font-weight: 700;
}
.theme-dark .status-pill { background-color: #203f43; color: #8ce9cc; }
.theme-light .status-pill { background-color: #d9f4eb; color: #08614e; }

.history-row { padding: 13px; }
.result-box {
  border-radius: 14px;
  padding: 12px;
}
.theme-dark .result-box {
  background-color: #091321;
  color: #eef4fb;
  border: 1px solid #26384f;
}
.theme-light .result-box {
  background-color: #f6f8fb;
  color: #172235;
  border: 1px solid #d5dee8;
}

.copy-button { min-width: 76px; font-weight: 700; }
.theme-dark .copy-button { color: #dff9f0; }
.theme-light .copy-button { color: #075f4d; }

.version-label { padding: 4px 16px 2px; font-size: 12px; }
.theme-dark .version-label { color: #a9b8c9; }
.theme-light .version-label { color: #566980; }

stacksidebar row { margin: 4px 8px; border-radius: 10px; }
.theme-dark stacksidebar row { color: #c8d3df; }
.theme-light stacksidebar row { color: #35465b; }
.theme-dark stacksidebar row:selected { background-color: #21354e; color: #ffffff; }
.theme-light stacksidebar row:selected { background-color: #d5e6e2; color: #0c493d; }
"""


class CursayWindow(Adw.ApplicationWindow):
    def __init__(self, application: "CursayApplication") -> None:
        super().__init__(application=application)
        self.app = application
        self._syncing_polish_switches = False
        self.sync_theme(application.is_dark_theme())
        self.set_title(APP_NAME)
        self.set_default_size(1060, 720)
        self.set_size_request(840, 600)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)
        header = Adw.HeaderBar()
        header.set_title_widget(self._brand_label())
        toolbar.add_top_bar(header)

        shell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        shell.add_css_class("app-shell")
        toolbar.set_content(shell)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar_box.set_size_request(205, -1)
        sidebar_box.set_margin_top(12)
        sidebar_box.set_margin_bottom(12)
        sidebar_box.add_css_class("sidebar")
        sidebar = Gtk.StackSidebar(stack=self.stack)
        sidebar.set_vexpand(True)
        sidebar_box.append(sidebar)
        version = Gtk.Label(label=f"Private • Local\nVersion {__version__}")
        version.add_css_class("version-label")
        sidebar_box.append(version)
        shell.append(sidebar_box)
        shell.append(self.stack)

        self.dashboard_page = self._dashboard()
        self.history_page = self._history()
        self.insights_page = self._insights()
        self.settings_page = self._settings()
        self.stack.add_titled(self.dashboard_page, "dashboard", "Dictate")
        self.stack.add_titled(self.history_page, "history", "History")
        self.stack.add_titled(self.insights_page, "insights", "Insights")
        self.stack.add_titled(self.settings_page, "settings", "Settings")
        self.stack.connect("notify::visible-child-name", self._page_changed)
        self.connect("close-request", self._on_close_request)

    @staticmethod
    def _brand_label() -> Gtk.Label:
        label = Gtk.Label(label="Cursay")
        label.add_css_class("brand")
        return label

    def sync_theme(self, dark: bool) -> None:
        self.remove_css_class("theme-dark")
        self.remove_css_class("theme-light")
        self.add_css_class("theme-dark" if dark else "theme-light")

    @staticmethod
    def _page_container() -> Gtk.ScrolledWindow:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # Wrapped labels may report the full unwrapped line as their natural
        # width. Never let page content resize the application window.
        scroll.set_propagate_natural_width(False)
        return scroll

    @staticmethod
    def _content_box(spacing: int = 20) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.set_margin_top(28)
        box.set_margin_bottom(28)
        box.set_margin_start(32)
        box.set_margin_end(32)
        return box

    @staticmethod
    def _section_title(title: str, subtitle: str = "") -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        heading = Gtk.Label(label=title, xalign=0)
        heading.add_css_class("section-title")
        box.append(heading)
        if subtitle:
            detail = Gtk.Label(label=subtitle, xalign=0)
            detail.set_wrap(True)
            detail.add_css_class("muted")
            box.append(detail)
        return box

    def _dashboard(self) -> Gtk.ScrolledWindow:
        scroll = self._page_container()
        content = self._content_box()
        scroll.set_child(content)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=17)
        hero.add_css_class("hero")
        heading = Gtk.Label(label="Speak naturally. Get clean text.", xalign=0)
        heading.add_css_class("hero-title")
        heading.set_wrap(True)
        hero.append(heading)
        subtitle = Gtk.Label(
            label="Press and hold Ctrl + Space anywhere, speak naturally, then release the keys to transcribe and paste.",
            xalign=0,
        )
        subtitle.set_wrap(True)
        subtitle.add_css_class("muted")
        hero.append(subtitle)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.record_button = Gtk.Button(label="Hold to talk")
        self.record_button.add_css_class("record-button")
        gesture = Gtk.GestureClick()
        gesture.set_button(1)
        gesture.connect("pressed", lambda *_args: self.app.start_recording("window"))
        gesture.connect("released", lambda *_args: self.app.stop_recording("window"))
        self.record_button.add_controller(gesture)
        controls.append(self.record_button)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mode_label = Gtk.Label(label="Writing style", xalign=0)
        mode_label.add_css_class("muted")
        mode_box.append(mode_label)
        self.mode_dropdown = Gtk.DropDown.new_from_strings(["Professional", "Casual", "Prompt", "Code", "Raw"])
        modes = ["professional", "casual", "prompt", "code", "raw"]
        self.mode_dropdown.set_selected(max(0, modes.index(self.app.config.get("mode", "professional"))))
        self.mode_dropdown.connect("notify::selected", self._mode_changed)
        mode_box.append(self.mode_dropdown)

        polish_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        polish_label = Gtk.Label(label="Smart polish", xalign=0)
        polish_label.set_hexpand(True)
        polish_row.append(polish_label)
        self.dashboard_polish_switch = Gtk.Switch(
            active=bool(self.app.config["smart_polish"]),
            valign=Gtk.Align.CENTER,
        )
        self.dashboard_polish_switch.connect("notify::active", self._dashboard_polish_changed)
        polish_row.append(self.dashboard_polish_switch)
        mode_box.append(polish_row)

        self.mode_detail = Gtk.Label(xalign=0)
        self.mode_detail.set_wrap(True)
        self.mode_detail.set_max_width_chars(44)
        self.mode_detail.add_css_class("muted")
        mode_box.append(self.mode_detail)
        self._update_mode_detail()
        controls.append(mode_box)
        hero.append(controls)

        self.status_label = Gtk.Label(label="Starting…", xalign=0)
        self.status_label.add_css_class("status-pill")
        self.status_label.set_halign(Gtk.Align.START)
        hero.append(self.status_label)
        content.append(hero)

        result_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        result_card.add_css_class("card")
        result_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        result_header.append(self._section_title("Latest dictation", "The final text is always copied to your clipboard."))
        copy_button = Gtk.Button(label="Copy")
        copy_button.set_halign(Gtk.Align.END)
        copy_button.set_hexpand(True)
        copy_button.add_css_class("copy-button")
        copy_button.connect("clicked", lambda *_: self.app.copy_latest())
        result_header.append(copy_button)
        result_card.append(result_header)
        self.result_view = Gtk.TextView()
        self.result_view.set_editable(False)
        self.result_view.set_cursor_visible(False)
        self.result_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.result_view.set_top_margin(10)
        self.result_view.set_bottom_margin(10)
        self.result_view.set_left_margin(12)
        self.result_view.set_right_margin(12)
        self.result_view.set_size_request(-1, 125)
        self.result_view.add_css_class("result-box")
        self.result_view.get_buffer().set_text("Your next dictation will appear here.")
        result_card.append(self.result_view)
        content.append(result_card)

        privacy = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        privacy.add_css_class("card")
        privacy_icon = Gtk.Image.new_from_icon_name("security-high-symbolic")
        privacy_icon.set_pixel_size(28)
        privacy.append(privacy_icon)
        privacy.append(
            self._section_title(
                "Designed for privacy",
                "History stays in your account. Local Whisper remains available if cloud transcription is unavailable.",
            )
        )
        content.append(privacy)
        return scroll

    def _history(self) -> Gtk.ScrolledWindow:
        scroll = self._page_container()
        content = self._content_box()
        scroll.set_child(content)
        content.append(self._section_title("Dictation history", "Search, copy, or remove your locally stored transcriptions."))
        self.history_search = Gtk.SearchEntry(placeholder_text="Search your dictations")
        self.history_search.connect("search-changed", lambda *_: self.refresh_history())
        content.append(self.history_search)
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.history_list.set_hexpand(True)
        self.history_list.add_css_class("card")
        content.append(self.history_list)
        return scroll

    def _insights(self) -> Gtk.ScrolledWindow:
        scroll = self._page_container()
        content = self._content_box()
        scroll.set_child(content)
        content.append(self._section_title("Speech insights", "Private analytics derived from your local history."))
        metrics = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.metric_dictations = self._metric(metrics, "Dictations")
        self.metric_words = self._metric(metrics, "Words")
        self.metric_minutes = self._metric(metrics, "Minutes")
        self.metric_cost = self._metric(metrics, "Est. cost (USD)")
        content.append(metrics)
        cost_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        cost_card.add_css_class("card")
        cost_card.append(
            self._section_title(
                "Transcription cost",
                "Provider charges derived from your locally stored usage. Local Whisper has no provider fee.",
            )
        )
        self.cost_breakdown_label = Gtk.Label(label="No cost data yet.", xalign=0)
        self.cost_breakdown_label.set_wrap(True)
        self.cost_breakdown_label.add_css_class("muted")
        cost_card.append(self.cost_breakdown_label)
        self.cost_source_link = Gtk.LinkButton(label="View provider pricing")
        self.cost_source_link.set_halign(Gtk.Align.START)
        self.cost_source_link.set_visible(False)
        cost_card.append(self.cost_source_link)
        content.append(cost_card)
        filler_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        filler_card.add_css_class("card")
        filler_card.append(self._section_title("Filler words removed", "Cursay tracks only words it actually removed."))
        self.filler_label = Gtk.Label(label="No filler-word data yet.", xalign=0)
        self.filler_label.set_wrap(True)
        self.filler_label.add_css_class("muted")
        filler_card.append(self.filler_label)
        content.append(filler_card)
        activity_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        activity_card.add_css_class("card")
        activity_card.append(self._section_title("Recent activity"))
        self.activity_label = Gtk.Label(label="No activity yet.", xalign=0)
        self.activity_label.set_wrap(True)
        self.activity_label.add_css_class("muted")
        activity_card.append(self.activity_label)
        content.append(activity_card)
        return scroll

    @staticmethod
    def _metric(parent: Gtk.Box, title: str) -> Gtk.Label:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        card.set_hexpand(True)
        card.add_css_class("metric")
        value = Gtk.Label(label="0", xalign=0)
        value.add_css_class("metric-value")
        card.append(value)
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("muted")
        card.append(label)
        parent.append(card)
        return value

    def _settings(self) -> Gtk.ScrolledWindow:
        scroll = self._page_container()
        content = self._content_box()
        scroll.set_child(content)
        content.append(self._section_title("Settings", "Tune Cursay without weakening Ubuntu's Wayland security."))

        appearance_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        appearance_card.add_css_class("card")
        appearance_card.append(
            self._section_title(
                "Appearance",
                "Follow your system theme automatically, or keep Cursay in light or dark mode.",
            )
        )
        appearance_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        appearance_label = Gtk.Label(label="Theme", xalign=0)
        appearance_label.set_hexpand(True)
        appearance_row.append(appearance_label)
        self.appearance_dropdown = Gtk.DropDown.new_from_strings(["System", "Light", "Dark"])
        appearance = str(self.app.config.get("appearance", "system"))
        selected = APPEARANCE_OPTIONS.index(appearance) if appearance in APPEARANCE_OPTIONS else 0
        self.appearance_dropdown.set_selected(selected)
        self.appearance_dropdown.connect("notify::selected", self._appearance_changed)
        appearance_row.append(self.appearance_dropdown)
        appearance_card.append(appearance_row)
        content.append(appearance_card)

        shortcut_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        shortcut_card.add_css_class("card")
        shortcut_card.append(self._section_title("Global push-to-talk", "The Ubuntu shortcut portal handles press and release events."))
        shortcut_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.shortcut_label = Gtk.Label(label="Ctrl + Space", xalign=0)
        self.shortcut_label.set_hexpand(True)
        shortcut_row.append(self.shortcut_label)
        configure = Gtk.Button(label="Change shortcut")
        configure.connect("clicked", lambda *_: self.app.configure_shortcut())
        shortcut_row.append(configure)
        shortcut_card.append(shortcut_row)
        content.append(shortcut_card)

        behavior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        behavior.add_css_class("card")
        behavior.append(self._section_title("Behavior"))
        self.auto_paste_switch = self._switch_row(
            behavior,
            "Paste automatically",
            "Uses a private keyboard-only input device to send Ctrl+V; no Remote Desktop access is used.",
            bool(self.app.config["auto_paste"]),
            lambda value: self.app.update_setting("auto_paste", value),
        )
        self.fillers_switch = self._switch_row(
            behavior,
            "Remove filler words",
            "Removes clear fillers such as “um” and “uh” without rewriting meaning.",
            bool(self.app.config["remove_fillers"]),
            lambda value: self.app.update_setting("remove_fillers", value),
        )
        self.polish_switch = self._switch_row(
            behavior,
            "Smart polish",
            "Uses the configured OpenAI-compatible text model for Professional, Casual, or Prompt rewrites. "
            "Disabled by default; Code and Raw never use it.",
            bool(self.app.config["smart_polish"]),
            self._set_smart_polish,
        )
        self.recordings_switch = self._switch_row(
            behavior,
            "Keep audio recordings",
            "Off by default. History normally stores text and metadata only.",
            bool(self.app.config["preserve_recordings"]),
            lambda value: self.app.update_setting("preserve_recordings", value),
        )
        self.login_switch = self._switch_row(
            behavior,
            "Launch when I sign in",
            "Runs Cursay in your graphical user session.",
            bool(self.app.config["launch_at_login"]),
            self.app.set_launch_at_login,
        )
        content.append(behavior)

        engine = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        engine.add_css_class("card")
        engine.append(self._section_title("Transcription engine", "Local Whisper by default; custom compatible endpoints are supported."))
        backend_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        backend_label = Gtk.Label(label="Provider", xalign=0)
        backend_label.set_hexpand(True)
        backend_row.append(backend_label)
        self.backend_dropdown = Gtk.DropDown.new_from_strings(["Automatic", "Local Whisper"])
        self.backend_dropdown.set_selected(1 if self.app.config["stt_model"] == "whisper-base.en" else 0)
        self.backend_dropdown.connect("notify::selected", self._backend_changed)
        backend_row.append(self.backend_dropdown)
        engine.append(backend_row)
        self.backend_health = Gtk.Label(label="Checking service…", xalign=0)
        self.backend_health.add_css_class("muted")
        engine.append(self.backend_health)
        content.append(engine)

        updates = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        updates.add_css_class("card")
        updates.append(
            self._section_title(
                "Application updates",
                "Check for a Cursay release and install it after verifying its SHA-256 checksum. "
                "Settings and history are preserved.",
            )
        )
        update_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.update_status_label = Gtk.Label(label=f"Current version: {__version__}", xalign=0)
        self.update_status_label.set_hexpand(True)
        self.update_status_label.set_wrap(True)
        self.update_status_label.add_css_class("muted")
        update_row.append(self.update_status_label)
        self.update_button = Gtk.Button(label="Check for updates")
        self.update_button.connect("clicked", lambda *_: self.app.update_button_clicked())
        update_row.append(self.update_button)
        updates.append(update_row)
        content.append(updates)

        danger = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        danger.add_css_class("card")
        about = Gtk.Label(label=f"Cursay {__version__}\nData: ~/.local/share/cursay", xalign=0)
        about.set_hexpand(True)
        about.add_css_class("muted")
        danger.append(about)
        quit_button = Gtk.Button(label="Quit Cursay")
        quit_button.connect("clicked", lambda *_: self.app.quit())
        danger.append(quit_button)
        content.append(danger)
        return scroll

    @staticmethod
    def _switch_row(
        parent: Gtk.Box,
        title: str,
        subtitle: str,
        active: bool,
        callback: Any,
    ) -> Gtk.Switch:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        row.set_margin_top(8)
        row.set_margin_bottom(8)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        words.set_hexpand(True)
        words.append(Gtk.Label(label=title, xalign=0))
        detail = Gtk.Label(label=subtitle, xalign=0)
        detail.set_wrap(True)
        detail.add_css_class("muted")
        words.append(detail)
        row.append(words)
        switch = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
        switch.connect("notify::active", lambda widget, _param: callback(widget.get_active()))
        row.append(switch)
        parent.append(row)
        return switch

    def _mode_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
        modes = ["professional", "casual", "prompt", "code", "raw"]
        self.app.update_setting("mode", modes[dropdown.get_selected()])
        self._update_mode_detail()

    def _dashboard_polish_changed(self, switch: Gtk.Switch, _param: Any) -> None:
        self._set_smart_polish(switch.get_active())

    def _set_smart_polish(self, enabled: bool) -> None:
        if self._syncing_polish_switches:
            return
        self._syncing_polish_switches = True
        try:
            self.app.update_setting("smart_polish", enabled)
            for name in ("dashboard_polish_switch", "polish_switch"):
                switch = getattr(self, name, None)
                if switch is not None and switch.get_active() != enabled:
                    switch.set_active(enabled)
            self._update_mode_detail()
        finally:
            self._syncing_polish_switches = False

    def _update_mode_detail(self) -> None:
        if not hasattr(self, "mode_detail"):
            return
        mode = str(self.app.config.get("mode", "professional"))
        polish = bool(self.app.config.get("smart_polish", False))
        if mode == "professional":
            detail = (
                "AI rewrite is on: concise workplace prose with complete grammar and punctuation."
                if polish
                else "Basic cleanup only. Turn on Smart polish for an actual professional rewrite."
            )
        elif mode == "casual":
            detail = (
                "AI rewrite is on: friendly conversational prose that keeps contractions and natural wording."
                if polish
                else "Basic cleanup only. Turn on Smart polish for an actual casual rewrite."
            )
        elif mode == "prompt":
            detail = (
                "AI rewrite is on: turns your spoken intent into a clear, ready-to-paste AI prompt."
                if polish
                else "Turn on Smart polish to transform your spoken words into an AI prompt."
            )
        elif mode == "code":
            detail = (
                "Converts spoken punctuation such as “open paren” and “new line.” "
                "AI rewriting is not used."
            )
        else:
            detail = (
                "Keeps the transcript verbatim apart from outer whitespace. "
                "Filler removal and AI rewriting are not used."
            )
        self.mode_detail.set_label(detail)

    def _appearance_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
        self.app.set_appearance(APPEARANCE_OPTIONS[dropdown.get_selected()])

    def _backend_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
        model = "whisper-base.en" if dropdown.get_selected() == 1 else "cursay-stt-auto"
        self.app.update_setting("stt_model", model)
        self.app.check_backend()

    def _page_changed(self, _stack: Gtk.Stack, _param: Any) -> None:
        name = self.stack.get_visible_child_name()
        if name == "history":
            self.refresh_history()
        elif name == "insights":
            self.refresh_insights()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self.set_visible(False)
        self.app.notify("Cursay is still listening", "Hold Ctrl + Space to dictate. Open the launcher to show this window again.")
        return True

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=4))

    def set_update_state(self, message: str, button_label: str, sensitive: bool = True) -> None:
        self.update_status_label.set_label(message)
        self.update_button.set_label(button_label)
        self.update_button.set_sensitive(sensitive)

    def set_status(self, message: str) -> None:
        self.status_label.set_label(message)

    def set_recording(self, active: bool) -> None:
        self.record_button.set_label("Recording… release to finish" if active else "Hold to talk")
        if active:
            self.record_button.add_css_class("recording")
        else:
            self.record_button.remove_css_class("recording")

    def set_result(self, text: str) -> None:
        self.result_view.get_buffer().set_text(text or "No speech detected.")

    def refresh_history(self) -> None:
        child = self.history_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.history_list.remove(child)
            child = next_child
        rows = self.app.store.search(self.history_search.get_text(), 150)
        if not rows:
            empty = Gtk.Label(label="No matching dictations yet.")
            empty.set_margin_top(30)
            empty.set_margin_bottom(30)
            empty.add_css_class("muted")
            self.history_list.append(empty)
            return
        for item in rows:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_hexpand(True)
            row.add_css_class("history-row")
            words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            words.set_hexpand(True)
            words.set_size_request(0, -1)
            text = Gtk.Label(label=item["final_text"], xalign=0)
            text.set_hexpand(True)
            text.set_wrap(True)
            text.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            text.set_max_width_chars(72)
            words.append(text)
            try:
                stamp = datetime.fromisoformat(item["created_at"]).astimezone().strftime("%b %-d, %-I:%M %p")
            except (ValueError, TypeError):
                stamp = item["created_at"]
            meta = Gtk.Label(
                label=f"{stamp}  •  {item['mode'].title()}  •  {item['word_count']} words",
                xalign=0,
            )
            meta.set_hexpand(True)
            meta.set_wrap(True)
            meta.set_max_width_chars(72)
            meta.add_css_class("muted")
            words.append(meta)
            row.append(words)
            copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy")
            copy.connect("clicked", lambda _button, value=item["final_text"]: self.app.copy_text(value))
            row.append(copy)
            delete = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete")
            delete.connect("clicked", lambda _button, row_id=item["id"]: self._delete_history(row_id))
            row.append(delete)
            self.history_list.append(row)

    def _delete_history(self, row_id: int) -> None:
        self.app.store.delete(row_id)
        self.refresh_history()
        self.toast("Dictation removed")

    def refresh_insights(self) -> None:
        stats = self.app.store.stats()
        self.metric_dictations.set_label(f"{stats['dictations']:,}")
        self.metric_words.set_label(f"{stats['words']:,}")
        self.metric_minutes.set_label(f"{stats['seconds'] / 60:.1f}")
        cost = stats["cost"]
        if cost["complete"]:
            cost_value = format_usd(cost["usd"])
        elif cost["has_priced"]:
            cost_value = f"{format_usd(cost['usd'])}+"
        else:
            cost_value = "—"
        self.metric_cost.set_label(cost_value)
        cost_lines = []
        source_url = None
        kind_labels = {
            "estimated": "estimated",
            "reported": "provider reported",
            "mixed": "reported + estimated",
            "partial": "partially reported",
            "local": "local",
            "unavailable": "rate unavailable",
        }
        for item in cost["breakdown"]:
            amount = format_usd(item["cost_usd"]) if item["cost_usd"] is not None else "Cost unavailable"
            cost_lines.append(
                f"{item['provider']} · {item['model']}\n"
                f"{amount} {kind_labels[item['kind']]}  •  {item['dictations']:,} dictations  •  "
                f"{item['seconds'] / 60:.1f} min  •  {item['words']:,} words  •  {item['rate_label']}"
            )
            source_url = source_url or item["source_url"]
        if cost_lines:
            note = "Estimates use recorded audio duration; your provider invoice is the final authority."
            if not cost["complete"]:
                note += f" No published rate is configured for {cost['unpriced_seconds'] / 60:.1f} min."
            self.cost_breakdown_label.set_label("\n\n".join(cost_lines) + f"\n\n{note}")
        else:
            self.cost_breakdown_label.set_label("Cost details will appear after your first dictation.")
        self.cost_source_link.set_visible(bool(source_url))
        if source_url:
            self.cost_source_link.set_uri(source_url)
        if stats["fillers"]:
            self.filler_label.set_label("  •  ".join(f"{word}: {count}" for word, count in stats["fillers"]))
        else:
            self.filler_label.set_label("No filler words have been removed yet.")
        if stats["recent"]:
            self.activity_label.set_label(
                "\n".join(f"{row['day']}: {row['count']} dictations, {row['words']} words" for row in stats["recent"])
            )
        else:
            self.activity_label.set_label("Your daily activity will appear after your first dictation.")


class CursayApplication(Adw.Application):
    def __init__(self, test_mode: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.test_mode = test_mode
        self.config = load_config()
        self.store = HistoryStore()
        self.recorder = PipeWireRecorder()
        self.window: CursayWindow | None = None
        self.latest_text = ""
        self.busy = False
        self.pending_auto_paste = False
        self.pending_auto_paste_text = ""
        self.clipboard_provider: Gdk.ContentProvider | None = None
        self.style_manager: Adw.StyleManager | None = None
        self.virtual_keyboard = VirtualKeyboard()
        self.shortcut_status = "Starting global shortcut…"
        self.shortcuts: GlobalShortcutPortal | None = None
        self.available_update: ReleaseInfo | None = None
        self.checking_for_update = False
        self.pending_update_status = None if test_mode else consume_update_status()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self.style_manager = Adw.StyleManager.get_default()
        self.style_manager.connect("notify::dark", self._theme_changed)
        self._apply_appearance()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.hold()

    def do_activate(self) -> None:
        if self.window is None:
            if not self.test_mode:
                self.shortcuts = GlobalShortcutPortal(
                    self.start_recording,
                    self.stop_recording,
                    self._shortcut_status,
                )
            self.window = CursayWindow(self)
            if self.test_mode:
                GLib.idle_add(self.quit)
            else:
                assert self.shortcuts is not None
                self.shortcuts.start(str(self.config["shortcut"]))
                self.check_backend()
            if self.pending_update_status is not None:
                success, message = self.pending_update_status
                self.window.set_update_state(
                    message,
                    "Check for updates",
                )
                self.window.toast(message)
                if success:
                    self.shortcut_status = f"Ready • Cursay {__version__} is up to date"
                self.pending_update_status = None
        if self.test_mode:
            return
        self.window.present()
        self.window.set_status(self.shortcut_status)

    def do_shutdown(self) -> None:
        self.recorder.cancel()
        if self.shortcuts is not None:
            self.shortcuts.close()
        Adw.Application.do_shutdown(self)

    def _shortcut_status(self, message: str) -> None:
        LOG.info("Shortcut status: %s", message)
        self.shortcut_status = message
        if self.window:
            self.window.set_status(message)

    def configure_shortcut(self) -> None:
        if self.shortcuts is not None:
            self.shortcuts.configure()

    def _paste_pending(self) -> bool:
        pasted = self.virtual_keyboard.paste()
        self.pending_auto_paste = False
        self.pending_auto_paste_text = ""
        self.notify(
            "Dictation ready",
            "Pasted into the active app." if pasted else "Copied to the clipboard; automatic paste was unavailable.",
        )
        return False

    def start_recording(self, source: str = "shortcut") -> None:
        if self.recorder.recording:
            return
        if self.busy:
            return
        try:
            path = self.recorder.start()
        except AudioError as exc:
            self._show_error(str(exc))
            return
        LOG.info("Recording started source=%s path=%s", source, path)
        if self.window:
            self.window.set_recording(True)
            self.window.set_status("Listening… release Ctrl + Space when you are finished")
        self.notify("Listening…", "Keep holding Ctrl + Space; release it when finished.")

    def stop_recording(self, source: str = "shortcut") -> None:
        if not self.recorder.recording:
            return
        LOG.info("Stopping recording source=%s", source)
        try:
            path, duration = self.recorder.stop(bool(self.config["preserve_recordings"]))
        except AudioError as exc:
            self._show_error(str(exc))
            return
        if self.window:
            self.window.set_recording(False)
            self.window.set_status("Transcribing…")
        self.notify("Recording stopped", "Transcribing and preparing your text…")
        self.busy = True
        threading.Thread(target=self._process_recording, args=(path, duration), daemon=True).start()

    def _process_recording(self, path: Path, duration: float) -> None:
        try:
            LOG.info("Transcribing %.2fs of audio with model=%s", duration, self.config["stt_model"])
            result = transcribe(
                path,
                str(self.config["stt_endpoint"]),
                str(self.config["stt_model"]),
                str(self.config["language"]),
            )
            raw = result["text"].strip()
            if not raw:
                raise TranscriptionError("No speech was detected. Check the microphone and try again.")
            mode = str(self.config["mode"])
            final, metadata = clean_transcript(
                raw,
                mode,
                bool(self.config["remove_fillers"]),
            )
            polish_warning: str | None = None
            if should_polish(mode, bool(self.config["smart_polish"])):
                try:
                    final = polish_transcript(
                        final,
                        mode,
                        str(self.config["polish_endpoint"]),
                        str(self.config["polish_model"]),
                    )
                except PolishError as exc:
                    polish_warning = str(exc)
                    LOG.warning("%s", polish_warning)
            recording_path = str(path) if bool(self.config["preserve_recordings"]) else None
            self.store.add(
                raw_text=raw,
                final_text=final,
                mode=mode,
                language=str(result.get("language") or self.config["language"]),
                duration_seconds=float(result.get("duration") or duration),
                provider=str(result.get("provider") or "unknown"),
                model=str(result.get("model") or self.config["stt_model"]),
                fillers_removed=list(metadata["fillers_removed"]),
                recording_path=recording_path,
                cost_usd=reported_cost_usd(result),
            )
            GLib.idle_add(
                self._completed,
                final,
                str(result.get("provider") or "speech service"),
                polish_warning,
            )
        except (TranscriptionError, OSError, ValueError) as exc:
            GLib.idle_add(self._failed, str(exc))
        finally:
            if not bool(self.config["preserve_recordings"]):
                path.unlink(missing_ok=True)

    def _completed(self, text: str, provider: str, polish_warning: str | None = None) -> bool:
        LOG.info("Dictation completed provider=%s words=%s", provider, len(text.split()))
        self.busy = False
        self.latest_text = text
        self.copy_text(text, quiet=True)
        if self.window:
            self.window.set_result(text)
            status = (
                "Ready • basic cleanup used; Smart polish was unavailable"
                if polish_warning
                else f"Ready • last transcription: {provider}"
            )
            self.window.set_status(status)
            self.window.refresh_history()
            if polish_warning:
                self.window.toast(polish_warning)
        if bool(self.config["auto_paste"]):
            self.pending_auto_paste = True
            self.pending_auto_paste_text = text
            GLib.timeout_add(80, self._verify_clipboard_for_paste, 0)
        suffix = "Clipboard updated; automatic paste is queued." if self.pending_auto_paste else "Copied to the clipboard."
        if polish_warning:
            suffix += " Smart polish was unavailable, so basic cleanup was used."
        self.notify("Dictation ready", suffix)
        return False

    def _verify_clipboard_for_paste(self, attempt: int) -> bool:
        if not self.pending_auto_paste or not self.pending_auto_paste_text:
            return False
        try:
            result = subprocess.run(
                [str(WL_PASTE), "--no-newline"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                check=False,
            )
            current = result.stdout.decode("utf-8") if result.returncode == 0 else ""
            if result.returncode != 0:
                LOG.warning("Wayland clipboard readback failed: %s", result.stderr.decode("utf-8", "replace").strip())
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
            LOG.warning("Wayland clipboard readback failed: %s", exc)
            current = ""
        expected = self.pending_auto_paste_text
        if not self.pending_auto_paste or not expected:
            return False
        if current == expected:
            LOG.info("Wayland clipboard readback verified (%s characters)", len(expected))
            GLib.timeout_add(120, self._paste_pending)
            return False
        if attempt < 8:
            LOG.info("Clipboard has not updated yet; retrying readback attempt=%s", attempt + 1)
            GLib.timeout_add(90, self._verify_clipboard_for_paste, attempt + 1)
            return False
        LOG.warning("Clipboard verification failed; refusing to paste stale clipboard contents")
        self.pending_auto_paste = False
        self.pending_auto_paste_text = ""
        if self.window:
            self.window.toast("Clipboard did not update; automatic paste was cancelled")
        return False

    def _failed(self, message: str) -> bool:
        LOG.warning("Dictation failed: %s", message)
        self.busy = False
        self._show_error(message)
        return False

    def _show_error(self, message: str) -> None:
        if self.window:
            self.window.set_recording(False)
            self.window.set_status("Ready • something needs attention")
            self.window.toast(message)
        self.notify("Cursay needs attention", message)

    def copy_text(self, text: str, quiet: bool = False) -> None:
        published = False
        try:
            result = subprocess.run(
                [str(WL_COPY), "--type", "text/plain;charset=utf-8"],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                # wl-copy forks a clipboard-serving child. A PIPE would stay
                # open in that child and make subprocess.run wait forever.
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            published = result.returncode == 0
            if not published:
                LOG.warning("wl-copy failed with status %s", result.returncode)
        except (OSError, subprocess.TimeoutExpired) as exc:
            LOG.warning("wl-copy unavailable: %s", exc)

        if not published:
            # Keep a GTK fallback for installations where the bundled Wayland
            # helper cannot run (for example, an X11 session).
            display = Gdk.Display.get_default()
            clipboard = display.get_clipboard()
            self.clipboard_provider = Gdk.ContentProvider.new_for_bytes(
                "text/plain;charset=utf-8",
                GLib.Bytes.new(text.encode("utf-8")),
            )
            published = clipboard.set_content(self.clipboard_provider)
            display.flush()
        LOG.info("Published Wayland clipboard text characters=%s accepted=%s", len(text), published)
        if self.window and not quiet:
            self.window.toast("Copied to clipboard")

    def copy_latest(self) -> None:
        if self.latest_text:
            self.copy_text(self.latest_text)
        elif self.window:
            self.window.toast("There is no dictation to copy yet")

    def notify(self, title: str, body: str) -> None:
        if not bool(self.config.get("show_notifications", True)):
            return
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_icon(Gio.ThemedIcon.new("audio-input-microphone-symbolic"))
        self.send_notification("cursay-status", notification)

    def update_setting(self, key: str, value: Any) -> None:
        self.config[key] = value
        save_config(self.config)

    def is_dark_theme(self) -> bool:
        return bool(self.style_manager and self.style_manager.get_dark())

    def set_appearance(self, appearance: str) -> None:
        if appearance not in APPEARANCE_OPTIONS:
            appearance = "system"
        self.update_setting("appearance", appearance)
        self._apply_appearance()
        if self.window:
            self.window.toast(f"Appearance set to {appearance.title()}")

    def _apply_appearance(self) -> None:
        if self.style_manager is None:
            return
        schemes = {
            "system": Adw.ColorScheme.DEFAULT,
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }
        appearance = str(self.config.get("appearance", "system"))
        self.style_manager.set_color_scheme(schemes.get(appearance, Adw.ColorScheme.DEFAULT))
        if self.window:
            self.window.sync_theme(self.style_manager.get_dark())

    def _theme_changed(self, style_manager: Adw.StyleManager, _param: Any) -> None:
        if self.window:
            self.window.sync_theme(style_manager.get_dark())

    def set_launch_at_login(self, enabled: bool) -> None:
        unit = "cursay.service"
        command = ["systemctl", "--user", "enable" if enabled else "disable", unit]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            self.update_setting("launch_at_login", enabled)
            if self.window:
                self.window.toast("Launch at login enabled" if enabled else "Launch at login disabled")
        elif self.window:
            self.window.toast((result.stderr or "Could not update startup setting").strip())

    def update_button_clicked(self) -> None:
        if self.available_update is None:
            self.check_for_updates()
            return
        if not self.available_update.can_install:
            try:
                Gio.AppInfo.launch_default_for_uri(self.available_update.page_url, None)
            except GLib.Error as exc:
                if self.window:
                    self.window.toast(f"Could not open the release page: {exc.message}")
            return
        if self.window:
            self.window.set_update_state("Starting the updater…", "Starting…", False)
        try:
            launch_update(self.available_update)
        except UpdateError as exc:
            if self.window:
                self.window.set_update_state(str(exc), "Try again", True)
                self.window.toast(str(exc))
            return
        if self.window:
            self.window.set_update_state(
                "Downloading and installing the update. Cursay will restart when it is ready.",
                "Updating…",
                False,
            )
            self.window.toast("Update started. Cursay will restart automatically.")
        GLib.timeout_add(1000, self._quit_for_update)

    def _quit_for_update(self) -> bool:
        self.quit()
        return False

    def check_for_updates(self) -> None:
        if self.checking_for_update:
            return
        self.checking_for_update = True
        self.available_update = None
        if self.window:
            self.window.set_update_state("Checking GitHub for the latest release…", "Checking…", False)

        def worker() -> None:
            try:
                release = fetch_latest_release()
                GLib.idle_add(self._update_checked, release, None)
            except NoReleaseAvailable as exc:
                GLib.idle_add(self._no_release_available, str(exc))
            except UpdateError as exc:
                GLib.idle_add(self._update_checked, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _no_release_available(self, message: str) -> bool:
        self.checking_for_update = False
        if self.window:
            self.window.set_update_state(message, "Check again", True)
        return False

    def _update_checked(self, release: ReleaseInfo | None, error: str | None) -> bool:
        self.checking_for_update = False
        if not self.window:
            return False
        if error is not None or release is None:
            self.window.set_update_state(error or "Could not check for updates", "Try again", True)
            return False
        try:
            newer = is_newer_version(release.version, __version__)
        except UpdateError as exc:
            self.window.set_update_state(str(exc), "Try again", True)
            return False
        if not newer:
            self.window.set_update_state(f"Cursay {__version__} is up to date.", "Check again", True)
            return False
        self.available_update = release
        if release.can_install:
            self.window.set_update_state(
                f"Cursay {release.version} is available. The download will be verified before installation.",
                f"Update to {release.version}",
                True,
            )
        else:
            self.window.set_update_state(
                f"Cursay {release.version} is available, but its automatic-update files are not ready.",
                "View release",
                True,
            )
        return False

    def check_backend(self) -> None:
        def worker() -> None:
            result = health(str(self.config["stt_endpoint"]))
            GLib.idle_add(self._backend_checked, result)

        threading.Thread(target=worker, daemon=True).start()

    def _backend_checked(self, result: dict[str, Any]) -> bool:
        if self.window:
            if result.get("status") == "ok":
                selected = result.get("selected_provider", "ready")
                local = result.get("local_model", "Whisper")
                self.window.backend_health.set_label(f"Service healthy • selected: {selected} • fallback: {local}")
            else:
                self.window.backend_health.set_label("Speech service is unavailable")
        return False


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    application = CursayApplication()
    return int(application.run(None))


def smoke_test() -> int:
    """Build every widget and exercise application startup without opening portals."""
    logging.basicConfig(level=logging.INFO)
    application = CursayApplication(test_mode=True)
    return int(application.run(None))
