from __future__ import annotations
import json
import threading
import time
from typing import Any
from .storage import HistoryStore


class MemorySync:
    """Future-capture-only, account-bound outbox, separate from local history."""

    def __init__(self, store: HistoryStore, cloud: Any) -> None:
        self.store = store
        self.cloud = cloud
        self._sync_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._generation = 0
        self._idle_step = 0
        self._next_poll = 0.0
        self._last_status = "Memory sync pending"
        self._rerun = False
        with store.connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS memory_state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_outbox (id TEXT PRIMARY KEY, account TEXT NOT NULL, epoch TEXT NOT NULL,
                    action TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    def state(self) -> dict[str, Any]:
        with self.store.connect() as c:
            row = c.execute("SELECT value FROM memory_state WHERE id=1").fetchone()
        return json.loads(row[0]) if row else {}

    def reset(self) -> None:
        with self._state_lock:
            self._generation += 1
            self._idle_step = 0
            self._next_poll = 0.0
            self._clear()

    def _clear(self) -> None:
        with self.store.connect() as c:
            c.execute("DELETE FROM memory_state")
            c.execute("DELETE FROM memory_outbox")

    def approved_vocabulary(self) -> list[str]:
        return self.state().get("vocabulary", [])[:100]

    def capture_scope(self) -> str | None:
        state = self.state()
        return (
            f"{state['account']}:{state['epoch']}" if state.get("enabled") and state.get("account") else None
        )

    def enqueue(self, row: dict[str, Any], expected_scope: str | None) -> None:
        with self._state_lock:
            state = self.state()
            if expected_scope is None or expected_scope != self.capture_scope():
                return
            payload = {
                "action": "save",
                "capture": {
                    "id": row["memory_id"],
                    "epoch": state["epoch"],
                    "revision": 1,
                    "original_text": row["raw_text"],
                    "final_text": row["final_text"],
                    "mode": row["mode"],
                    "platform": "ubuntu",
                    "created_at": row["created_at"],
                    "project_id": None,
                },
            }
            with self.store.connect() as c:
                c.execute(
                    "INSERT OR IGNORE INTO memory_outbox VALUES(?,?,?,?,?)",
                    (row["memory_id"], state["account"], state["epoch"], "save", json.dumps(payload)),
                )

    def delete(self, row: dict[str, Any]) -> None:
        with self._state_lock:
            state = self.state()
            if not state.get("account"):
                return
            with self.store.connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO memory_outbox VALUES(?,?,?,?,?)",
                    (
                        row["memory_id"],
                        state["account"],
                        state["epoch"],
                        "delete",
                        json.dumps({"action": "delete", "id": row["memory_id"]}),
                    ),
                )

    def sync(self, *, background: bool = False) -> str:
        with self._state_lock:
            if background and time.monotonic() < self._next_poll:
                return self._last_status
            if not background:
                self._idle_step = 0
            if not self._sync_lock.acquire(blocking=False):
                self._rerun = self._rerun or not background
                return "Memory sync in progress"
        before: dict[str, Any] = {}
        sent = False
        try:
            before = self.state()
            with self._state_lock:
                generation = self._generation
            state = self.state()
            page = self.cloud.memory(cursor=int(state.get("cursor", 0)))
            with self._state_lock:
                if generation != self._generation:
                    return "Memory sync canceled"
            settings = page["settings"]
            if state.get("account") and (state.get("account") != settings["account_id"] or state.get("epoch") != settings["epoch"]):
                with self._state_lock:
                    if generation != self._generation:
                        return "Memory sync canceled"
                    self._clear()
                page = self.cloud.memory()
            while True:
                settings = page["settings"]
                state = {
                    "account": settings["account_id"],
                    "epoch": settings["epoch"],
                    "enabled": settings["enabled"],
                    "cursor": page["cursor"],
                    "vocabulary": [
                        i["preferred"]
                        for i in page["items"]
                        if i["kind"] == "vocabulary" and i["status"] == "confirmed" and i.get("preferred")
                    ],
                }
                with self._state_lock, self.store.connect() as c:
                    if generation != self._generation:
                        return "Memory sync canceled"
                    for item in page["captures"]:
                        if item.get("deleted_at"):
                            c.execute("DELETE FROM memory_outbox WHERE id=?", (item["id"],))
                    c.execute(
                        "DELETE FROM memory_outbox WHERE account<>? OR epoch<>?",
                        (state["account"], state["epoch"]),
                    )
                    if not state["enabled"]:
                        c.execute("DELETE FROM memory_outbox WHERE action='save'")
                    c.execute("INSERT OR REPLACE INTO memory_state VALUES(1,?)", (json.dumps(state),))
                if not page.get("has_more"):
                    break
                next_page = self.cloud.memory(cursor=int(state["cursor"]))
                if int(next_page["cursor"]) <= int(state["cursor"]):
                    raise ValueError("Memory cursor did not advance")
                page = next_page
            with self.store.connect() as c:
                pending = c.execute(
                    "SELECT * FROM memory_outbox ORDER BY CASE WHEN action='delete' THEN 0 ELSE 1 END"
                ).fetchall()
            for row in pending:
                with self._state_lock:
                    if generation != self._generation:
                        return "Memory sync canceled"
                # A local deletion may have replaced this queued save while awaiting I/O.
                with self._state_lock, self.store.connect() as c:
                    current = c.execute("SELECT payload FROM memory_outbox WHERE id=?", (row["id"],)).fetchone()
                    if not current or current["payload"] != row["payload"]:
                        continue
                try:
                    self.cloud.memory(json.loads(row["payload"]))
                    sent = True
                except Exception as exc:
                    if getattr(exc, "code", None) != "sync_conflict":
                        raise
                with self._state_lock, self.store.connect() as c:
                    if generation != self._generation:
                        return "Memory sync canceled"
                    c.execute(
                        "DELETE FROM memory_outbox WHERE id=? AND payload=?", (row["id"], row["payload"])
                    )
            self._last_status = (
                f"Memory synced · {len(state['vocabulary'])} approved words"
                if state["enabled"]
                else "Memory off — enable it in the workspace"
            )
            if sent or before != state:
                self._idle_step = 0
            return self._last_status
        except Exception as exc:
            if getattr(exc, "code", None) == "memory_not_available":
                self._last_status = "Account Memory is unavailable on the server. Local dictation is still available."
            else:
                self._last_status = "Memory sync pending. Local dictation is still available."
            return self._last_status
        finally:
            with self._state_lock:
                delays = (60, 120, 300, 900)
                self._next_poll = time.monotonic() + delays[self._idle_step]
                self._idle_step = min(self._idle_step + 1, len(delays) - 1)
                rerun = self._rerun
                self._rerun = False
                self._sync_lock.release()
            if rerun:
                # A capture/deletion arriving during a request must not wait for idle polling.
                threading.Thread(target=self.sync, daemon=True).start()


def is_private_capture(private: bool, exclusions: str, application: str | None = None) -> bool:
    excluded = {value.strip() for value in exclusions.split(",") if value.strip()}
    return private or bool(excluded and (application is None or application in excluded))
