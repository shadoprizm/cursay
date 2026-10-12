from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cursay.app import CursayApplication


class AppInsightsTests(unittest.TestCase):
    def test_saved_duration_uses_recording_time_instead_of_provider_duration(self) -> None:
        app = SimpleNamespace(
            config={
                "stt_provider": "local", "local_stt_endpoint": "http://localhost/transcribe",
                "local_stt_model": "whisper", "language": "en", "mode": "raw",
                "remove_fillers": False, "smart_polish": False, "preserve_recordings": False, "memory_sync": False,
            },
            store=Mock(), _completed=Mock(), _failed=Mock(),
            recording_private=False, recording_memory=False, recording_memory_scope=None, sync_memory=Mock(),
        )
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "recording.wav"
            audio.touch()
            with (
                patch("cursay.app.transcribe", return_value={"text": "Hello there", "duration": 1}),
                patch("cursay.app.GLib.idle_add") as idle,
            ):
                CursayApplication._process_recording(app, audio, 30)
            self.assertEqual(app.store.add.call_args.kwargs["duration_seconds"], 30)
            self.assertEqual(idle.call_args.args[0], app._completed)
            self.assertFalse(audio.exists())

    def test_completion_refreshes_insights(self) -> None:
        app = SimpleNamespace(
            config={"auto_paste": False}, busy=True, latest_text="", pending_auto_paste=False,
            window=Mock(), copy_text=Mock(), notify=Mock(),
        )
        CursayApplication._completed(app, "Hello there", "local")
        app.window.refresh_insights.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
