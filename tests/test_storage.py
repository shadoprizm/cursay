from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cursay.storage import HistoryStore


class StorageTests(unittest.TestCase):
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
            store.delete(row_id)
            self.assertEqual(store.search(), [])


if __name__ == "__main__":
    unittest.main()
