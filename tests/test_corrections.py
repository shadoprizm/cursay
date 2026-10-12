from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cursay.app import CursayApplication
from cursay.cleanup import clean_transcript
from cursay.corrections import apply_replacements, suggest_replacements
from cursay.insights import dictation_word_count, words_per_minute
from cursay.storage import HistoryStore


class CorrectionTests(unittest.TestCase):
    def test_whole_phrases_longest_first_and_no_cascading(self) -> None:
        rules = [
            {"source": "say", "target": "speak"},
            {"source": "curse say", "target": "Cursay"},
            {"source": "Cursay", "target": "Other"},
        ]
        self.assertEqual(
            apply_replacements("CURSE SAY, say, essay and Cursay.", rules),
            "Cursay, speak, essay and Other.",
        )

    def test_unicode_and_literal_regex_characters(self) -> None:
        rules = [{"source": "Straße", "target": "street"}, {"source": "c++", "target": "C++"}]
        self.assertEqual(apply_replacements("Straße c++", rules), "street C++")

    def test_suggestions_preserve_multiword_spacing_and_ignore_punctuation_and_deletions(self) -> None:
        self.assertEqual(
            suggest_replacements("Send it to curse say, please.", "Send it to Cursay, please."),
            [("curse say", "Cursay")],
        )
        self.assertEqual(suggest_replacements("Hello, Jordan.", "Hello Jordan!"), [])
        self.assertEqual(suggest_replacements("Hello um Jordan.", "Hello Jordan."), [])
        self.assertEqual(suggest_replacements("Hello.", "Hello there."), [])

    def test_basic_cleanup_keeps_meaningful_phrases(self) -> None:
        text, metadata = clean_transcript("um, do you know what I mean about the ER?", "professional")
        self.assertEqual(text, "Do you know what I mean about the ER?")
        self.assertEqual(metadata["fillers_removed"], ["um"])

    def test_correction_persists_and_keeps_original_with_only_selected_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            row_id = store.add("curse say", "Curse say.", "professional", "en", 2, "local", "whisper")
            store.save_correction(row_id, "Cursay is ready.", [("curse say", "Cursay")])
            store.save_correction(row_id, "Cursay is now ready.", [])
            reopened = HistoryStore(store.path)
            row = reopened.get(row_id)
            self.assertEqual(row["raw_text"], "curse say")
            self.assertEqual(row["original_final_text"], "Curse say.")
            self.assertEqual(row["final_text"], "Cursay is now ready.")
            self.assertEqual(row["word_count"], 4)
            self.assertIsNotNone(row["corrected_at"])
            self.assertEqual(apply_replacements("Use curse say.", reopened.replacements()), "Use Cursay.")

    def test_invalid_or_deleted_correction_does_not_save_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            row_id = store.add("wrong", "Wrong.", "professional", "en", 2, "local", "whisper")
            with self.assertRaises(ValueError):
                store.save_correction(row_id, "Fixed.", [("wrong", "right"), ("", "invalid")])
            self.assertEqual(store.get(row_id)["final_text"], "Wrong.")
            self.assertEqual(store.replacements(), [])

            store.delete(row_id)
            with self.assertRaises(ValueError):
                store.save_correction(row_id, "Fixed.", [("wrong", "right")])
            self.assertEqual(store.replacements(), [])

    def test_typed_edits_preserve_session_period_daily_and_all_time_voice_speed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            row_id = store.add("two words", "Two words.", "professional", "en", 60, "local", "whisper")
            initial = store.stats()["speed"]
            for corrected in ("Many more words added after recording ended.", "Short."):
                store.save_correction(row_id, corrected, [])
                row = store.get(row_id)
                self.assertEqual(row["word_count"], len(corrected.split()))
                self.assertEqual(dictation_word_count(row), 2)
                self.assertEqual(words_per_minute(dictation_word_count(row), row["duration_seconds"]), 2)
                speed = store.stats()["speed"]
                self.assertEqual(speed["wpm"], initial["wpm"])
                self.assertEqual(speed["lifetime_wpm"], initial["lifetime_wpm"])
                self.assertEqual(speed["latest_wpm"], initial["latest_wpm"])
                self.assertEqual(speed["daily"], initial["daily"])

    def test_rule_can_be_updated_disabled_reenabled_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            store.save_replacement(" Wrong ", "Right")
            store.save_replacement("wrong", "Better")
            self.assertEqual(len(store.replacements()), 1)
            row_id = store.replacements()[0]["id"]
            store.set_replacement_enabled(row_id, False)
            self.assertEqual(apply_replacements("Wrong", store.replacements()), "Wrong")
            store.set_replacement_enabled(row_id, True)
            self.assertEqual(apply_replacements("Wrong", store.replacements()), "Better")
            store.delete_replacement(row_id)
            self.assertEqual(store.replacements(), [])

    def test_next_capture_uses_correction_after_polish_and_raw_bypasses_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            store.save_replacement("curse say", "Cursay")
            app = SimpleNamespace(
                config={
                    "stt_provider": "local", "local_stt_endpoint": "http://localhost/transcribe",
                    "local_stt_model": "whisper", "language": "en", "mode": "professional",
                    "remove_fillers": True, "smart_polish": True, "preserve_recordings": False,
                    "memory_sync": False, "polish_endpoint": "http://localhost/polish", "polish_model": "test",
                },
                store=store, _completed=Mock(), _failed=Mock(), recording_private=False,
                recording_memory=False, recording_memory_scope=None, sync_memory=Mock(),
            )
            audio = Path(directory) / "recording.wav"
            for mode in ("professional", "raw"):
                app.config["mode"] = mode
                audio.touch()
                with (
                    patch("cursay.app.transcribe", return_value={"text": "use curse say"}),
                    patch("cursay.app.polish_transcript", return_value="Try curse say.") as polish,
                    patch("cursay.app.GLib.idle_add") as idle,
                ):
                    CursayApplication._process_recording(app, audio, 2)
                expected = "Try Cursay." if mode == "professional" else "use curse say"
                self.assertEqual(idle.call_args.args[1], expected)
                row_id = idle.call_args.args[4]
                self.assertEqual(store.get(row_id)["final_text"], expected)
                self.assertEqual(polish.call_count, int(mode == "professional"))
                app._failed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
