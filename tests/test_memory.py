import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from cursay.memory import MemorySync, is_private_capture
from cursay.storage import HistoryStore


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = HistoryStore(Path(self.directory.name) / "history.db")
        self.cloud = Mock()
        self.memory = MemorySync(self.store, self.cloud)
        self.page = {
            "settings": {"account_id": "a", "epoch": "e", "enabled": True},
            "captures": [],
            "cursor": 0,
            "has_more": False,
            "items": [],
        }
        self.cloud.memory.return_value = self.page

    def row(self):
        row_id = self.store.add("hello", "Hello", "raw", "en", 1, "test", "test")
        return self.store.get(row_id)

    def test_existing_integer_id_and_stable_uuid_are_preserved(self):
        row = self.row()
        self.assertIsInstance(row["id"], int)
        self.assertEqual(HistoryStore(self.store.path).get(row["id"])["memory_id"], row["memory_id"])

    def test_does_not_import_history_or_capture_without_consent(self):
        row = self.row()
        self.memory.enqueue(row, self.memory.capture_scope())
        self.memory.sync()
        self.assertFalse(any(call.args for call in self.cloud.memory.call_args_list))

    def test_switch_accounts_or_epoch_discards_old_outbox(self):
        self.memory.sync()
        self.memory.enqueue(self.row(), self.memory.capture_scope())
        self.page["settings"]["account_id"] = "b"
        self.memory.sync()
        self.assertFalse(any(call.args for call in self.cloud.memory.call_args_list))

    def test_tombstone_wins_before_pending_upload(self):
        self.memory.sync()
        row = self.row()
        self.memory.enqueue(row, self.memory.capture_scope())
        self.page["captures"] = [{"id": row["memory_id"], "deleted_at": "today"}]
        self.memory.sync()
        self.assertFalse(any(call.args for call in self.cloud.memory.call_args_list))

    def test_deletion_precedes_queued_capture(self):
        self.memory.sync()
        row = self.row()
        self.memory.enqueue(row, self.memory.capture_scope())
        self.memory.delete(row)
        self.memory.sync()
        self.assertEqual(self.cloud.memory.call_args.args[0]["action"], "delete")

    def test_guessed_words_are_not_applied(self):
        self.page["items"] = [
            {"kind": "vocabulary", "status": "confirmed", "preferred": "Cursay"},
            {"kind": "vocabulary", "status": "suggested", "preferred": "Wrong"},
        ]
        self.memory.sync()
        self.assertEqual(self.memory.approved_vocabulary(), ["Cursay"])

    def test_signout_wins_over_inflight_snapshot(self):
        self.memory.sync()
        self.memory.enqueue(self.row(), self.memory.capture_scope())

        def reset_during_request(*args, **kwargs):
            self.memory.reset()
            return self.page

        self.cloud.memory.side_effect = reset_during_request
        self.assertEqual(self.memory.sync(), "Memory sync canceled")
        self.assertEqual(self.memory.state(), {})
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_outbox").fetchone()[0], 0)

    def test_capture_is_not_enrolled_in_a_changed_account(self):
        self.memory.sync()
        scope = self.memory.capture_scope()
        self.page["settings"]["account_id"] = "b"
        self.memory.sync()
        self.memory.enqueue(self.row(), scope)
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_outbox").fetchone()[0], 0)

    def test_exclusions_fail_closed_when_identity_unknown(self):
        self.assertTrue(is_private_capture(False, "secret.app"))
        self.assertTrue(is_private_capture(False, "secret.app", "secret.app"))
        self.assertFalse(is_private_capture(False, "secret.app", "other.app"))
        self.assertFalse(is_private_capture(False, ""))
