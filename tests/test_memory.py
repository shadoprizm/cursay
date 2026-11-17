import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from cursay.memory import MemorySync, is_private_capture
from cursay.storage import HistoryStore
from cursay.cloud import CloudError


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

    def test_disabled_server_reports_unavailability_without_discarding_queue(self):
        self.memory.sync()
        self.memory.enqueue(self.row(), self.memory.capture_scope())
        self.cloud.memory.side_effect = CloudError("private server detail", status=503, code="memory_not_available")
        self.assertEqual(
            self.memory.sync(),
            "Account Memory is unavailable on the server. Local dictation is still available.",
        )
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_outbox").fetchone()[0], 1)

    def test_temporary_failure_remains_pending_and_recovers(self):
        self.cloud.memory.side_effect = CloudError("private server detail", status=503, code="memory_unavailable")
        self.assertEqual(self.memory.sync(), "Memory sync pending. Local dictation is still available.")
        self.cloud.memory.side_effect = None
        self.assertEqual(self.memory.sync(), "Memory synced · 0 approved words")

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


    def test_idle_backoff_is_bounded_and_foreground_bypasses_it(self):
        with patch("cursay.memory.time.monotonic", return_value=100) as clock:
            self.memory.sync()
            self.assertEqual(self.cloud.memory.call_count, 1)
            now = 100
            for delay in (60, 120, 300, 900, 900):
                clock.return_value = now + delay - 1
                count = self.cloud.memory.call_count
                self.memory.sync(background=True)
                self.assertEqual(self.cloud.memory.call_count, count)
                now += delay
                clock.return_value = now
                self.memory.sync(background=True)
                self.assertEqual(self.cloud.memory.call_count, count + 1)
            self.memory.sync()
            self.assertEqual(self.cloud.memory.call_count, count + 2)

    def test_compact_bootstrap_uses_one_request(self):
        self.memory.sync()
        self.assertEqual(self.cloud.memory.call_count, 1)

    def test_nonadvancing_pagination_fails_bounded(self):
        self.page.update(cursor=5, has_more=True)
        self.assertIn("pending", self.memory.sync())
        self.assertEqual(self.cloud.memory.call_count, 2)

    def test_paginated_tombstone_prevents_upload(self):
        self.memory.sync()
        row = self.row()
        self.memory.enqueue(row, self.memory.capture_scope())
        first = dict(self.page, cursor=3, has_more=True)
        last = dict(self.page, cursor=4, captures=[{"id": row["memory_id"], "deleted_at": "today"}])
        self.cloud.memory.side_effect = [first, last]
        self.memory.sync()
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_outbox").fetchone()[0], 0)
        self.assertEqual(self.memory.state()["cursor"], 4)

    def test_offline_queue_survives_restart(self):
        self.memory.sync()
        self.memory.enqueue(self.row(), self.memory.capture_scope())
        self.cloud.memory.side_effect = RuntimeError("offline")
        self.memory.sync()
        restarted = MemorySync(self.store, self.cloud)
        self.cloud.memory.side_effect = None
        restarted.sync()
        self.assertEqual(self.cloud.memory.call_args.args[0]["action"], "save")
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_outbox").fetchone()[0], 0)

    def test_local_delete_during_upload_is_not_lost(self):
        self.memory.sync()
        row = self.row()
        self.memory.enqueue(row, self.memory.capture_scope())
        def during_upload(*args, **kwargs):
            if args:
                self.memory.delete(row)
            return self.page
        self.cloud.memory.side_effect = during_upload
        self.memory.sync()
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT action FROM memory_outbox").fetchone()[0], "delete")
