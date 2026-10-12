from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


def words_per_minute(words: int, seconds: float) -> float | None:
    """Return output speed only when both words and recording time are known."""
    if words <= 0 or seconds <= 0 or not math.isfinite(seconds):
        return None
    return words * 60.0 / seconds


def dictation_word_count(row: dict[str, Any]) -> int:
    """Measure the generated voice output, excluding subsequent typed corrections."""
    original = row.get("original_final_text")
    return len(original.split()) if original is not None else int(row["word_count"])


def summarize_speed(
    rows: Iterable[dict[str, Any]], days: int = 30, now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate by local calendar day, weighting speed by recording duration."""
    if days not in (14, 30, 90):
        raise ValueError("Choose a 14-, 30-, or 90-day window")
    today = (now or datetime.now().astimezone()).date()
    start = today - timedelta(days=days - 1)
    daily = {
        (start + timedelta(days=offset)).isoformat(): {
            "day": (start + timedelta(days=offset)).isoformat(),
            "words": 0, "count": 0, "timed_words": 0, "seconds": 0.0, "timed_count": 0,
        }
        for offset in range(days)
    }
    total_words = 0
    total_seconds = 0.0
    latest_at: datetime | None = None
    latest_wpm: float | None = None
    for row in rows:
        words = dictation_word_count(row)
        seconds = float(row["duration_seconds"])
        wpm = words_per_minute(words, seconds)
        if wpm is not None:
            total_words += words
            total_seconds += seconds
        try:
            stamp = datetime.fromisoformat(row["created_at"])
        except (ValueError, TypeError):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        local_stamp = stamp.astimezone(now.tzinfo) if now is not None else stamp.astimezone()
        if latest_at is None or stamp > latest_at:
            latest_at, latest_wpm = stamp, wpm
        bucket = daily.get(local_stamp.date().isoformat())
        if bucket is None:
            continue
        bucket["words"] += words
        bucket["count"] += 1
        if wpm is not None:
            bucket["timed_words"] += words
            bucket["seconds"] += seconds
            bucket["timed_count"] += 1

    for bucket in daily.values():
        bucket["wpm"] = words_per_minute(bucket["timed_words"], bucket["seconds"])
    period_words = sum(bucket["timed_words"] for bucket in daily.values())
    period_seconds = sum(bucket["seconds"] for bucket in daily.values())
    return {
        "days": days,
        "daily": list(daily.values()),
        "wpm": words_per_minute(period_words, period_seconds),
        "lifetime_wpm": words_per_minute(total_words, total_seconds),
        "latest_wpm": latest_wpm,
        "timed_count": sum(bucket["timed_count"] for bucket in daily.values()),
        "words": sum(bucket["words"] for bucket in daily.values()),
    }
