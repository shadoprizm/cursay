from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cursay.config import APPEARANCE_OPTIONS, DEFAULT_CONFIG, load_config, migrate_legacy_data, save_config


class ConfigTests(unittest.TestCase):
    def test_round_trip_and_unknown_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            value = dict(DEFAULT_CONFIG)
            value["mode"] = "code"
            value["unknown"] = "discard me"
            save_config(value, path)
            loaded = load_config(path)
            self.assertEqual(loaded["mode"], "code")
            self.assertNotIn("unknown", loaded)

    def test_malformed_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_config(path)["mode"], DEFAULT_CONFIG["mode"])

    def test_appearance_defaults_to_system_and_round_trips(self) -> None:
        self.assertEqual(DEFAULT_CONFIG["appearance"], "system")
        self.assertEqual(APPEARANCE_OPTIONS, ("system", "light", "dark"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            value = dict(DEFAULT_CONFIG)
            value["appearance"] = "dark"
            save_config(value, path)
            self.assertEqual(load_config(path)["appearance"], "dark")

    def test_invalid_appearance_falls_back_to_system(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"appearance": "sepia"}', encoding="utf-8")
            self.assertEqual(load_config(path)["appearance"], "system")

    def test_existing_custom_endpoint_is_preserved_as_custom_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                '{"stt_endpoint":"https://speech.example/v1/audio/transcriptions","stt_model":"private-model"}',
                encoding="utf-8",
            )
            loaded = load_config(path)
            self.assertEqual(loaded["stt_provider"], "custom")
            self.assertEqual(loaded["stt_endpoint"], "https://speech.example/v1/audio/transcriptions")
            self.assertEqual(loaded["stt_model"], "private-model")

    def test_existing_default_endpoint_migrates_to_local_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                '{"stt_endpoint":"http://127.0.0.1:8765/v1/audio/transcriptions","stt_model":"whisper-base.en"}',
                encoding="utf-8",
            )
            self.assertEqual(load_config(path)["stt_provider"], "local")

    def test_migrates_legacy_profile_without_removing_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_config = root / "legacy-config"
            legacy_data = root / "legacy-data"
            config = root / "config"
            data = root / "data"
            legacy_config.mkdir()
            legacy_data.mkdir()
            (legacy_config / "config.json").write_text('{"mode": "casual"}\n', encoding="utf-8")
            (legacy_data / "history.db").write_bytes(b"history")

            self.assertTrue(migrate_legacy_data(legacy_config, legacy_data, config, data))
            self.assertEqual((config / "config.json").read_text(encoding="utf-8"), '{"mode": "casual"}\n')
            self.assertEqual((data / "history.db").read_bytes(), b"history")
            self.assertTrue((legacy_config / "config.json").exists())
            self.assertTrue((legacy_data / "history.db").exists())


if __name__ == "__main__":
    unittest.main()
