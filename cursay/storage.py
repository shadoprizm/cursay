from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import DATABASE_FILE, ensure_directories


SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
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
);
CREATE INDEX IF NOT EXISTS idx_dictations_created_at ON dictations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dictations_mode ON dictations(mode);
"""


class HistoryStore:
    def __init__(self, path: Path = DATABASE_FILE) -> None:
        ensure_directories()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add(
        self,
        raw_text: str,
        final_text: str,
        mode: str,
        language: str | None,
        duration_seconds: float,
        provider: str | None,
        model: str | None,
        fillers_removed: list[str] | None = None,
        recording_path: str | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO dictations (
                    created_at, raw_text, final_text, mode, language, duration_seconds,
                    provider, model, word_count, fillers_removed_json, recording_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    raw_text,
                    final_text,
                    mode,
                    language,
                    max(0.0, float(duration_seconds)),
                    provider,
                    model,
                    len(final_text.split()),
                    json.dumps(fillers_removed or []),
                    recording_path,
                ),
            )
            return int(cursor.lastrowid)

    def search(self, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM dictations
                WHERE (? = '' OR final_text LIKE ? OR raw_text LIKE ?)
                ORDER BY created_at DESC LIMIT ?
                """,
                (query.strip(), pattern, pattern, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, row_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM dictations WHERE id = ?", (row_id,))

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            aggregate = connection.execute(
                """
                SELECT COUNT(*) AS dictations,
                       COALESCE(SUM(word_count), 0) AS words,
                       COALESCE(SUM(duration_seconds), 0) AS seconds
                FROM dictations
                """
            ).fetchone()
            recent = connection.execute(
                """
                SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count,
                       COALESCE(SUM(word_count), 0) AS words
                FROM dictations GROUP BY day ORDER BY day DESC LIMIT 14
                """
            ).fetchall()
            filler_rows = connection.execute(
                "SELECT fillers_removed_json FROM dictations ORDER BY created_at DESC LIMIT 500"
            ).fetchall()

        filler_counts: dict[str, int] = {}
        for row in filler_rows:
            try:
                values = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                values = []
            for filler in values:
                normalized = str(filler).lower().strip()
                if normalized:
                    filler_counts[normalized] = filler_counts.get(normalized, 0) + 1

        return {
            "dictations": int(aggregate["dictations"]),
            "words": int(aggregate["words"]),
            "seconds": float(aggregate["seconds"]),
            "recent": [dict(row) for row in recent],
            "fillers": sorted(filler_counts.items(), key=lambda item: (-item[1], item[0]))[:10],
        }
