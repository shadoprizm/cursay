from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from cursay.storage import HistoryStore


class StorageTests(unittest.TestCase):
    def test_existing_database_is_migrated_for_reported_costs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            connection = sqlite3.connect(path)
            connection.execute(
                """
                CREATE TABLE dictations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    final_text TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    language TEXT,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    provider TEXT,
                    model TEXT,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    fillers_removed_json TEXT NOT NULL DEFAULT '[]',
                    recording_path TEXT
                )
                """
            )
            connection.commit()
            connection.close()

            HistoryStore(path)

            connection = sqlite3.connect(path)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(dictations)")}
            connection.close()
            self.assertIn("cost_usd", columns)

    def test_add_search_stats_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            row_id = store.add(
                raw_text="um hello there",
                final_text="Hello there.",
                mode="professional",
                language="en",
                duration_seconds=2.5,
                provider="test",
                model="test-model",
                fillers_removed=["um"],
            )
            rows = store.search("hello")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], row_id)
            stats = store.stats()
            self.assertEqual(stats["dictations"], 1)
            self.assertEqual(stats["words"], 2)
            self.assertEqual(stats["fillers"], [("um", 1)])
            self.assertFalse(stats["cost"]["complete"])
            store.delete(row_id)
            self.assertEqual(store.search(), [])

    def test_xai_cost_is_estimated_from_audio_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            store.add(
                raw_text="hello",
                final_text="Hello.",
                mode="professional",
                language="en",
                duration_seconds=3600,
                provider="xai",
                model="grok-voice-transcribe-2.0",
            )
            cost = store.stats()["cost"]
            self.assertAlmostEqual(cost["usd"], 0.10)
            self.assertTrue(cost["estimated"])
            self.assertTrue(cost["complete"])
            self.assertEqual(cost["breakdown"][0]["rate_label"], "$0.10/hour REST")

    def test_provider_reported_cost_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            store.add(
                raw_text="hello",
                final_text="Hello.",
                mode="professional",
                language="en",
                duration_seconds=3600,
                provider="xai",
                model="grok-voice-transcribe-2.0",
                cost_usd=0.25,
            )
            cost = store.stats()["cost"]
            self.assertAlmostEqual(cost["usd"], 0.25)
            self.assertFalse(cost["estimated"])
            self.assertTrue(cost["has_reported"])
            self.assertEqual(cost["breakdown"][0]["kind"], "reported")


if __name__ == "__main__":
    unittest.main()
