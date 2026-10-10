from __future__ import annotations
import json
import threading
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

    def sync(self) -> str:
        if not self._sync_lock.acquire(blocking=False):
            return "Memory sync in progress"
        try:
            with self._state_lock:
                generation = self._generation
            state = self.state()
            page = self.cloud.memory(cursor=int(state.get("cursor", 0)))
            with self._state_lock:
                if generation != self._generation:
                    return "Memory sync canceled"
            settings = page["settings"]
            if state.get("account") != settings["account_id"] or state.get("epoch") != settings["epoch"]:
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
                page = self.cloud.memory(cursor=int(state["cursor"]))
            with self.store.connect() as c:
                pending = c.execute(
                    "SELECT * FROM memory_outbox ORDER BY CASE WHEN action='delete' THEN 0 ELSE 1 END"
                ).fetchall()
            for row in pending:
                with self._state_lock:
                    if generation != self._generation:
                        return "Memory sync canceled"
                try:
                    self.cloud.memory(json.loads(row["payload"]))
                except Exception as exc:
                    if getattr(exc, "code", None) != "sync_conflict":
                        raise
                with self._state_lock, self.store.connect() as c:
                    if generation != self._generation:
                        return "Memory sync canceled"
                    c.execute(
                        "DELETE FROM memory_outbox WHERE id=? AND payload=?", (row["id"], row["payload"])
                    )
            return (
                f"Memory synced · {len(state['vocabulary'])} approved words"
                if state["enabled"]
                else "Memory off — enable it in the workspace"
            )
        except Exception:
            return "Memory sync pending. Local dictation is still available."
        finally:
            self._sync_lock.release()


def is_private_capture(private: bool, exclusions: str, application: str | None = None) -> bool:
    excluded = {value.strip() for value in exclusions.split(",") if value.strip()}
    return private or bool(excluded and (application is None or application in excluded))
