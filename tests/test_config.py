from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cursay.config import DEFAULT_CONFIG, load_config, migrate_legacy_data, save_config


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
