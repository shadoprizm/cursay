from __future__ import annotations

import unittest
from unittest.mock import Mock

from cursay.app import CursayApplication, CursayWindow
from cursay.correction_window import CorrectionWindow
from cursay.corrections import apply_replacements

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class CorrectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            raise unittest.SkipTest("GTK interface tests require an available display")

    def setUp(self) -> None:
        self.parent = Gtk.Window()
        self.save = Mock()
        self.dialog = CorrectionWindow(
            self.parent, {"id": 1, "raw_text": "curse say", "final_text": "Curse say."}, self.save,
        )

    def tearDown(self) -> None:
        self.dialog.destroy()
        self.parent.destroy()

    def test_review_requires_explicit_selection_and_edit_invalidates_it(self) -> None:
        self.dialog.editor.get_buffer().set_text("Cursay.")
        self.dialog.review()
        self.assertEqual(len(self.dialog.choices), 1)
        choice, pair = self.dialog.choices[0]
        self.assertEqual(pair, ("Curse say", "Cursay"))
        self.assertFalse(choice.get_active())
        choice.set_active(True)
        self.dialog.editor.get_buffer().set_text("Another product.")
        self.assertEqual(self.dialog.choices, [])
        self.dialog.save_changes()
        self.save.assert_called_once_with(1, "Another product.", [])

    def test_selected_rule_is_saved_with_corrected_text(self) -> None:
        self.dialog.editor.get_buffer().set_text("Cursay.")
        self.dialog.review()
        self.dialog.choices[0][0].set_active(True)
        self.dialog.save_changes()
        self.save.assert_called_once_with(1, "Cursay.", [("Curse say", "Cursay")])

    def test_saving_failure_stays_visible(self) -> None:
        self.save.side_effect = ValueError("This dictation was deleted.")
        self.dialog.save_changes()
        self.assertEqual(self.dialog.error.get_label(), "This dictation was deleted.")

    def test_full_app_save_updates_history_latest_clipboard_and_rule_manager(self) -> None:
        app = CursayApplication(test_mode=True)
        app.register(None)
        app.config["auto_paste"] = False
        window = CursayWindow(app)
        app.window = window
        app.copy_text = Mock()
        app.notify = Mock()
        app.sync_memory = Mock()
        try:
            row_id = app.store.add("curse say", "Curse say.", "professional", "en", 2, "local", "whisper")
            app._completed("Curse say.", "local", row_id=row_id)
            app.pending_auto_paste = True
            app.pending_auto_paste_text = "Curse say."
            window._save_correction(row_id, "Cursay.", [("Curse say", "Cursay")])
            self.assertEqual(app.latest_text, "Cursay.")
            self.assertEqual(app.store.get(row_id)["final_text"], "Cursay.")
            app.copy_text.assert_called_with("Cursay.", quiet=True)
            self.assertFalse(app.pending_auto_paste)
            self.assertEqual(app.pending_auto_paste_text, "")
            self.assertEqual(apply_replacements("Curse say.", app.store.replacements()), "Cursay.")
            app.sync_memory.assert_not_called()
            rule_row = window.correction_list.get_first_child()
            rule_row.get_first_child().set_active(False)
            self.assertEqual(apply_replacements("Curse say.", app.store.replacements()), "Curse say.")
            window._delete_replacement(app.store.replacements()[0]["id"])
            self.assertEqual(app.store.replacements(), [])
            window.correction_source.set_text("Curse say")
            window.correction_target.set_text("Cursay")
            window._add_replacement()
            self.assertEqual(apply_replacements("Curse say.", app.store.replacements()), "Cursay.")
        finally:
            window.destroy()
            app._smoke_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
